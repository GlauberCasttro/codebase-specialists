"""Iteração 4 — `panel record` não deixa um revisor gravar (ou sobrescrever) as objeções de OUTRO
(go-polyglot, iteração 3: um revisor regravou 5 arquivos de outros revisores e o registro aceitou)."""
import json
import unittest

from helpers import cs, synth, write
from test_panel import EMPTY, basic_card

from cslib import json5io
from team._shared_tmp.common import read_json, sp_path, write_json
from team.derive import derive
from team.maps import build_maps


class RecordOwnFileOnly(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)
        build_maps(self.root)
        t = read_json(sp_path(self.root, "team.json5"))
        for a in t["agents"]:
            a["card"] = basic_card(a["name"])
        write_json(self.root, sp_path(self.root, "team.json5"), t)
        self.assertEqual(cs(self.root, "panel", "plan")[0], 0)
        pl = json5io.load(sp_path(self.root, "panel", "plan.json5"))
        self.revs = [r["name"] for r in pl["agents"]["dev-billing"]["reviewers"]]

    def tearDown(self):
        synth.cleanup(self.root)

    def rec(self, rel, obj, reviewer):
        write(self.root, rel, json.dumps(obj))
        return cs(self.root, "panel", "record", "dev-billing", "--reviewer", reviewer, "--file", rel)

    def test_reviewer_field_must_match(self):
        a, b = self.revs[0], self.revs[1]
        for key in ("revisor", "reviewer"):
            code, out, err = self.rec(".swarm/tmp/panel/x.json5", dict(EMPTY, **{key: b}), a)
            self.assertEqual(code, 2, "%s: %s" % (key, out + err))
            self.assertIn(b, err)
        self.assertEqual(self.rec(".swarm/tmp/panel/x.json5", dict(EMPTY, reviewer=a), a)[0], 0)

    def test_file_named_for_another_reviewer_refused(self):
        a, b = self.revs[0], self.revs[1]
        code, out, err = self.rec(".swarm/tmp/panel/dev-billing.%s.json5" % b, EMPTY, a)
        self.assertEqual(code, 2, out + err)
        self.assertIn("dev-billing.%s.json5" % b, err)
        self.assertEqual(self.rec(".swarm/tmp/panel/dev-billing.%s.json5" % a, EMPTY, a)[0], 0)
        # arquivo de outro AGENTE também não
        self.assertEqual(self.rec(".swarm/tmp/panel/dev-orders.%s.json5" % a, EMPTY, a)[0], 2)


if __name__ == "__main__":
    unittest.main()
