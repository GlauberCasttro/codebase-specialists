"""Auditoria 1.4 (iteração 3, P0): todo `check` de references/stages.json5 prova o EFEITO da sub-etapa.

Para cada check há um cenário em que o subcomando ANTIGO "passava" (ou travava a etapa) sem o efeito ter
acontecido; o check ATUAL — lido do stages.json5 real e executado por `stage.engine.run_check`, exatamente como
`cs.py stage done` faz — tem de falhar nele, e passar depois que o efeito acontece.
`test_every_check_is_audited` garante que check novo em stages.json5 não entra sem cenário aqui.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (SCRIPTS, os.path.join(SCRIPTS, "team", "tests"), os.path.join(SCRIPTS, "probes", "tests"),
          os.path.join(SCRIPTS, "emit", "tests"), os.path.join(SCRIPTS, "sanitize", "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)
import synth  # noqa: E402

from cslib import json5io  # noqa: E402
from cslib.paths import STATE_DIR  # noqa: E402
from stage import engine  # noqa: E402
from team._shared_tmp.common import read_json, sp_path, write_json  # noqa: E402

CS = os.path.join(SCRIPTS, "cs.py")
CFG = engine.load_stages(engine.STAGES_FILE)
CHECKS = {s["id"]: s["check"] for n in CFG["order"] for s in CFG["stages"][n]["substages"] if s.get("check")}
GIT = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]


def cs(root, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CS_STAGES_FILE", None)
    p = subprocess.run([sys.executable, CS, "--target", root] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=env, cwd=root)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def check(root, sid):
    ok, code, detail, _ = engine.run_check(root, CHECKS[sid])
    return ok, detail


def old(root, cmd):
    """O check ANTIGO (iteração 2) — só para provar que ele passava no cenário sem efeito."""
    ok, code, detail, _ = engine.run_check(root, cmd)
    return ok


def git_init(root):
    subprocess.run(["git", "-C", root, "init", "-q"], check=True)
    subprocess.run(GIT + ["-C", root, "add", "-A"], check=True)
    subprocess.run(GIT + ["-C", root, "commit", "-qm", "init"], check=True)


def card(name, facts=("gl.invoice",)):
    return {"description": "Use para mudar %s." % name, "mission": "Mantém %s correto." % name,
            "knows": [{"text": "Invoice é o termo canônico", "facts": list(facts)}] if facts else [],
            "refuses": [{"text": "usar float para dinheiro", "why": "ADR 1", "facts": ["rat.adr.money"]}],
            "done_when": "`python3 -m unittest discover -s tests` sai 0",
            "playbooks": [], "rules": [], "footguns": [], "anchors": ["src/billing/invoice.py"]}


class Synth(unittest.TestCase):
    """Repo sintético com fatos (team/tests/synth) + roster derivado."""

    def setUp(self):
        from team.derive import derive
        self.root = synth.make_repo()
        derive(self.root)
        self.agents = [a["name"] for a in read_json(sp_path(self.root, "team.json5"))["agents"]]

    def tearDown(self):
        synth.cleanup(self.root)

    def put(self, rel, obj):
        full = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write(json.dumps(obj))
        return rel

    def draft_all(self):
        for a in self.agents:
            rel = self.put(".swarm/tmp/cards/%s.json5" % a, {"agent": a, "card": card(a), "camadas": {
                "s0_core": [{"text": "Dinheiro em centavos inteiros", "facts": ["rat.adr.money"]}]}})
            c, o, e = cs(self.root, "team", "card", "set", a, "--file", rel)
            self.assertEqual(c, 0, o + e)

    def panel_all(self):
        self.assertEqual(cs(self.root, "panel", "plan")[0], 0)
        pl = read_json(sp_path(self.root, "panel", "plan.json5"))
        empty = {"afirmacoes_sem_evidencia": [], "conflitos_com_meu_territorio": [], "regras_cross_cutting_faltando": []}
        for a, v in pl["agents"].items():
            for r in v["reviewers"]:
                rel = self.put(".swarm/tmp/rev/%s.%s.json5" % (a, r["name"]), empty)
                c, o, e = cs(self.root, "panel", "record", a, "--reviewer", r["name"], "--file", rel)
                self.assertEqual(c, 0, o + e)


# ------------------------------------------------------------------ init

class Init(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="cs-audit-"))
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_init_1_target_must_be_repo_root(self):
        sub = os.path.join(self.root, "pkg")
        os.makedirs(sub)
        self.assertTrue(old(sub, "git -C {target} rev-parse --git-dir"))  # antes: subdiretório passava
        self.assertFalse(check(sub, "init.1")[0])
        self.assertTrue(check(self.root, "init.1")[0])

    def test_init_3_needs_explicit_init(self):
        cs(self.root, "stage", "load", "init")  # cria run.json5 sozinho (plataformas default)
        # iteração 2: `init --check` passava com o run.json5 criado pelo `stage load` (plataformas default)
        self.assertFalse(check(self.root, "init.3")[0])
        cs(self.root, "init", "--platforms", "claude-code,cursor")
        self.assertTrue(check(self.root, "init.3")[0])


# ------------------------------------------------------------------ scan (scan real num repo minúsculo)

class Scan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = os.path.realpath(tempfile.mkdtemp(prefix="cs-audit-scan-"))
        files = {"src/a/x.py": "from src.b.m import f\n\n\ndef g():\n    return f()\n",
                 "src/b/m.py": "def f():\n    return 1\n", "tests/test_x.py": "import unittest\n",
                 "README.md": "# Tiny\n"}
        for rel, txt in files.items():
            full = os.path.join(cls.root, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as fh:
                fh.write(txt)
        git_init(cls.root)
        code, o, e = cs(cls.root, "scan", "--no-exec")
        assert code == 0, o + e

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_scan_1_to_4_facts_must_describe_current_code(self):
        for sid in ("scan.1", "scan.2", "scan.3", "scan.4"):
            self.assertTrue(check(self.root, sid)[0], sid)
        with open(os.path.join(self.root, "src", "b", "m.py"), "a") as fh:
            fh.write("\n\ndef h():\n    return 2\n")
        subprocess.run(GIT + ["-C", self.root, "commit", "-qam", "muda produto"], check=True)
        try:
            self.assertTrue(old(self.root, "cs.py scan --layers L0,L1,L2,L3 --check"))  # antes: só um AVISO
            for sid in ("scan.1", "scan.2", "scan.3", "scan.4"):
                ok, detail = check(self.root, sid)
                self.assertFalse(ok, sid)
                self.assertIn("fatos velhos", detail)
        finally:
            cs(self.root, "scan", "--no-exec")
        self.assertTrue(check(self.root, "scan.1")[0])


class Spotcheck(Synth):
    def test_scan_5_rescanned_fact_needs_new_check(self):
        ids = ["gl.invoice", "rat.adr.money", "br.refund.window", "rules.lint.ruff-e", "ops.test.unittest"]
        for f in ids:
            self.assertEqual(cs(self.root, "facts", "spotcheck", "record", "--fact", f, "--verdict", "ok",
                                "--note", "conferido")[0], 0)
        self.assertTrue(check(self.root, "scan.5")[0])
        # re-scan mudou o fato conferido: a conferência era de OUTRO fato
        g = read_json(sp_path(self.root, "facts", "glossary.json5"))
        g["facts"][0]["claim"] = "Fatura é o termo canônico"
        g["facts"][0]["fingerprint"] = "y"
        write_json(self.root, sp_path(self.root, "facts", "glossary.json5"), g)
        # iteração 2: `facts spotcheck --min 5` contava a conferência do fato ANTERIOR ao re-scan
        ok, detail = check(self.root, "scan.5")
        self.assertFalse(ok)
        cs(self.root, "facts", "spotcheck", "record", "--fact", "gl.invoice", "--verdict", "ok", "--note", "de novo")
        self.assertTrue(check(self.root, "scan.5")[0])


class Interview(Synth):
    def test_scan_6_answers_must_be_facts(self):
        cs(self.root, "interview", "record", "--id", "Q-01", "--question", "Quem aprova estorno?", "--answer", "Carla")
        cs(self.root, "interview", "record", "--id", "Q-02", "--question", "Prazo de chargeback?", "--answer-unknown")
        self.assertTrue(check(self.root, "scan.6")[0])
        idx = read_json(sp_path(self.root, "facts", "index.json5"))
        self.assertIn("gap.q-02", idx["facts"])
        # re-scan regrava o índice sem a entrevista: a resposta "existe" no log mas não é fato
        idx["facts"] = [f for f in idx["facts"] if not f.startswith(("interview.", "gap."))]
        write_json(self.root, sp_path(self.root, "facts", "index.json5"), idx)
        self.assertFalse(check(self.root, "scan.6")[0])
        self.assertEqual(cs(self.root, "interview", "sync")[0], 0)
        self.assertTrue(check(self.root, "scan.6")[0])


# ------------------------------------------------------------------ specialize

class Specialize(Synth):
    def test_specialize_1_roster_must_come_from_derive(self):
        self.assertTrue(check(self.root, "specialize.1")[0])
        os.remove(sp_path(self.root, "team-derivation.json5"))  # team.json5 "à mão"
        # iteração 2: `team validate --stage derive` passava com team.json5 escrito à mão
        self.assertFalse(check(self.root, "specialize.1")[0])

    def test_specialize_2_approval_of_valid_roster(self):
        cs(self.root, "team", "approve", "--by", "ana")
        self.assertTrue(check(self.root, "specialize.2")[0])
        full = os.path.join(self.root, "src", "novo", "mod.py")
        os.makedirs(os.path.dirname(full))
        with open(full, "w") as fh:
            fh.write("x = 1\n")
        inv = read_json(sp_path(self.root, "facts", "inventory.json5"))
        inv["files"].append({"path": "src/novo/mod.py", "class": "product"})
        write_json(self.root, sp_path(self.root, "facts", "inventory.json5"), inv)
        self.assertFalse(check(self.root, "specialize.2")[0])  # antes: sha do roster igual → "aprovado"

    def test_specialize_3_card_must_cite_facts(self):
        self.draft_all()
        self.assertTrue(check(self.root, "specialize.3")[0])
        rel = self.put(".swarm/tmp/cards/x.json5", dict(card("qa", facts=None),
                                                              refuses=[{"text": "x", "why": "y"}]))
        self.assertEqual(cs(self.root, "team", "card", "set", "qa", "--file", rel)[0], 0)
        self.assertFalse(check(self.root, "specialize.3")[0])

    def test_specialize_4_core_by_command(self):
        self.draft_all()
        t = read_json(sp_path(self.root, "team.json5"))
        t["core"]["lines"] = [{"text": "Dinheiro em centavos inteiros", "facts": ["rat.adr.money"]}]
        write_json(self.root, sp_path(self.root, "team.json5"), t)  # núcleo escrito à mão
        self.assertTrue(old(self.root, "cs.py emit budget"))
        self.assertFalse(check(self.root, "specialize.4")[0])
        self.assertEqual(cs(self.root, "team", "core", "from-panel")[0], 0)
        ok, detail = check(self.root, "specialize.4")
        self.assertTrue(ok, detail)

    def test_specialize_5_existence_in_every_mode(self):
        self.draft_all()
        ok, detail = check(self.root, "specialize.5")
        self.assertTrue(ok, detail)
        c = card("dev-billing")
        c["knows"].append({"text": "o cálculo vive em `src/billing/nao_existe.py`", "facts": ["gl.invoice"]})
        self.assertEqual(cs(self.root, "team", "card", "set", "dev-billing", "--file",
                            self.put(".swarm/tmp/b.json5", c))[0], 0)
        # sem mesa redonda (--fast): specialize.5 é a única conferência antes do verify
        self.assertFalse(os.path.exists(sp_path(self.root, "panel", "dev-billing.json5")))
        self.assertFalse(check(self.root, "specialize.5")[0])
        fb = sp_path(self.root, "probes", "existence-fix", "dev-billing.json5")
        self.assertTrue(os.path.isfile(fb))
        self.assertIn("src/billing/nao_existe.py", [m["value"] for m in read_json(fb)["missing"]])
        code, o, e = cs(self.root, "team", "card", "revise", "dev-billing", "--file",
                        self.put(".swarm/tmp/limpo.json5", card("dev-billing")), "--note", "conserto")
        self.assertEqual(code, 0, o + e)
        ok, detail = check(self.root, "specialize.5")
        self.assertTrue(ok, detail)
        self.assertFalse(os.path.exists(fb))


# ------------------------------------------------------------------ round-table

class RoundTable(Synth):
    def test_rt_1_review_of_current_draft(self):
        self.draft_all()
        self.panel_all()
        self.assertTrue(check(self.root, "rt.1")[0])
        c = card("dev-billing")
        c["mission"] = "redigido de novo depois da revisão"
        rel = self.put(".swarm/tmp/cards/again.json5", c)
        cs(self.root, "team", "card", "set", "dev-billing", "--file", rel)
        # iteração 2: `panel status --all-reviewed` passava (revisões de um rascunho que não existe mais)
        self.assertFalse(check(self.root, "rt.1")[0])

    def test_rt_2_existence_fed_to_author_and_gone_after_revision(self):
        self.draft_all()
        c = card("dev-billing")
        c["knows"].append({"text": "o cálculo vive em `src/billing/nao_existe.py`", "facts": ["gl.invoice"]})
        cs(self.root, "team", "card", "set", "dev-billing", "--file", self.put(".swarm/tmp/b.json5", c))
        self.panel_all()
        # antes de rt.4 a falta é ESPERADA: o check antigo (G2 estrito) travava a etapa aqui
        self.assertFalse(old(self.root, "cs.py probes existence"))
        self.assertTrue(check(self.root, "rt.2")[0])
        self.assertEqual(cs(self.root, "panel", "consolidate")[0], 0)
        doc = read_json(sp_path(self.root, "panel", "dev-billing.json5"))
        self.assertIn("src/billing/nao_existe.py",
                      [x.get("ref") for x in doc["confirmed"]["afirmacoes_sem_evidencia"]])
        self.assertTrue(check(self.root, "rt.2")[0])
        # iteração 4: revisão que não corrige a falta de existência é RECUSADA (exit 2) e não conta como revisada
        code, _, err = cs(self.root, "team", "card", "revise", "dev-billing", "--note", "ignorei")
        self.assertEqual(code, 2, err)
        self.assertIn("src/billing/nao_existe.py", err)
        self.assertFalse(read_json(sp_path(self.root, "cards", "status.json5")).get("dev-billing", {}).get("revised"))

    def test_rt_3_core_promotion_registered(self):
        self.draft_all()
        self.panel_all()
        cs(self.root, "panel", "consolidate")
        self.assertTrue(old(self.root, "cs.py panel consolidate --check"))
        self.assertFalse(check(self.root, "rt.3")[0])
        self.assertEqual(cs(self.root, "team", "core", "from-panel")[0], 0)
        self.assertTrue(check(self.root, "rt.3")[0])

    def test_rt_4_revision_must_fix_existence(self):
        self.draft_all()
        c = card("dev-billing")
        c["anchors"] = ["src/billing/sumiu.py"]
        cs(self.root, "team", "card", "set", "dev-billing", "--file", self.put(".swarm/tmp/b.json5", c))
        self.panel_all()
        cs(self.root, "panel", "consolidate")
        for a in self.agents:
            cs(self.root, "team", "card", "revise", a, "--note", "nada a mudar")
        # iteração 2: `card-status --all-revised` passava (revisado por nota, faltas de existência intactas)
        self.assertFalse(check(self.root, "rt.4")[0])


# ------------------------------------------------------------------ validate

class Validate1(unittest.TestCase):
    def setUp(self):
        import fixture
        self.root = fixture.make_repo()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_validate_1_all_run_platforms_emitted(self):
        t = json5io.load(os.path.join(self.root, STATE_DIR, "team.json5"))
        t["platforms"] = ["claude-code"]  # team derivado antes do init escolher cursor também
        json5io.dump(t, os.path.join(self.root, STATE_DIR, "team.json5"), "t", target=self.root)
        self.assertEqual(cs(self.root, "emit", "--platforms", "claude-code", "--allow-outside")[0], 0)
        json5io.dump({"platforms": ["claude-code", "cursor"]}, os.path.join(self.root, STATE_DIR, "run.json5"),
                     "r", target=self.root)
        self.assertFalse(check(self.root, "validate.1")[0])
        self.assertEqual(cs(self.root, "emit", "--allow-outside")[0], 0)
        self.assertTrue(check(self.root, "validate.1")[0])


class Probes(Synth):
    def setUp(self):
        Synth.setUp(self)
        from probes.generate import generate
        self.bank = generate(self.root, seed="s1")

    def answers(self, a, good=True):
        from probes.generate import load_bank
        from test_probes import perfect
        ps = [p for p in load_bank(self.root)["probes"] if p["agent"] == a]
        items = [perfect(p) for p in ps] if good else [{"id": p["id"], "answer": "não sei",
                                                         "evidence": ["grep -rn x src"]} for p in ps]
        write_json(self.root, sp_path(self.root, "probes", "exams", "%s.answers.json5" % a), items)

    def baseline(self, a, real=True):
        from probes.exam import baseline_filter
        from probes.generate import load_bank
        items = [{"id": p["id"], "answer": "não sei"} for p in load_bank(self.root)["probes"] if p["agent"] == a] \
            if real else []
        write_json(self.root, sp_path(self.root, "probes", "exams", "%s.baseline.json5" % a), items)
        baseline_filter(self.root, a)

    def test_validate_2_baseline_actually_ran(self):
        for a in self.agents:
            self.baseline(a, real=False)  # [] gravado só para "passar"
        # iteração 2: `baseline-filter --check` passava com baseline vazio ([] gravado só para passar)
        self.assertFalse(check(self.root, "validate.2")[0])
        for a in self.agents:
            self.baseline(a)
        self.assertTrue(check(self.root, "validate.2")[0])

    def test_validate_3_exam_complete_without_pending_judges(self):
        for a in self.agents:
            self.baseline(a)
            self.answers(a)
        self.assertTrue(old(self.root, "cs.py probes check --all"))  # PASS provisório (painel POR-QUÊ pendente)
        self.assertFalse(check(self.root, "validate.3")[0])
        from panel.core import why_verdict
        from probes.generate import load_bank
        for p in load_bank(self.root)["probes"]:
            if p.get("panel"):
                why_verdict(self.root, p["agent"], p["id"], "PASS")
        self.assertTrue(check(self.root, "validate.3")[0])

    def test_validate_4_no_exhaustion_without_refine(self):
        from probes.generate import generate
        bad = "dev-billing"
        for a in self.agents:
            self.baseline(a)
            self.answers(a, good=(a != bad))
        cs(self.root, "probes", "check", "--all")
        for seed in ("s2", "s3"):  # iteração 2: bancos novos repontuavam respostas VELHAS → esgotava sem refino
            generate(self.root, seed=seed)
            cs(self.root, "probes", "check", "--all")
        code, o, e = cs(self.root, "probes", "check", "--all", "--final", "--allow-non-specialist",
                        "--reason", "sem refino")
        self.assertNotEqual(code, 0, "aceitar nao-especialista exige 2 refinos DE VERDADE")
        self.assertIn("refino pendente", e)
        self.assertFalse(check(self.root, "validate.4")[0])
        cyc = read_json(sp_path(self.root, "probes", "cycles.json5"))
        self.assertEqual(len(cyc[bad]), 1)


class Harness(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="cs-audit-h-"))
        with open(os.path.join(self.root, "README.md"), "w") as fh:
            fh.write("# x\n")
        git_init(self.root)
        cs(self.root, "init", "--platforms", "claude-code,cursor")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_validate_5_installed_for_run_platforms(self):
        self.assertEqual(cs(self.root, "harness", "install", "--no-makefile", "--allow-outside")[0], 0)
        ok, detail = check(self.root, "validate.5")
        self.assertFalse(ok, "sem adapter do Cursor e sem pre-commit o selftest passava")
        self.assertEqual(cs(self.root, "harness", "install", "--no-makefile", "--allow-outside", "--platforms", "cursor",
                            "--git-hook")[0], 0)
        ok, detail = check(self.root, "validate.5")
        self.assertTrue(ok, detail)

    def test_approve_3_session_saved_after_decision(self):
        self.assertEqual(cs(self.root, "harness", "install", "--no-makefile", "--allow-outside")[0], 0)
        save = os.path.join(SCRIPTS, "harness", "engine", "session.py")
        r = subprocess.run([sys.executable, save, "--root", self.root, "save", "--did", "x", "--next", "y"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(check(self.root, "approve.3")[0])
        time.sleep(1.1)
        with open(os.path.join(self.root, STATE_DIR, "approvals.jsonl"), "a") as fh:
            fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                                 "decision": "GO"}) + "\n")
        self.assertFalse(check(self.root, "approve.3")[0])  # antes: o save velho "congelava" o baseline


class VerifyApprove(Synth):
    def fake_verify(self, passed=True):
        from verify import gates as G

        def fn(t, c):
            return [G.gate(g, n, passed, "fake", "x") for g, n in G.GATES]
        return G.verify(self.root, gates_fn=fn)

    def test_validate_6_recorded_and_fresh_no_go_closes(self):
        self.fake_verify(passed=False)
        self.assertFalse(old(self.root, "cs.py approve --check"))  # NO-GO: validate nunca fechava (verify exit 1)
        self.assertTrue(check(self.root, "validate.6")[0])
        t = read_json(sp_path(self.root, "team.json5"))
        t["core"]["lines"] = [{"text": "x", "facts": ["rat.adr.money"]}]
        write_json(self.root, sp_path(self.root, "team.json5"), t)
        self.assertFalse(check(self.root, "validate.6")[0])

    def test_approve_1_report_of_current_acceptance(self):
        self.fake_verify()
        self.assertFalse(check(self.root, "approve.1")[0])  # antes: sem check (nota manual bastava)
        self.assertEqual(cs(self.root, "report")[0], 0)
        self.assertTrue(check(self.root, "approve.1")[0])
        time.sleep(1.1)
        self.fake_verify(passed=False)
        self.assertFalse(check(self.root, "approve.1")[0])

    def test_approve_2_decision_on_current_acceptance(self):
        self.fake_verify()
        cs(self.root, "approve", "--by", "eval", "--decision", "GO", "--simulated")
        self.assertTrue(check(self.root, "approve.2")[0])
        acc = read_json(sp_path(self.root, "acceptance.json5"))
        self.assertEqual(acc["approval"], "simulated")
        t = read_json(sp_path(self.root, "team.json5"))
        t["core"]["lines"] = [{"text": "mudou depois", "facts": ["rat.adr.money"]}]
        write_json(self.root, sp_path(self.root, "team.json5"), t)
        # iteração 2: `approve --check` passava sobre acceptance velho (team mudou depois do verify)
        self.assertFalse(check(self.root, "approve.2")[0])
        # NO-GO formal: registrável e fecha approve.2
        self.fake_verify(passed=False)
        cs(self.root, "approve", "--by", "ana", "--decision", "NO-GO", "--note", "2 gates vermelhos")
        self.assertTrue(check(self.root, "approve.2")[0])


class Sanitize(unittest.TestCase):
    def setUp(self):
        import test_sanitize
        self.root = test_sanitize.post_init_repo()
        self.sp = os.path.join(self.root, test_sanitize.D)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_approve_4_sanitize_before_final_save(self):
        ok, detail = check(self.root, "approve.4")
        self.assertFalse(ok, "tmp/ cheio e sem .gitignore")
        self.assertEqual(cs(self.root, "sanitize", "--apply")[0], 0)
        ok, detail = check(self.root, "approve.4")
        self.assertTrue(ok, detail)
        os.remove(os.path.join(self.sp, ".gitignore"))
        ok, detail = check(self.root, "approve.4")
        self.assertFalse(ok)
        self.assertIn(".gitignore", detail)
        self.assertEqual(cs(self.root, "sanitize", "--apply")[0], 0)
        os.makedirs(os.path.join(self.sp, "copia", ".git"))
        ok, detail = check(self.root, "approve.4")
        self.assertFalse(ok)
        self.assertIn(".git aninhado", detail)
        shutil.rmtree(os.path.join(self.sp, "copia"))
        ok, detail = check(self.root, "approve.4")
        self.assertTrue(ok, detail)


class Meta(unittest.TestCase):
    AUDITED = {
        "init.1": Init.test_init_1_target_must_be_repo_root, "init.3": Init.test_init_3_needs_explicit_init,
        "scan.1": Scan.test_scan_1_to_4_facts_must_describe_current_code,
        "scan.2": Scan.test_scan_1_to_4_facts_must_describe_current_code,
        "scan.3": Scan.test_scan_1_to_4_facts_must_describe_current_code,
        "scan.4": Scan.test_scan_1_to_4_facts_must_describe_current_code,
        "scan.5": Spotcheck.test_scan_5_rescanned_fact_needs_new_check,
        "scan.6": Interview.test_scan_6_answers_must_be_facts,
        "specialize.1": Specialize.test_specialize_1_roster_must_come_from_derive,
        "specialize.2": Specialize.test_specialize_2_approval_of_valid_roster,
        "specialize.3": Specialize.test_specialize_3_card_must_cite_facts,
        "specialize.4": Specialize.test_specialize_4_core_by_command,
        "specialize.5": Specialize.test_specialize_5_existence_in_every_mode,
        "rt.1": RoundTable.test_rt_1_review_of_current_draft,
        "rt.2": RoundTable.test_rt_2_existence_fed_to_author_and_gone_after_revision,
        "rt.3": RoundTable.test_rt_3_core_promotion_registered,
        "rt.4": RoundTable.test_rt_4_revision_must_fix_existence,
        "validate.1": Validate1.test_validate_1_all_run_platforms_emitted,
        "validate.2": Probes.test_validate_2_baseline_actually_ran,
        "validate.3": Probes.test_validate_3_exam_complete_without_pending_judges,
        "validate.4": Probes.test_validate_4_no_exhaustion_without_refine,
        "validate.5": Harness.test_validate_5_installed_for_run_platforms,
        "validate.6": VerifyApprove.test_validate_6_recorded_and_fresh_no_go_closes,
        "approve.1": VerifyApprove.test_approve_1_report_of_current_acceptance,
        "approve.2": VerifyApprove.test_approve_2_decision_on_current_acceptance,
        "approve.3": Harness.test_approve_3_session_saved_after_decision,
        "approve.4": Sanitize.test_approve_4_sanitize_before_final_save,
    }

    def test_every_check_is_audited(self):
        self.assertEqual(sorted(CHECKS), sorted(self.AUDITED))

    def test_every_check_command_exists_in_cli(self):
        sys.path.insert(0, SCRIPTS)
        import cs as cli  # noqa
        parser = cli.build_parser()
        for sid, chk in sorted(CHECKS.items()):
            argv = chk.replace("{target}", "/tmp").split()
            if argv[0] != "cs.py":
                continue
            try:
                parser.parse_args(argv[1:])
            except SystemExit:
                self.fail("%s: `%s` não existe na CLI" % (sid, chk))


if __name__ == "__main__":
    unittest.main()
