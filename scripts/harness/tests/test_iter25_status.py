"""iter25 (0.13.1): `status` canônico (en) gravado no arquivo do item, conferido no validate; regravação por comando."""
import json
import os
import re
import unittest

import fixture
import hcore
import tree
from test_iter23_arvore import cs, cs_ok, new_id, us_args


def raw(p):
    with open(p, "rb") as f:
        return f.read()


def file_of(root, iid):
    it = hcore.load_board(root)["tree"][iid]
    p = os.path.join(tree.tree_root(root), it["path"])
    with open(p, encoding="utf-8") as f:
        return p, json.loads(f.read())


class StatusNoItem(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(with_state=False)
        cs_ok(self.root, "init")
        self.spr = new_id(self.root, "sprint", "--meta", "meta da Ana")
        cs_ok(self.root, "start", self.spr)
        self.t = new_id(self.root, *us_args("us a", "src/billing/total.py", "--sprint", self.spr))
        self.b = new_id(self.root, *us_args("us b", "src/billing/tax.py", "--backlog"))

    def tearDown(self):
        fixture.rm(self.root)

    def test_gravado_canonico_e_exibicao_pt(self):
        self.assertEqual(file_of(self.root, self.t)[1]["status"], "TODO")
        self.assertEqual(file_of(self.root, self.b)[1]["status"], "BACKLOG")
        self.assertEqual(file_of(self.root, self.spr)[1]["status"], "ACTIVE")
        tv = tree.load_view(self.root)
        self.assertEqual(tree.status_of(tv, tv.items[self.t]), "a fazer")
        self.assertEqual(tree.status_code(tv, tv.items[self.t]), "TODO")
        self.assertNotIn("status", hcore.load_board(self.root)["tree"][self.t])

    def test_drop_grava_dropped(self):
        cs_ok(self.root, "drop", self.t, "--reason", "a Ana desistiu")
        self.assertEqual(file_of(self.root, self.t)[1]["status"], "DROPPED")

    def test_validate_acusa_valor_errado_e_fora_do_vocabulario(self):
        cs_ok(self.root, "validate", "--strict")
        p, _ = file_of(self.root, self.t)
        with open(p, encoding="utf-8") as f:
            txt = f.read()
        for bad in ("DONE", "a fazer"):
            with open(p, "w", encoding="utf-8") as f:
                f.write(re.sub(r'("status": )"[^"]*"', lambda m: m.group(1) + json.dumps(bad), txt))
            code, out, err = cs(self.root, "validate", "--strict")
            self.assertNotEqual(code, 0)
            self.assertIn("TODO esperado", out + err)
            self.assertIn(self.t, out + err)

    def test_migrate_item_status_regrava_sem_evento(self):
        p, _ = file_of(self.root, self.t)
        with open(p, encoding="utf-8") as f:
            txt = f.read()
        with open(p, "w", encoding="utf-8") as f:
            f.write(re.sub(r'\n\s*"status": "[^"]*",', "", txt))
        self.assertNotIn("status", file_of(self.root, self.t)[1])
        ev = hcore.tree_paths(self.root)["events"]
        before = raw(ev)
        out = cs_ok(self.root, "migrate", "item-status", "--dry-run")
        self.assertIn(self.t, out)
        self.assertNotIn("status", file_of(self.root, self.t)[1])
        cs_ok(self.root, "migrate", "item-status")
        self.assertEqual(file_of(self.root, self.t)[1]["status"], "TODO")
        self.assertEqual(raw(ev), before)
        self.assertIn("0 item(ns) a regravar", cs_ok(self.root, "migrate", "item-status"))
        cs_ok(self.root, "validate", "--strict")

    def _strip_status(self, iid):
        p, _ = file_of(self.root, iid)
        with open(p, encoding="utf-8") as f:
            txt = f.read()
        with open(p, "w", encoding="utf-8") as f:
            f.write(re.sub(r'\n\s*"status": "[^"]*",', "", txt))
        self.assertNotIn("status", file_of(self.root, iid)[1])

    def test_validate_acusa_status_ausente_em_alvo_migrado(self):
        self._strip_status(self.t)
        code, out, err = cs(self.root, "validate", "--strict")
        self.assertNotEqual(code, 0)
        self.assertIn("status ausente", out + err)
        self.assertIn(self.t, out + err)
        self.assertIn("TODO esperado", out + err)

    def test_validate_ok_em_alvo_nao_migrado(self):
        for iid in hcore.load_board(self.root)["tree"]:
            self._strip_status(iid)
        cs_ok(self.root, "validate", "--strict")

    def test_commit_em_alvo_nao_migrado_completa_a_migracao(self):
        ids = list(hcore.load_board(self.root)["tree"])
        for iid in ids:
            self._strip_status(iid)
        ev = hcore.tree_paths(self.root)["events"]
        n_before = raw(ev).count(b"\n")
        cs_ok(self.root, "drop", self.b, "--reason", "a Ana desistiu")
        self.assertEqual(raw(ev).count(b"\n"), n_before + 1)  # só o evento do drop, nenhum de migração
        cs_ok(self.root, "validate", "--strict")
        for iid in ids:
            self.assertIn("status", file_of(self.root, iid)[1], iid)
        self.assertEqual(file_of(self.root, self.spr)[1]["status"], "ACTIVE")

    def test_status_codes_falhando_e_reportado(self):
        orig = tree.status_codes

        def boom(root, board):
            raise RuntimeError("falha simulada da Ana")
        tree.status_codes = boom
        try:
            errs = tree.validate(self.root)
        finally:
            tree.status_codes = orig
        self.assertTrue(any("status não verificável" in e and "falha simulada da Ana" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
