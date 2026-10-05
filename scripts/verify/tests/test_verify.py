"""cs.py verify (G1–G16 → acceptance.json5) e cs.py approve [--check]."""
import os
import subprocess
import unittest

from helpers import cs, synth, write

from cslib import json5io
from cslib.paths import STATE_DIR
from team.derive import derive
from verify import gates as G


def fake(passed_ids):
    def fn(target, control):
        return [G.gate(g, n, g in passed_ids, "fake", "x") for g, n in G.GATES if g != "G7"]
    return fn


class DecisionTest(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()

    def tearDown(self):
        synth.cleanup(self.root)

    def acc(self):
        return json5io.load(os.path.join(self.root, STATE_DIR, "acceptance.json5"))

    def test_omitted_gate_is_not_measured_and_no_go(self):
        doc = G.verify(self.root, gates_fn=fake({g for g, _ in G.GATES}))
        ids = [g["id"] for g in doc["gates"]]
        self.assertEqual(ids, [g for g, _ in G.GATES])
        g7 = [g for g in doc["gates"] if g["id"] == "G7"][0]
        self.assertEqual((g7["passed"], g7["evidence"]), (False, "não medido"))
        self.assertEqual(self.acc()["decision"], "NO-GO")

    def test_all_pass_is_go(self):
        def allpass(t, c):
            return [G.gate(g, n, True, "ok", "x") for g, n in G.GATES]
        self.assertEqual(G.verify(self.root, gates_fn=allpass)["decision"], "GO")

    def test_g5_and_g16_measures(self):
        self.assertTrue(G.g5(self.root, "G5")["passed"])  # fato ops.test.unittest verified do synth
        write(self.root, ".swarm/facts/operations.json5",
              '{commands: [{cmd: "make test", kind: "test", status: "declared"}], facts: []}')
        self.assertFalse(G.g5(self.root, "G5")["passed"])
        write(self.root, ".swarm/facts/operations.json5",
              '{commands: [{cmd: "python3 -m unittest", kind: "test", status: "verified", exit: 0}], facts: []}')
        self.assertTrue(G.g5(self.root, "G5")["passed"])
        os.remove(os.path.join(self.root, STATE_DIR, "facts", "operations.json5"))
        g = G.g5(self.root, "G5")
        self.assertFalse(g["passed"])
        self.assertIn("não medido", g["evidence"])
        g16 = G.g16(self.root, "G16")
        self.assertFalse(g16["passed"])
        self.assertIn("run.json5 ausente", g16["evidence"])

    def test_approve_flow(self):
        self.assertEqual(cs(self.root, "approve", "--check")[0], 1)
        self.assertEqual(cs(self.root, "approve", "--by", "f", "--decision", "GO")[0], 2)  # sem acceptance
        G.verify(self.root, gates_fn=fake(set()))
        self.assertEqual(cs(self.root, "approve", "--by", "Ana", "--decision", "GO")[0], 0)
        code, _, err = cs(self.root, "approve", "--check")
        self.assertEqual(code, 1)
        self.assertIn("NO-GO", err)

        def allpass(t, c):
            return [G.gate(g, n, True, "ok", "x") for g, n in G.GATES]
        G.verify(self.root, gates_fn=allpass)
        code, _, err = cs(self.root, "approve", "--check")
        self.assertEqual(code, 1)
        self.assertIn("mudou depois", err)
        self.assertEqual(cs(self.root, "approve", "--by", "Ana", "--decision", "NO-GO", "--note", "espera")[0], 0)
        self.assertEqual(cs(self.root, "approve", "--check")[0], 1)
        self.assertEqual(cs(self.root, "approve", "--by", "Ana", "--decision", "GO", "--note", "ok")[0], 0)
        self.assertEqual(cs(self.root, "approve", "--check")[0], 0)
        self.assertEqual(cs(self.root, "approve")[0], 2)


class RealRunTest(unittest.TestCase):
    """Uma execução real (todas as suítes da skill rodam): repo sem harness/emissão → NO-GO, 16 gates."""

    def setUp(self):
        self.root = synth.make_repo()
        subprocess.run(["git", "-C", self.root, "init", "-q"], check=True)
        derive(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def test_real_verify_no_go(self):
        code, out, err = cs(self.root, "verify")
        self.assertEqual(code, 1, out + err)
        doc = json5io.load(os.path.join(self.root, STATE_DIR, "acceptance.json5"))
        self.assertEqual([g["id"] for g in doc["gates"]], [g for g, _ in G.GATES])
        by = {g["id"]: g for g in doc["gates"]}
        self.assertEqual(doc["decision"], "NO-GO")
        self.assertFalse(by["G3"]["passed"])
        self.assertNotIn("não medido", by["G3"]["evidence"])  # controle default: generic-cards
        self.assertFalse(by["G3"]["passed"])
        self.assertFalse(by["G6"]["passed"])  # harness não instalado
        for gid in ("G9", "G10", "G12", "G14", "G15"):  # suítes do motor da skill
            self.assertTrue(by[gid]["passed"], by[gid])
        for g in doc["gates"]:
            self.assertTrue(g["command"])


if __name__ == "__main__":
    unittest.main()
