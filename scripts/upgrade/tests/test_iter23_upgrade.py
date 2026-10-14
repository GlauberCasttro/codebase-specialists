"""iter23 (0.13.0): o relatório de itens presos do upgrade (render) e a entrada do catálogo."""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(os.path.dirname(HERE))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from upgrade import core  # noqa: E402


class TestRenderStuck(unittest.TestCase):
    def test_task_lista_drop_e_amend_junto_do_id(self):
        L = core.render_stuck([{"id": "TSK-009", "kind": "task", "tipo": "FIX", "title": "Fix da Ana",
                                "problems": ["FIX sem --fixes"]}])
        txt = "\n".join(L)
        self.assertIn("cs-state drop TSK-009", txt)
        self.assertIn("cs-state amend TSK-009", txt)
        self.assertIn("NÃO altera", txt)

    def test_sprint_so_descarta(self):
        txt = "\n".join(core.render_stuck([{"id": "SPR-003", "kind": "sprint", "title": "x", "problems": ["p"]}]))
        self.assertIn("cs-state drop SPR-003", txt)
        self.assertNotIn("amend SPR-003", txt)

    def test_alvo_inexistente_e_erro_nao_lista_vazia(self):
        r = core.stuck_items(os.path.join(HERE, "nao-existe-da-ana"))
        self.assertIsInstance(r, dict)
        self.assertIn("error", r)


def _plan(stuck=None, legacy=False):
    p = {"target": "/x", "from": "0.12.2", "to": "0.13.0", "legacy": False,
         "migrations": [{"to": "0.13.0", "why": "w"}], "actions": [], "reexam": False, "renaming": legacy,
         "layout_legacy": legacy, "inside": [], "outside": [], "backup": "b", "conflict": None}
    if stuck is not None:
        p["stuck"] = stuck
    if legacy:
        p["stuck_deferred"] = True
    return p


class TestStuckFalhaVisivel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cs-iter23-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_estado_corrompido_diz_nao_foi_possivel(self):
        d = os.path.join(self.tmp, ".swarm", "state")
        os.makedirs(d)
        for n in ("x.json", os.path.join("..", "events.jsonl")):
            with open(os.path.join(d, n), "w") as f:
                f.write("{bad\n")
        r = core.stuck_items(self.tmp)
        self.assertIsInstance(r, dict)
        txt = core.render_plan(_plan(r))
        self.assertIn("não foi possível listar itens presos", txt)
        self.assertIn("cs-state check", txt)

    def test_sem_estado_diz_explicitamente(self):
        r = core.stuck_items(self.tmp)
        self.assertIsInstance(r, dict)
        self.assertIn("absent", r)
        txt = core.render_plan(_plan(r))
        self.assertIn("itens presos: não verificados", txt)
        self.assertNotIn("não foi possível listar", txt)

    def test_render_erro(self):
        txt = core.render_plan(_plan({"error": "motor saiu 1: boom"}))
        self.assertIn("não foi possível listar itens presos: motor saiu 1: boom", txt)

    def test_nada_preso_diz_nada(self):
        txt = core.render_plan(_plan([]))
        self.assertIn("itens presos: nenhum", txt)

    def test_legado_avisa_depois_do_rename(self):
        txt = core.render_plan(_plan(legacy=True))
        self.assertIn("itens presos serão listados depois do rename", txt)

    def test_dor_que_levanta_vira_item(self):
        self.assertIn("DoR não avaliável", core._STUCK_SNIPPET)
        self.assertNotIn("probs = []", core._STUCK_SNIPPET)


if __name__ == "__main__":
    unittest.main()
