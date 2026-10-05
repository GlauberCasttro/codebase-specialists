"""Regressão: `team maps` grava deps/collision em {nodes, edges} e `emit validate` (G7/G13) aceita."""
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402

from team._shared_tmp.common import read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402

CS = os.path.join(synth.SCRIPTS, "cs.py")


def cs(root, *args):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    p = subprocess.run([sys.executable, CS, "--target", root] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=env)
    return p.returncode, p.stdout.decode(), p.stderr.decode()


class MapsEmitTest(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        # o scan real (L0) grava `category`; o synth usa `class` — o emissor só lê `category`
        inv = read_json(sp_path(self.root, "facts", "inventory.json5"))
        for f in inv["files"]:
            f["category"] = f["class"]
        write_json(self.root, sp_path(self.root, "facts", "inventory.json5"), inv)
        derive(self.root)
        t = read_json(sp_path(self.root, "team.json5"))
        t["core"] = {"lines": [{"text": "Testes: `python3 -m unittest discover -s tests`",
                                "facts": ["ops.test.unittest"]}]}
        t["platforms"] = ["claude-code", "cursor", "copilot", "codex"]
        for a in t["agents"]:
            a["card"] = {"description": "Use para %s." % a["name"], "mission": "Mantém %s." % a["name"],
                         "knows": [], "refuses": [], "done_when": "`python3 -m unittest discover -s tests` sai 0",
                         "playbooks": [], "rules": [], "footguns": [], "anchors": []}
        write_json(self.root, sp_path(self.root, "team.json5"), t)

    def tearDown(self):
        synth.cleanup(self.root)

    def test_maps_then_emit_validate(self):
        code, out, err = cs(self.root, "team", "maps")
        self.assertEqual(code, 0, err)
        for name in ("deps.json5", "collision.json5"):
            d = read_json(sp_path(self.root, "knowledge", name))
            self.assertTrue(d["nodes"] and isinstance(d["edges"], list), name)
        deps = read_json(sp_path(self.root, "knowledge", "deps.json5"))
        self.assertIn("matrix", deps)
        self.assertIn({"from": "dev-orders", "to": "dev-billing", "count": 1}, deps["edges"])
        self.assertIn("do_not_parallelize", read_json(sp_path(self.root, "knowledge", "collision.json5")))
        code, out, err = cs(self.root, "emit", "--allow-outside")
        self.assertEqual(code, 0, out + err)
        code, out, err = cs(self.root, "emit", "validate")
        self.assertEqual(code, 0, out + err)
        from emit import maps
        from emit.team import load_team
        _, data = maps.build(self.root, load_team(self.root))
        self.assertEqual(maps.check_maps(self.root, data), [])  # G13 (parte do emissor)
        self.assertEqual(cs(self.root, "panel", "plan")[0], 0)


if __name__ == "__main__":
    unittest.main()
