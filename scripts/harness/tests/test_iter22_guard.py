"""iter22 (0.12.1): `cs-state show` (leitura) passa pelo hook pre-bash; varredura argparse x guard."""
import json
import os
import re
import subprocess
import sys
import unittest

import fixture
from fixture import A
import cmds
import guard

GUARD = os.path.join(fixture.ENGINE, "guard.py")
STATE = os.path.join(fixture.ENGINE, "state.py")
SUB = {"agent_id": "ag-1", "agent_type": "dev-billing"}
# subcomandos com regra explicita no guard (fora de STATE_SUB): ato humano, so principal ou so subagente
EXPLICIT = {"legacy-ack", "waive-verify", "dispatch", "submit", "review", "abstain"}


def hook_bash(root, cmd, actor=None):
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": root}
    payload.update(actor or {})
    e = dict(os.environ, CLAUDE_PROJECT_DIR=root)
    e.pop("CS_GUARD_OFF", None)
    p = subprocess.run([sys.executable, GUARD, "pre-bash"], input=json.dumps(payload).encode(), env=e,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    return p.returncode, p.stdout.decode(), p.stderr.decode()


class TestShowPeloHook(unittest.TestCase):
    def setUp(self):
        self.root = fixture.make_repo(no_rules=True)
        fixture.process(self.root, "pequena")
        cmds.add_task(self.root, A, fixture.task_spec(), ready=True)

    def tearDown(self):
        fixture.rm(self.root)

    def test_principal_show_liberado(self):
        code, out, err = hook_bash(self.root, ".swarm/bin/cs-state show T-1")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("desconhecido", out + err)

    def test_subagente_show_liberado_e_mutacao_barrada(self):
        code, out, err = hook_bash(self.root, ".swarm/bin/cs-state show T-1", SUB)
        self.assertEqual(code, 0, out + err)
        for c in ("close T-1 --summary x", "start T-1", "new task --tipo FIX --avulsa --title x"):
            code, out, err = hook_bash(self.root, ".swarm/bin/cs-state " + c, SUB)
            self.assertEqual(code, 2, c + out + err)


class TestVarreduraArgparse(unittest.TestCase):
    def test_todo_subcomando_tem_regra(self):
        p = subprocess.run([sys.executable, STATE, "--help"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        m = re.search(r"\{([a-z0-9_,-]+)\}", p.stdout.decode())
        self.assertTrue(m, "state.py --help sem lista de subcomandos")
        subs = set(m.group(1).split(","))
        coberto = guard.STATE_SUB["main"] | guard.STATE_SUB["any"] | EXPLICIT
        self.assertEqual(sorted(subs - coberto), [], "subcomando do argparse sem regra no guard")
        self.assertIn("show", guard.STATE_SUB["main"])
        self.assertIn("show", guard.STATE_SUB["any"])


if __name__ == "__main__":
    unittest.main()
