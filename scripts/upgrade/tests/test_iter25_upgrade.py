"""iter25 (0.13.1): a ação item-status do upgrade e a entrada do catálogo."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(os.path.dirname(HERE))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from upgrade import core  # noqa: E402


class TestItemStatusAcao(unittest.TestCase):
    def test_item_status_esta_no_order_depois_do_state_format(self):
        o = core.ORDER
        self.assertIn("item-status", o)
        self.assertLess(o.index("state-format"), o.index("item-status"))
        self.assertLess(o.index("item-status"), o.index("emit"))

    def test_describe_menciona_o_comando_do_motor(self):
        txt = core.describe({"kind": "item-status"})
        self.assertIn("cs-state migrate item-status", txt)

    def test_sem_arvore_o_plano_nao_quebra(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            L = core._plan_item_status({}, d, ["item-status"])
            self.assertTrue(L and L[0].startswith("item-status:"))


class TestPlanoForma(unittest.TestCase):
    def test_item_status_so_contagem_sem_ids(self):
        import tempfile
        from unittest import mock
        out = "item-status (dry-run): 2 item(ns) a regravar, 0 ja em dia\n  SPR-001/01 → TODO\n  EP-01 → DONE\n"
        with tempfile.TemporaryDirectory() as d:
            sd = os.path.join(d, core.paths.SPECIALISTS_DIRNAME)
            os.makedirs(sd)
            open(os.path.join(sd, "events.jsonl"), "w").close()
            with mock.patch.object(core, "_item_status_cmd", return_value=(0, out, "")):
                L = core._plan_item_status({}, d, ["item-status"])
        self.assertEqual(len(L), 1)
        self.assertIn("2 item(ns)", L[0])
        self.assertNotIn("SPR-001/01", "\n".join(L))

    def test_presos_antes_da_regravacao(self):
        import inspect
        src = inspect.getsource(core.render_plan)
        self.assertLess(src.index("render_stuck"), src.index("muda dentro de"))


if __name__ == "__main__":
    unittest.main()
