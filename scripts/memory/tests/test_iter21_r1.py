"""iter21 rodada 1, D-1-01: `cs-mem search` sem --agent herda o agente da delegação ativa (rastro B-24);
`consultei:` só vale com busca do PRÓPRIO agente e `consultei: nada` exige motivo. Pessoa = "Ana"."""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "harness", "tests"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "harness", "engine"))
import fixture  # noqa: E402
import mem  # noqa: E402

MEM = os.path.join(os.path.dirname(HERE), "mem.py")
AG = "dev-billing"


def trail(root):
    return mem.read_jsonl(mem.search_trail_path(root))


def search(root, *extra):
    p = subprocess.run([sys.executable, MEM, "--root", root, "search", "calagem"] + list(extra),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return p.returncode, p.stdout, p.stderr


class TestD101(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo()

    def tearDown(self):
        fixture.rm(self.root)

    def test_a_search_sem_agent_com_delegacao_ativa_grava_agente(self):
        fixture.dispatched(self.root)
        code, out, err = search(self.root)
        self.assertEqual(code, 0, err)
        row = trail(self.root)[-1]
        self.assertEqual(row["agent"], AG)
        self.assertIs(row["agent_inferred"], True)
        for k in ("at", "query", "kinds", "paths", "hits", "ids"):
            self.assertIn(k, row)

    def test_d_sem_delegacao_agent_null_sem_erro(self):
        code, out, err = search(self.root)
        self.assertEqual(code, 0, err)
        row = trail(self.root)[-1]
        self.assertIsNone(row["agent"])
        self.assertIs(row["agent_inferred"], False)

    def test_agent_explicito_nao_e_inferido(self):
        fixture.dispatched(self.root)
        search(self.root, "--agent", AG)
        row = trail(self.root)[-1]
        self.assertEqual(row["agent"], AG)
        self.assertIs(row["agent_inferred"], False)


if __name__ == "__main__":
    unittest.main()
