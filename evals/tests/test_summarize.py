"""summarize.py: [Q] e [S] separados por config, mean±sd, tempo/tokens do timing.json."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import summarize  # noqa: E402


def run(root, ev, cfg, q, s, secs, tok):
    d = os.path.join(root, "runs", ev, cfg, "run-1")
    os.makedirs(d)
    exp = [{"text": "[Q][X] a%d" % i, "passed": i < q[0]} for i in range(q[1])]
    exp += [{"text": "[S][G1] b%d" % i, "passed": i < s[0]} for i in range(s[1])]
    json.dump({"expectations": exp, "summary": {"quality": {"passed": q[0], "total": q[1]},
                                                "structure": {"passed": s[0], "total": s[1]}}},
              open(os.path.join(d, "grading.json"), "w"))
    json.dump({"total_tokens": tok, "duration_ms": secs * 1000}, open(os.path.join(d, "timing.json"), "w"))


class Summarize(unittest.TestCase):
    def test_q_and_s_separate(self):
        root = tempfile.mkdtemp()
        try:
            run(root, "eval-1", "with_skill", (13, 13), (30, 40), 100, 1000)
            run(root, "eval-2", "with_skill", (12, 13), (34, 40), 300, 3000)
            run(root, "eval-1", "without_skill", (9, 13), (1, 30), 50, 500)
            self.assertEqual(summarize.main([os.path.join(root, "runs")]), 0)
            out = json.load(open(os.path.join(root, "benchmark-q.json")))
            w = out["configurations"]["with_skill"]
            self.assertAlmostEqual(w["q_rate"]["mean"], (1 + 12 / 13.0) / 2)
            self.assertAlmostEqual(w["s_rate"]["mean"], (30 + 34) / 80.0)
            self.assertAlmostEqual(w["seconds"]["mean"], 200)
            self.assertAlmostEqual(w["tokens"]["mean"], 2000)
            self.assertEqual(out["configurations"]["without_skill"]["q_rate"]["sd"], 0.0)
            md = open(os.path.join(root, "benchmark-q.md")).read()
            self.assertIn("[Q] pass rate", md)
            self.assertIn("[S] pass rate", md)
        finally:
            shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
