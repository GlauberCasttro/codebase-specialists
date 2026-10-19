"""iter26 (CA-08, B-49): o verify não culpa a task pelo caderno que o próprio harness regravou (bloco == render do
cs-mem); bloco adulterado, outro arquivo reservado e texto livre alheio continuam acusados."""
import os
import unittest

import fixture
import cmds
import mem


class Ctx:
    def __init__(self, root):
        self.root = root


class NotebookHarness(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(with_state=False)
        self.rel = ".claude/agent-memory/dev-web/MEMORY.md"
        self.path = os.path.join(self.root, self.rel)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.blk = mem.render_notebook(self.root, "dev-web")
        self.write(self.blk + "\n")
        fixture.git(self.root, "add", "-f", self.rel)
        fixture.git(self.root, "commit", "-q", "-m", "caderno da Ana")

    def tearDown(self):
        fixture.rm(self.root)

    def write(self, txt):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(txt)

    def ok(self, agent):
        return cmds.notebook_harness_write_ok(Ctx(self.root), {"agent": agent}, self.rel)

    def test_bloco_igual_ao_render_e_aceito(self):
        self.assertTrue(self.ok("dev-billing"))
        self.assertTrue(self.ok("dev-web"))

    def test_bloco_adulterado_e_acusado(self):
        self.write("linha forjada da Ana\n" + self.blk + "\n")
        self.assertFalse(self.ok("dev-web"))

    def test_texto_livre_de_caderno_alheio_e_acusado_mas_do_dono_passa(self):
        self.write(self.blk + "\nnota livre da Ana\n")
        self.assertFalse(self.ok("dev-billing"))
        self.assertTrue(self.ok("dev-web"))

    def test_nao_caderno_nao_e_isento(self):
        self.assertFalse(cmds.notebook_harness_write_ok(Ctx(self.root), {"agent": "x"}, ".claude/orchestrator.md"))


if __name__ == "__main__":
    unittest.main()
