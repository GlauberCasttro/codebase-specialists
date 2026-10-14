"""iter23 (0.13.0): motor da árvore — drop/amend de task não iniciada, sprint, DoR na criação, plan de story,
auto-memória do agente principal e `cs-state version`. Cada teste prova UM comportamento pela CLI real (state.py)
e pelo guard real (guard.py) num repositório de fixture em modo árvore."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import fixture
import hcore
import tree

STATE = os.path.join(fixture.ENGINE, "state.py")
GUARD = os.path.join(fixture.ENGINE, "guard.py")
VERIFY = "python3 -m unittest tests.test_billing"
C1 = "AC-1|Dado pedido Quando aplico Então desconta|tests.test_billing"
AG = "dev-billing"


def cs(root, *args):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    p = subprocess.run([sys.executable, STATE, "--root", root] + list(args), cwd=root, env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    return p.returncode, p.stdout.decode(), p.stderr.decode()


def cs_ok(root, *args):
    code, out, err = cs(root, *args)
    assert code == 0, "cs-state %s → %d: %s%s" % (" ".join(args), code, out, err)
    return out


def new_id(root, *args):
    out = cs_ok(root, "new", *args)
    return re.search(r"criado (\S+) em", out).group(1)


def task_args(tipo, title, path, *extra):
    return ["task", "--tipo", tipo, "--agent", AG, "--title", title, "--allowed-path", path, "--verify-cmd", VERIFY] \
        + list(extra)


def us_args(title, path, *extra):
    return task_args("US", title, path, "--como", "cliente", "--quero", "cupom", "--para", "pagar menos",
                     "--criterio", C1, *extra)


def item(root, iid):
    return hcore.load_board(root)["tree"][iid]


def snapshot(root):
    snap = {}
    for dp, _, fns in os.walk(os.path.join(root, ".swarm")):
        for fn in fns:
            p = os.path.join(dp, fn)
            with open(p, "rb") as f:
                snap[p] = f.read()
    return snap


class Arvore(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(with_state=False)
        cs_ok(self.root, "init")

    def tearDown(self):
        fixture.rm(self.root)

    def sprint_com_tasks(self):
        spr = new_id(self.root, "sprint", "--meta", "meta da Ana")
        cs_ok(self.root, "start", spr)
        a = new_id(self.root, *task_args("CHORE", "chore a", "src/billing/tax.py", "--motivo", "manutencao", "--sprint", spr))
        b = new_id(self.root, *us_args("us b", "src/billing/total.py", "--sprint", spr))
        return spr, a, b


class TestDrop(Arvore):
    def test_drop_task_nao_iniciada_vai_para_archive_como_dropped(self):
        _, a, _ = self.sprint_com_tasks()
        cs_ok(self.root, "drop", a, "--reason", "a Ana desistiu")
        it = item(self.root, a)
        self.assertTrue(it["path"].startswith("archive/"))
        self.assertEqual(it["closed"]["status"], "DROPPED")
        self.assertIn("a Ana desistiu", json.dumps(it))
        self.assertNotIn(a + " ", cs_ok(self.root, "board").split("fechados recentes")[0])
        self.assertEqual(cs(self.root, "validate", "--strict", "--allow-empty")[0], 0)

    def test_drop_sem_reason_recusa_e_nao_altera(self):
        _, a, _ = self.sprint_com_tasks()
        before = snapshot(self.root)
        code, out, err = cs(self.root, "drop", a)
        self.assertNotEqual(code, 0)
        self.assertIn("--reason", out + err)
        self.assertEqual(snapshot(self.root), before)

    def test_drop_task_iniciada_segue_o_fluxo_da_m2(self):
        _, _, b = self.sprint_com_tasks()
        cs_ok(self.root, "start", b)
        code, _, _ = cs(self.root, "drop", b, "--reason", "x")
        self.assertNotEqual(code, 0)
        self.assertTrue(item(self.root, b)["path"].startswith("state/"))

    def test_drop_de_sprint_vazia_nao_iniciada(self):
        spr = new_id(self.root, "sprint", "--meta", "vazia")
        cs_ok(self.root, "drop", spr, "--reason", "nao vai usar")
        it = item(self.root, spr)
        self.assertTrue(it["path"].startswith("archive/"))
        self.assertEqual(it["closed"]["status"], "DROPPED")
        self.assertEqual(cs(self.root, "validate", "--strict", "--allow-empty")[0], 0)

    def test_drop_de_sprint_com_task_aberta_recusa_listando(self):
        spr = new_id(self.root, "sprint", "--meta", "com task")
        t = new_id(self.root, *task_args("CHORE", "c", "src/billing/tax.py", "--motivo", "m", "--sprint", spr))
        code, out, err = cs(self.root, "drop", spr, "--reason", "x")
        self.assertNotEqual(code, 0)
        self.assertIn(t, out + err)

    def test_close_da_sprint_aceita_tasks_dropped_e_recusa_a_aberta(self):
        spr, a, b = self.sprint_com_tasks()
        cs_ok(self.root, "drop", a, "--reason", "fora")
        code, out, err = cs(self.root, "close", spr, "--summary", "x")
        self.assertNotEqual(code, 0)
        self.assertIn(b, out + err)
        self.assertNotIn(a + "\n", out + err)
        cs_ok(self.root, "drop", b, "--reason", "fora")
        cs_ok(self.root, "close", spr, "--summary", "encerrada")
        self.assertTrue(item(self.root, spr)["path"].startswith("archive/"))


class TestAmendDor(Arvore):
    def test_amend_campos_do_dor_em_task_nao_iniciada(self):
        spr = new_id(self.root, "sprint", "--meta", "m")
        cs_ok(self.root, "start", spr)
        ch = new_id(self.root, *task_args("CHORE", "c", "src/billing/tax.py", "--motivo", "m", "--sprint", spr))
        for field, val, key in (("motivo", "manutencao pedida", "motivo"), ("verify_cmd", VERIFY + " -q", "verify_cmd")):
            cs_ok(self.root, "amend", ch, "--field", field, "--after", val, "--reason", "DoR da Ana")
            self.assertEqual(item(self.root, ch)[key], val)
        h = item(self.root, ch)["historico"][-1]
        self.assertEqual((h["acao"], h["field"], h["reason"]), ("amend", "verify_cmd", "DoR da Ana"))

    def test_amend_historia_da_us_e_chore_recusa_como(self):
        spr = new_id(self.root, "sprint", "--meta", "m")
        us = new_id(self.root, *us_args("u", "src/billing/total.py", "--sprint", spr))
        cs_ok(self.root, "amend", us, "--field", "como", "--after", "gerente", "--reason", "r")
        self.assertEqual(item(self.root, us)["como"], "gerente")
        ch = new_id(self.root, *task_args("CHORE", "c", "src/billing/tax.py", "--motivo", "m", "--sprint", spr))
        self.assertNotEqual(cs(self.root, "amend", ch, "--field", "como", "--after", "x", "--reason", "r")[0], 0)

    def test_amend_de_task_iniciada_mantem_regras(self):
        spr = new_id(self.root, "sprint", "--meta", "m")
        cs_ok(self.root, "start", spr)
        us = new_id(self.root, *us_args("u", "src/billing/total.py", "--sprint", spr))
        cs_ok(self.root, "start", us)
        before = item(self.root, us).get("motivo")
        self.assertNotEqual(cs(self.root, "amend", us, "--field", "motivo", "--after", "x", "--reason", "r")[0], 0)
        self.assertEqual(item(self.root, us).get("motivo"), before)


class TestSprintPorEpico(Arvore):
    def test_new_segunda_sprint_aberta_no_epico_recusa_inclusive_dry_run(self):
        epc = new_id(self.root, "epico", "--title", "E", "--objetivo", "x")
        s1 = new_id(self.root, "sprint", "--meta", "a", "--epico", epc)
        before = snapshot(self.root)
        for extra in (["--dry-run"], []):
            code, out, err = cs(self.root, "new", "sprint", "--meta", "b", "--epico", epc, *extra)
            self.assertNotEqual(code, 0)
            self.assertIn(s1, out + err)
        self.assertEqual(snapshot(self.root), before)

    def test_move_de_sprint_para_epico_com_sprint_aberta_recusa(self):
        epc = new_id(self.root, "epico", "--title", "E", "--objetivo", "x")
        s1 = new_id(self.root, "sprint", "--meta", "a", "--epico", epc)
        s2 = new_id(self.root, "sprint", "--meta", "b")
        code, out, err = cs(self.root, "move", s2, "--to", epc)
        self.assertNotEqual(code, 0)
        self.assertIn(s1, out + err)

    def test_start_de_segunda_sprint_no_epico_recusa_dado_legado(self):
        # a 2ª sprint aberta no épico veio de motor antigo (o `new` novo já recusa): injeta no modelo em memória
        epc = new_id(self.root, "epico", "--title", "E", "--objetivo", "x")
        s1 = new_id(self.root, "sprint", "--meta", "a", "--epico", epc)
        s2 = new_id(self.root, "sprint", "--meta", "b")
        cs_ok(self.root, "start", epc)
        cs_ok(self.root, "start", s1)
        tv = tree.load_view(self.root)
        tv.items[s2]["epico"] = epc
        with self.assertRaises(hcore.Refused) as cm:
            tree.start(tv, s2)
        self.assertIn(s1, str(cm.exception))

    def test_sprint_em_outro_epico_cria(self):
        e1 = new_id(self.root, "epico", "--title", "Um", "--objetivo", "x")
        e2 = new_id(self.root, "epico", "--title", "Dois", "--objetivo", "y")
        new_id(self.root, "sprint", "--meta", "a", "--epico", e1)
        new_id(self.root, "sprint", "--meta", "b", "--epico", e2)


class TestDorNaCriacao(Arvore):
    CASES = [
        ("reservado", ("reservad", ".claude"), us_args("n", ".claude/agent-memory/x.md", "--backlog")),
        ("fix", ("fixes", "teste"), task_args("FIX", "f", "src/billing/tax.py", "--backlog")),
        ("chore", ("motivo",), task_args("CHORE", "c", "src/billing/tax.py", "--backlog")),
        ("bug", ("reproducao",), task_args("BUG", "b", "src/billing/tax.py", "--backlog")),
        ("us sem historia", ("como",), task_args("US", "u", "src/billing/tax.py", "--criterio", C1, "--backlog")),
        ("sem verify", ("verify",), ["task", "--tipo", "CHORE", "--agent", AG, "--title", "c", "--allowed-path",
                                     "src/billing/tax.py", "--motivo", "m", "--backlog"]),
    ]

    def test_new_task_recusa_dor_estatico_sem_criar_nada(self):
        before = snapshot(self.root)
        for dry in ([], ["--dry-run"]):
            for label, words, args in self.CASES:
                code, out, err = cs(self.root, "new", *(args + dry))
                self.assertNotEqual(code, 0, "%s %s" % (label, dry))
                for w in words:
                    self.assertIn(w, (out + err).lower(), label)
        self.assertEqual(snapshot(self.root), before)

    def test_new_task_com_campos_certos_cria_e_bug_verde_cria(self):
        new_id(self.root, *us_args("u", "src/billing/total.py", "--backlog"))
        new_id(self.root, *task_args("BUG", "b", "src/billing/tax.py", "--reproducao", "tests.test_billing", "--backlog"))


class TestValidateArvore(Arvore):
    def test_validate_strict_aceita_arvore_sem_entidade_m2(self):
        new_id(self.root, "epico", "--title", "E", "--objetivo", "x")
        new_id(self.root, "sprint", "--meta", "meta da Ana")
        new_id(self.root, "feature", "--title", "F", "--backlog", "--aceite", "false")
        code, out, err = cs(self.root, "validate", "--strict")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("estado vazio", out + err)


class TestPlanStory(Arvore):
    def story(self):
        spr = new_id(self.root, "sprint", "--meta", "s")
        cs_ok(self.root, "start", spr)
        fea = new_id(self.root, "feature", "--title", "F", "--backlog", "--aceite", "false")
        st = new_id(self.root, "story", "--tipo", "US", "--title", "S", "--feature", fea, "--agents", AG,
                    "--agents", "dev-users", "--verify-cmd", VERIFY, "--como", "a", "--quero", "b", "--para", "c",
                    "--criterio", C1)
        return spr, st

    def test_plan_story_vincula_por_referencia_e_aparece_no_board_e_next(self):
        spr, st = self.story()
        cs_ok(self.root, "plan", st, "--sprint", spr)
        self.assertEqual(item(self.root, st)["sprint"], spr)
        self.assertIn(st, item(self.root, spr)["stories"])
        self.assertIn("features", item(self.root, st)["path"])
        self.assertTrue(any(st in ln and spr in ln for ln in cs_ok(self.root, "board").splitlines()))
        self.assertIn(st, cs_ok(self.root, "next"))
        self.assertEqual(cs(self.root, "validate", "--strict", "--allow-empty")[0], 0)

    def test_close_da_sprint_cita_a_story_planejada(self):
        spr, st = self.story()
        cs_ok(self.root, "plan", st, "--sprint", spr)
        code, out, err = cs(self.root, "close", spr, "--summary", "x")
        self.assertNotEqual(code, 0)
        self.assertIn(st, out + err)

    def test_plan_de_task_na_sprint_continua(self):
        spr, _ = self.story()
        t = new_id(self.root, *us_args("t", "src/billing/total.py", "--backlog"))
        cs_ok(self.root, "plan", t, "--sprint", spr)

    def test_sprint_plan_em_arvore_aponta_o_comando_certo(self):
        code, out, err = cs(self.root, "sprint", "plan", "--goal", "g", "--budget", "10")
        self.assertNotEqual(code, 0)
        self.assertRegex(out + err, r"cs-state plan <story\|task> --sprint")


class TestVersao(Arvore):
    def _manifest(self, **kw):
        d = os.path.join(self.root, ".swarm", "harness")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "MANIFEST.json5"), "w") as f:
            f.write(json.dumps(dict({"files": {}}, **kw)))

    def _run(self, skill):
        with open(os.path.join(self.root, ".swarm", "run.json5"), "w") as f:
            f.write(json.dumps({"skill_version": skill}))

    def test_version_mostra_a_do_manifest(self):
        self._manifest(version="9.8.7")
        self._run("9.8.6")
        out = cs_ok(self.root, "version")
        self.assertIn("9.8.7", out.splitlines()[0])
        self.assertIn("divergem", out)

    def test_version_cai_para_run_json5_sem_o_campo(self):
        self._manifest()
        self._run("9.8.6")
        self.assertIn("9.8.6", cs_ok(self.root, "version").splitlines()[0])

    def test_version_sem_nenhuma_fonte_recusa(self):
        self.assertNotEqual(cs(self.root, "version")[0], 0)


class TestAutoMemoria(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()
        self.home = os.path.realpath(tempfile.mkdtemp(prefix="cs-home-"))
        slug = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(self.root))
        self.mem = os.path.join(self.home, ".claude", "projects", slug, "memory")
        os.makedirs(self.mem)
        os.makedirs(os.path.join(self.home, "fora"))

    def tearDown(self):
        fixture.rm(self.root)
        shutil.rmtree(self.home, ignore_errors=True)

    def w(self, path, actor=None):
        payload = {"tool_name": "Write", "tool_input": {"file_path": path, "content": "x\n"}, "cwd": self.root}
        payload.update(actor or {})
        env = dict(os.environ, CLAUDE_PROJECT_DIR=self.root, HOME=self.home)
        env.pop("CS_GUARD_OFF", None)
        p = subprocess.run([sys.executable, GUARD, "pre-write"], input=json.dumps(payload).encode(), env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return p.returncode

    def test_principal_escreve_so_na_propria_memoria(self):
        self.assertEqual(self.w(os.path.join(self.mem, "MEMORY.md")), 0)

    def test_subagente_outro_projeto_ponto_ponto_e_fora_continuam_recusados(self):
        sub = {"agent_id": "ag-1", "agent_type": "dev-billing"}
        outro = os.path.join(self.home, ".claude", "projects", "-outro", "memory", "x.md")
        recusados = [(os.path.join(self.mem, "x.md"), sub), (outro, None),
                     (os.path.join(self.mem, "..", "x.md"), None),
                     (os.path.join(self.mem, "..", "..", "..", "settings.json"), None),
                     (os.path.join(self.home, "fora", "y.md"), None)]
        for p, actor in recusados:
            self.assertEqual(self.w(p, actor), 2, p)

    def test_symlink_na_memoria_para_fora_continua_recusado(self):
        os.symlink(os.path.join(self.home, "fora"), os.path.join(self.mem, "atalho"))
        os.symlink(os.path.join(self.home, "fora", "alvo.md"), os.path.join(self.mem, "nota.md"))
        self.assertEqual(self.w(os.path.join(self.mem, "atalho", "x.md")), 2)
        self.assertEqual(self.w(os.path.join(self.mem, "nota.md")), 2)

    def test_memory_que_e_symlink_nao_libera(self):
        shutil.rmtree(self.mem)
        os.symlink(os.path.join(self.home, "fora"), self.mem)
        self.assertEqual(self.w(os.path.join(self.mem, "x.md")), 2)

    def test_hardlink_de_protegido_na_memoria_recusado(self):
        prot = os.path.join(self.root, ".claude", "settings.json")
        os.makedirs(os.path.dirname(prot), exist_ok=True)
        if not os.path.exists(prot):
            with open(prot, "w") as f:
                f.write("{}\n")
        with open(prot) as f:
            antes = f.read()
        link = os.path.join(self.mem, "nota.md")
        os.link(prot, link)
        self.assertEqual(self.w(link), 2)
        with open(prot) as f:
            self.assertEqual(f.read(), antes)
        comum = os.path.join(self.mem, "comum.md")
        with open(comum, "w") as f:
            f.write("Ana\n")
        self.assertEqual(self.w(comum), 0)


if __name__ == "__main__":
    unittest.main()
