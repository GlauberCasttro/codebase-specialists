"""Iteração 4 (frente probes/verify) — um teste de regressão por defeito da rodada 3.

1. exam-pack com histórico: a cópia é um clone local do alvo sem .swarm/; `git log` na cópia mostra só o
   histórico do alvo (nunca o de um repo pai); `--out` aceito dentro de <alvo>/.swarm/tmp/.
2. não medido ≠ reprovado: ≥6 sondas positivas "difíceis" no território; território saturado pelo baseline usa o
   score sem filtro e marca `baseline_saturated: true`.
3. NONE_RE só casa resposta que É negativa; veredito do painel POR-QUÊ prevalece sobre a heurística.
4. `--allow-non-specialist` vale com validate.4 pulado (--fast) e por agente.
5. `probes check <a>` depois de `--closed` não quebra (KeyError 'decision').
6. refs: proibição citada (`nunca use pickle.load`) não é símbolo inexistente.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "team", "tests"))
sys.path.insert(0, HERE)
import synth  # noqa: E402

from cslib import refs  # noqa: E402
from cslib.paths import STATE_DIR  # noqa: E402
from team._shared_tmp.cardtext import extract_refs  # noqa: E402
from team._shared_tmp.common import read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402
from probes.exam import Checker, baseline_filter, is_none  # noqa: E402
from probes.generate import generate, load_bank, probe_sha  # noqa: E402
from test_probes import perfect  # noqa: E402
from test_final import cs  # noqa: E402

GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_NOSYSTEM="1", LC_ALL="C")


def git(cwd, *args, check=True):
    p = subprocess.run(["git", "-C", cwd, "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false"]
                       + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=GIT_ENV)
    if check and p.returncode != 0:
        raise AssertionError("git %s: %s" % (args, p.stderr.decode()))
    return p.returncode, p.stdout.decode().strip()


def commit_all(cwd, msg):
    git(cwd, "add", "-A")
    git(cwd, "commit", "-q", "-m", msg)
    return git(cwd, "rev-parse", "HEAD")[1]


def shas(cwd):
    code, out = git(cwd, "log", "--all", "--format=%H", check=False)
    return code, set(out.split()) if code == 0 else set()


AGENT = "dev-billing"


class ExamPackHistory(unittest.TestCase):
    def setUp(self):
        self.parent = os.path.realpath(tempfile.mkdtemp(prefix="cs-parent-"))
        git(self.parent, "init", "-q")
        with open(os.path.join(self.parent, "outro.txt"), "w") as fh:
            fh.write("repo pai\n")
        self.parent_sha = commit_all(self.parent, "commit do repo PAI")
        self.root = synth.make_repo()
        derive(self.root)
        generate(self.root)

    def tearDown(self):
        synth.cleanup(self.root)
        shutil.rmtree(self.parent, ignore_errors=True)

    def git_target(self):
        with open(os.path.join(self.root, ".gitignore"), "w") as fh:
            fh.write(".swarm/\n")
        git(self.root, "init", "-q")
        first = commit_all(self.root, "init")
        with open(os.path.join(self.root, "src", "billing", "tax.py"), "a") as fh:
            fh.write("# fix rounding\n")
        second = commit_all(self.root, "fix rounding in tax")
        return {first, second}

    def pack(self, out):
        code, o, e = cs(self.root, "probes", "exam-pack", AGENT, "--out", out)
        self.assertEqual(code, 0, o + e)
        return os.path.join(out, "repo")

    def assert_no_specialists(self, out):
        for dp, dn, fn in os.walk(os.path.join(out, "repo")):
            self.assertNotIn(STATE_DIR, dn, dp)

    def test_clone_has_target_history_only_even_inside_parent_repo(self):
        mine = self.git_target()
        out = os.path.join(self.parent, "exams", AGENT)
        repo = self.pack(out)
        code, got = shas(repo)
        self.assertEqual(code, 0, "git -C <out>/repo log tem de funcionar")
        self.assertEqual(got, mine)
        self.assertNotIn(self.parent_sha, got, "git log da cópia subiu para o repo pai")
        self.assertEqual(git(repo, "rev-parse", "--show-toplevel")[1], os.path.realpath(repo))
        self.assertEqual(git(repo, "remote")[1], "", "a cópia não aponta de volta para o alvo")
        self.assertIn("fix rounding in tax", git(repo, "log", "--format=%s")[1])
        self.assert_no_specialists(out)
        man = read_json(os.path.join(out, "exam.json5"))
        self.assertEqual(man["history"]["mode"], "clone")

    def test_working_tree_state_is_what_the_examinee_sees(self):
        self.git_target()
        with open(os.path.join(self.root, "src", "billing", "refund.py"), "a") as fh:
            fh.write("# não commitado\n")
        repo = self.pack(os.path.join(self.parent, "exams", AGENT))
        with open(os.path.join(repo, "src", "billing", "refund.py")) as fh:
            self.assertIn("# não commitado", fh.read())

    def test_out_inside_specialists_tmp_is_accepted(self):
        mine = self.git_target()
        out = os.path.join(self.root, STATE_DIR, "tmp", "exam", AGENT)
        repo = self.pack(out)
        self.assertEqual(shas(repo)[1], mine)
        self.assert_no_specialists(out)
        self.assertFalse(os.path.exists(os.path.join(repo, STATE_DIR)))

    def test_out_inside_target_outside_tmp_is_refused(self):
        code, _, err = cs(self.root, "probes", "exam-pack", AGENT, "--out", os.path.join(self.root, "exam"))
        self.assertEqual(code, 2)
        self.assertIn(".swarm/tmp/", err)

    def test_specialists_in_history_never_reaches_the_copy(self):
        git(self.root, "init", "-q")
        commit_all(self.root, "versionou .swarm (gabarito no histórico)")
        out = os.path.join(self.parent, "exams", AGENT)
        repo = self.pack(out)
        code, got = shas(repo)
        self.assertFalse(got & {self.parent_sha}, "nunca commits de outro repo")
        self.assertEqual(got, set(), "histórico com .swarm/ não entra na cópia")
        self.assert_no_specialists(out)
        self.assertEqual(read_json(os.path.join(out, "exam.json5"))["history"]["mode"], "none")

    def test_non_git_target_never_shows_parent_history(self):
        out = os.path.join(self.parent, "exams", AGENT)
        repo = self.pack(out)
        code, got = shas(repo)
        self.assertNotIn(self.parent_sha, got)
        self.assertEqual(got, set())
        self.assertEqual(git(repo, "rev-parse", "--show-toplevel")[1], os.path.realpath(repo))


class NotMeasured(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def test_generator_guarantees_hard_positive_territory_probes(self):
        from probes.generate import HARD_MIN, is_hard
        bank = generate(self.root)
        for a in sorted(bank["agents"]):
            hard = [p for p in bank["probes"] if p["agent"] == a and p["scope"] == "territory" and is_hard(p)]
            self.assertGreaterEqual(len(hard), HARD_MIN, "%s: só %d sondas positivas difíceis" % (a, len(hard)))

    def test_saturated_territory_uses_raw_score_and_is_flagged(self):
        bank = generate(self.root)
        a = "ops"
        ps = [p for p in bank["probes"] if p["agent"] == a]
        # baseline sem cartão acerta TODO o território (ex.: tudo negativa "NENHUM")
        write_json(self.root, sp_path(self.root, "probes", "exams", "%s.baseline.json5" % a),
                   [perfect(p) if p["scope"] == "territory" else {"id": p["id"], "answer": "não sei"} for p in ps])
        baseline_filter(self.root, a)
        write_json(self.root, sp_path(self.root, "probes", "exams", "%s.answers.json5" % a), [perfect(p) for p in ps])
        code, out, err = cs(self.root, "probes", "check", a)
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("None", out)
        rep = read_json(sp_path(self.root, "probes", "reports", "%s.json5" % a))
        self.assertEqual(rep["score_territory"], 1.0)
        self.assertTrue(rep["baseline_saturated"])
        agg = read_json(sp_path(self.root, "probes", "report.json5"))
        self.assertTrue(agg["agents"][a]["baseline_saturated"])


class NoneAnswers(unittest.TestCase):
    def test_only_real_negatives(self):
        for t in ("NENHUM", "nenhuma", "não existe", "Não existe.", "none", "N/A", "n/a", "Não.", "nenhum (só um "
                  "comentário em a/b.ts)", "NENHUM — nada importa"):
            self.assertTrue(is_none(t), t)
        for t in ("Na Black Friday de teste o estoque ficou negativo (docs/adr/0002-x.md:5)",
                  "no-restricted-syntax em eslint.config.mjs:12", "No checkout, em src/a.py:3",
                  "Não é em a/b.py, é em src/c.py:4", "Nao use float: docs/adr/0001-money.md:3"):
            self.assertFalse(is_none(t), t)


class PanelPrevails(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)
        self.bank = generate(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def test_panel_pass_overrides_mechanical_heuristic(self):
        why = [p for p in self.bank["probes"] if p["type"] == "why"][0]
        a = why["agent"]
        ps = [p for p in self.bank["probes"] if p["agent"] == a]
        write_json(self.root, sp_path(self.root, "probes", "exams", "%s.baseline.json5" % a),
                   [{"id": p["id"], "answer": "não sei"} for p in ps])
        baseline_filter(self.root, a)
        ans = [perfect(p) for p in ps if p["id"] != why["id"]]
        # resposta certa que começa por "Na ..." e cita fonte sem o termo-chave na janela
        ans.append({"id": why["id"], "answer": "Na prática, porque float perde precisão (README.md:1)",
                    "evidence": ["README.md:1"]})
        write_json(self.root, sp_path(self.root, "probes", "exams", "%s.answers.json5" % a), ans)
        write_json(self.root, sp_path(self.root, "probes", "panel", "%s.json5" % a),
                   {why["id"]: {"verdict": "PASS", "probe_sha256": probe_sha(why)}})
        cs(self.root, "probes", "check", a)
        rep = read_json(sp_path(self.root, "probes", "reports", "%s.json5" % a))
        row = [r for r in rep["probes"] if r["id"] == why["id"]][0]
        self.assertTrue(row["pass"], row["reason"])
        self.assertIn("painel=PASS", row["reason"])


class FinalFastAndPerAgent(unittest.TestCase):
    BAD = "dev-billing"

    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)
        bank = generate(self.root, seed="f1")
        self.agents = sorted(bank["agents"])
        for a in self.agents:
            ps = [p for p in bank["probes"] if p["agent"] == a]
            write_json(self.root, sp_path(self.root, "probes", "exams", "%s.baseline.json5" % a),
                       [{"id": p["id"], "answer": "não sei"} for p in ps])
            baseline_filter(self.root, a)
            items = [{"id": p["id"], "answer": "não sei", "evidence": ["grep -rn x src"]} for p in ps] \
                if a == self.BAD else [perfect(p) for p in ps]
            write_json(self.root, sp_path(self.root, "probes", "exams", "%s.answers.json5" % a), items)

    def tearDown(self):
        synth.cleanup(self.root)

    def skip_validate4(self):
        from cslib import json5io
        p = sp_path(self.root, "run.json5")
        json5io.dump({"schema_version": 1, "stages": {"validate": {"status": "in_progress", "substages": {
            "validate.4": {"status": "skipped", "reason": "--fast", "at": "2026-10-03T00:00:00Z"}}}}},
            p, "run de teste", target=self.root)

    def test_refining_agent_needs_refine_without_fast(self):
        code, out, err = cs(self.root, "probes", "check", "--all", "--final", "--allow-non-specialist",
                            "--reason", "x")
        self.assertEqual(code, 1, out + err)
        self.assertIn("refino pendente", err)

    def test_fast_allows_non_specialist_and_records_it(self):
        self.skip_validate4()
        code, out, err = cs(self.root, "probes", "check", "--all", "--final", "--allow-non-specialist",
                            "--reason", "--fast: sem refino")
        self.assertEqual(code, 0, out + err)
        agg = read_json(sp_path(self.root, "probes", "report.json5"))
        self.assertEqual(agg["agents"][self.BAD]["status"], "nao-especialista")
        self.assertEqual(agg["final"]["non_specialist"], [self.BAD])

    def test_per_agent_allow(self):
        code, _, err = cs(self.root, "probes", "check", self.BAD, "--allow-non-specialist", "--reason", "x")
        self.assertEqual(code, 2, err)
        self.assertIn("refino", err)
        self.skip_validate4()
        code, out, err = cs(self.root, "probes", "check", self.BAD, "--allow-non-specialist")
        self.assertEqual(code, 2)
        self.assertIn("--reason", err)
        code, out, err = cs(self.root, "probes", "check", self.BAD, "--allow-non-specialist", "--reason",
                            "--fast: ops sem sonda discriminante")
        self.assertEqual(code, 0, out + err)
        self.assertIn("nao-especialista", out)
        code, out, err = cs(self.root, "probes", "check", "--all", "--final")
        self.assertEqual(code, 0, out + err)
        agg = read_json(sp_path(self.root, "probes", "report.json5"))
        self.assertEqual(agg["agents"][self.BAD]["status"], "nao-especialista")
        self.assertEqual(agg["agents"][self.BAD]["allowed"]["reason"], "--fast: ops sem sonda discriminante")


class ClosedThenGuided(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)
        self.bank = generate(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def test_check_after_closed_does_not_crash(self):
        a, b = "dev-billing", "dev-orders"
        for x in (a, b):
            ps = [p for p in self.bank["probes"] if p["agent"] == x]
            write_json(self.root, sp_path(self.root, "probes", "exams", "%s.closed.json5" % x),
                       [{"id": p["id"], "answer": "não sei"} for p in ps])
            self.assertEqual(cs(self.root, "probes", "check", x, "--closed")[0], 0)
        ps = [p for p in self.bank["probes"] if p["agent"] == a]
        write_json(self.root, sp_path(self.root, "probes", "exams", "%s.baseline.json5" % a),
                   [{"id": p["id"], "answer": "não sei"} for p in ps])
        baseline_filter(self.root, a)
        write_json(self.root, sp_path(self.root, "probes", "exams", "%s.answers.json5" % a), [perfect(p) for p in ps])
        code, out, err = cs(self.root, "probes", "check", a)
        self.assertNotIn("KeyError", err)
        self.assertEqual(code, 0, out + err)
        agg = read_json(sp_path(self.root, "probes", "report.json5"))
        self.assertEqual(agg["agents"][a]["decision"], "PASS")
        self.assertIn("closed_mode", agg["agents"][b])
        self.assertEqual(agg["g4"], "FAIL", "agente sem exame guiado não deixa o G4 agregado verde")


class ProhibitionRefs(unittest.TestCase):
    def test_prohibited_symbol_is_not_a_reference(self):
        got = refs.extract("Nunca use `pickle.load`, `yaml.load` nem `eval()` em src/; use `Money.percent`.")
        kinds = {v: k for k, v, _, _ in got}
        self.assertEqual(kinds["pickle.load"], "forbidden")
        self.assertEqual(kinds["yaml.load"], "forbidden")
        self.assertEqual(kinds["eval()"], "forbidden")
        self.assertEqual(kinds["Money.percent"], "symbol")
        self.assertEqual(extract_refs("never call `os.system` or `subprocess.call`"), [])
        # negação que NÃO é proibição do token: o comando continua sendo afirmação verificável
        self.assertEqual(extract_refs("nunca entregue sem `make test`"), [("command", "make test", None)])

    def test_existence_does_not_flag_prohibition(self):
        from probes.existence import existence_report
        root = synth.make_repo()
        try:
            derive(root)
            team = read_json(sp_path(root, "team.json5"))
            for ag in team["agents"]:
                if ag["name"] == "security":
                    ag["card"] = {"description": "gate de segurança", "rules": [
                        {"text": "Nunca use `pickle.load` nem `yaml.load` para dados externos", "why": "RCE"}]}
            rep = existence_report(root, team=team)
            self.assertEqual(rep["agents"]["security"]["missing"], [])
        finally:
            synth.cleanup(root)


if __name__ == "__main__":
    unittest.main()
