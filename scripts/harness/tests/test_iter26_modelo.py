"""iter26 (0.14.0): modelo canônico — sem campos mortos, kind en, repro_steps, flags en com alias pt depreciado,
listas por tentativa e orientação do `close`. Pela CLI real (state.py) num repositório de fixture em modo árvore."""
import json
import os
import unittest

import fixture
import hcore
import tree
from test_iter23_arvore import AG, C1, VERIFY, cs, cs_ok, item, new_id, us_args

STEPS = "1. Ana abre o carrinho 2. aplica o cupom 3. o total fica negativo"
DEAD = ("dod", "handoff", "knowledge_context")


def file_json(root, iid):
    it = hcore.load_board(root)["tree"][iid]
    with open(os.path.join(tree.tree_root(root), it["path"]), encoding="utf-8") as f:
        return json.loads(f.read())


class Base(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(with_state=False)
        cs_ok(self.root, "init")

    def tearDown(self):
        fixture.rm(self.root)


class CamposMortos(Base):
    def test_task_iniciada_sem_campos_mortos(self):
        spr = new_id(self.root, "sprint", "--meta", "meta da Ana")
        cs_ok(self.root, "start", spr)
        t = new_id(self.root, *us_args("us a", "src/billing/total.py", "--sprint", spr))
        cs_ok(self.root, "start", t)
        m2 = hcore.load_board(self.root)["tasks"][0]
        self.assertEqual([k for k in DEAD if k in m2], [])
        self.assertNotIn("context", m2["briefing"])
        self.assertNotIn("in", m2["briefing"]["scope"])
        self.assertIn("out", m2["briefing"]["scope"])


class KindEpic(Base):
    def test_new_epic_e_alias_gravam_epic_e_aliase_avisa(self):
        e1 = new_id(self.root, "epic", "--title", "Fiscal da Ana", "--objetivo", "nota")
        code, out, err = cs(self.root, "new", "epico", "--title", "Outro da Ana", "--objetivo", "x")
        self.assertEqual(code, 0, out + err)
        self.assertIn("depreciado", err)
        e2 = out.split()[1]
        for e in (e1, e2):
            self.assertEqual(file_json(self.root, e)["kind"], "epic")
            self.assertEqual(item(self.root, e)["kind"], "epico")      # em memória segue o histórico

    def test_arquivo_antigo_kind_epico_e_lido_e_valida(self):
        e = new_id(self.root, "epic", "--title", "Fiscal da Ana", "--objetivo", "nota")
        it = hcore.load_board(self.root)["tree"][e]
        p = os.path.join(tree.tree_root(self.root), it["path"])
        with open(p, encoding="utf-8") as f:
            txt = f.read()
        with open(p, "w", encoding="utf-8") as f:
            f.write(txt.replace('"kind": "epic"', '"kind": "epico"'))
        self.assertEqual(hcore.item_to_pt({"kind": "epico"})["kind"], "epico")
        self.assertEqual(hcore.item_to_pt({"kind": "epic"})["kind"], "epico")
        cs_ok(self.root, "validate", "--strict")
        cs_ok(self.root, "show", e)


class ReproSteps(Base):
    def bug(self, *extra):
        spr = new_id(self.root, "sprint", "--meta", "meta da Ana")
        return new_id(self.root, "task", "--type", "BUG", "--agent", AG, "--title", "bug da Ana", "--allowed-path",
                      "src/billing/bug.py", "--verify-cmd", VERIFY, "--sprint", spr, *extra)

    def test_passos_e_teste_separados_no_disco_e_no_show(self):
        b = self.bug("--repro", STEPS, "--failing-test", "tests.test_billing")
        d = file_json(self.root, b)
        self.assertEqual((d["repro_steps"], d["failing_test"]), (STEPS, "tests.test_billing"))
        out = cs_ok(self.root, "show", b)
        self.assertIn(STEPS, out)
        self.assertIn("tests.test_billing", out)

    def test_bug_antigo_com_passos_em_failing_test_mostra_passos(self):
        b = self.bug("--reproducao", STEPS)          # nome antigo: grava em failing_test (como a 0.13.1)
        self.assertEqual(file_json(self.root, b)["failing_test"], STEPS)
        self.assertIn("passos de reprodução: " + STEPS, cs_ok(self.root, "show", b))
        cs_ok(self.root, "validate", "--strict")


class FlagsEn(Base):
    def test_en_vale_e_pt_avisa_e_en_vence(self):
        spr = new_id(self.root, "sprint", "--meta", "meta da Ana")
        base = ["task", "--agent", AG, "--title", "t", "--allowed-path", "src/billing/p.py", "--verify-cmd", VERIFY,
                "--criterio", C1, "--sprint", spr]
        en = new_id(self.root, *(base + ["--type", "US", "--as-a", "cliente", "--i-want", "cupom", "--so-that", "pagar"]))
        code, out, err = cs(self.root, "new", *(base + ["--tipo", "US", "--como", "cliente", "--quero", "cupom",
                                                         "--para", "pagar"]))
        self.assertEqual(code, 0, out + err)
        self.assertIn("depreciada", err)
        pt = out.split()[1]
        a, b = file_json(self.root, en), file_json(self.root, pt)
        for k in ("type", "as_a", "i_want", "so_that"):
            self.assertEqual(a[k], b[k])
        code, out, err = cs(self.root, "new", *(base + ["--type", "US", "--tipo", "BUG", "--as-a", "x", "--i-want", "y",
                                                         "--so-that", "z"]))
        self.assertEqual(code, 0, out + err)
        self.assertIn("ignorada", err)
        self.assertEqual(file_json(self.root, out.split()[1])["type"], "US")

    def test_help_so_en(self):
        for args in (["new", "task", "--help"], ["new", "--help"]):
            code, out, err = cs(self.root, *args)
            self.assertEqual(code, 0)
            for w in ("--tipo", "--como", "--quero", "--motivo", "epico"):
                self.assertNotIn(w, out)


class CloseOrienta(Base):
    def test_close_de_sprint_manda_git_add_swarm(self):
        spr = new_id(self.root, "sprint", "--meta", "meta da Ana")
        cs_ok(self.root, "start", spr)
        t = new_id(self.root, *us_args("us a", "src/billing/total.py", "--sprint", spr))
        cs_ok(self.root, "drop", t, "--reason", "a Ana desistiu")
        out = cs_ok(self.root, "close", spr, "--summary", "encerrada")
        self.assertIn("git add .swarm", out)


if __name__ == "__main__":
    unittest.main()
