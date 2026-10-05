"""probes baseline-filter --check, probes check --all [--final] (regra de 2 refinos → nao-especialista)."""
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "team", "tests"))
sys.path.insert(0, HERE)
import synth  # noqa: E402

from team._shared_tmp.common import read_json, sp_path, write_json  # noqa: E402
from team.derive import derive  # noqa: E402
from probes.exam import baseline_filter  # noqa: E402
from probes.generate import generate, load_bank  # noqa: E402
from test_probes import perfect  # noqa: E402

CS = os.path.join(synth.SCRIPTS, "cs.py")


def cs(root, *args):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    p = subprocess.run([sys.executable, CS, "--target", root] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, env=env)
    return p.returncode, p.stdout.decode(), p.stderr.decode()


class FinalTest(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()
        derive(self.root)

    def tearDown(self):
        synth.cleanup(self.root)

    def exams(self, seed="s1", bad=None, baseline=True, answers=True):
        bank = generate(self.root, seed=seed)
        agents = sorted(bank["agents"])
        for a in agents:
            ps = [p for p in bank["probes"] if p["agent"] == a]
            if baseline:
                write_json(self.root, sp_path(self.root, "probes", "exams", "%s.baseline.json5" % a), [{"id": x["id"], "answer": "não sei"} for x in load_bank(self.root)["probes"] if x["agent"] == a])
                baseline_filter(self.root, a)
            if answers:
                items = [] if a == bad else [perfect(p) for p in ps]
                write_json(self.root, sp_path(self.root, "probes", "exams", "%s.answers.json5" % a), items)
        return agents

    def test_baseline_check(self):
        self.exams(baseline=False, answers=False)
        code, _, err = cs(self.root, "probes", "baseline-filter", "--check")
        self.assertEqual(code, 1)
        self.assertIn("sem baseline", err)
        self.exams(baseline=True, answers=False)
        self.assertEqual(cs(self.root, "probes", "baseline-filter", "--check")[0], 0)
        self.assertEqual(cs(self.root, "probes", "baseline-filter")[0], 2)

    def test_check_all(self):
        agents = self.exams(answers=False)
        code, _, err = cs(self.root, "probes", "check", "--all")
        self.assertEqual(code, 1)
        self.assertIn("reprovado", err)
        self.exams()
        code, out, err = cs(self.root, "probes", "check", "--all")
        self.assertEqual(code, 0, out + err)
        for a in agents:
            self.assertIn(a, out)
        self.assertEqual(cs(self.root, "probes", "check")[0], 2)
        self.assertEqual(cs(self.root, "probes", "check", agents[0], "--all")[0], 2)

    def test_two_refine_cycles_then_non_specialist(self):
        agents = self.exams("c1", bad="dev-billing")
        code, _, err = cs(self.root, "probes", "check", "--all", "--final")
        self.assertEqual(code, 1)
        self.assertIn("refino pendente", err)
        # retake das MESMAS sondas não abre ciclo
        cs(self.root, "probes", "check", "--all", "--final")
        cyc = read_json(sp_path(self.root, "probes", "cycles.json5"))
        self.assertEqual(len(cyc["dev-billing"]), 1)
        self.exams("c2", bad="dev-billing")
        self.assertEqual(cs(self.root, "probes", "check", "--all", "--final")[0], 1)
        self.exams("c3", bad="dev-billing")
        code, out, err = cs(self.root, "probes", "check", "--all", "--final")
        self.assertEqual(code, 1)
        self.assertIn("nao-especialista", err)
        rep = read_json(sp_path(self.root, "probes", "report.json5"))
        self.assertEqual(rep["agents"]["dev-billing"]["status"], "nao-especialista")
        self.assertEqual(rep["final"]["non_specialist"], ["dev-billing"])
        others = [a for a in agents if a != "dev-billing"]
        self.assertTrue(all(rep["agents"][a]["status"] == "especialista" for a in others))
        self.assertEqual(cs(self.root, "probes", "check", "--all", "--final", "--allow-non-specialist")[0], 2)
        self.assertEqual(cs(self.root, "probes", "check", "--all", "--final", "--allow-non-specialist",
                            "--reason", "billing sem cobertura de fatos; dito ao usuário")[0], 0)
        self.assertEqual(cs(self.root, "probes", "check", "--all", "--final")[0], 0)  # motivo registrado
        rep = read_json(sp_path(self.root, "probes", "report.json5"))
        self.assertEqual(rep["final"]["allowed"]["agents"], ["dev-billing"])

    def test_repeated_old_probes_rejected(self):
        self.exams("c1", bad="dev-billing")
        cs(self.root, "probes", "check", "--all")
        self.exams("c2", bad="dev-billing")
        cs(self.root, "probes", "check", "--all")
        self.exams("c1", bad="dev-billing")
        code, _, err = cs(self.root, "probes", "check", "--all")
        self.assertEqual(code, 2)
        self.assertIn("sondas NOVAS", err)


if __name__ == "__main__":
    unittest.main()
