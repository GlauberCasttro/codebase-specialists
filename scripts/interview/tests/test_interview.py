"""cs.py interview (scan.6): ask/record/status, unknown, lote ≤8, fatos interview.* para team/probes."""
import json
import os
import unittest

from helpers import cs, synth

from cslib import json5io
from cslib.paths import STATE_DIR


class InterviewTest(unittest.TestCase):
    def setUp(self):
        self.root = synth.make_repo()

    def tearDown(self):
        synth.cleanup(self.root)

    def ask(self, qid, q="Por que dinheiro é inteiro?"):
        return cs(self.root, "interview", "ask", "--id", qid, "--question", q, "--context",
                  "vi valores monetários inteiros em 4 lugares")

    def test_empty_interview_fails_no_pending(self):
        self.assertEqual(cs(self.root, "interview", "status", "--no-pending")[0], 1)

    def test_pending_then_answered(self):
        self.assertEqual(self.ask("Q-01")[0], 0)
        self.assertEqual(self.ask("Q-02", "Há área congelada?")[0], 0)
        code, _, err = cs(self.root, "interview", "status", "--no-pending")
        self.assertEqual(code, 1)
        self.assertIn("Q-01", err)
        self.assertEqual(cs(self.root, "interview", "record", "--id", "Q-01", "--answer",
                            "Centavos: float já quebrou fatura em 2023.", "--scope", "src/billing/**")[0], 0)
        self.assertEqual(cs(self.root, "interview", "record", "--id", "Q-02", "--answer-unknown")[0], 0)
        self.assertEqual(cs(self.root, "interview", "status", "--no-pending")[0], 0)
        doc = json5io.load(os.path.join(self.root, STATE_DIR, "facts", "interview.json5"))
        ids = [f["id"] for f in doc["facts"]]
        self.assertEqual(ids, ["interview.q-01"])  # unknown não vira fato
        f = doc["facts"][0]
        self.assertEqual(f["layer"], "interview")
        self.assertEqual(f["data"]["answer"], "Centavos: float já quebrou fatura em 2023.")
        self.assertEqual(f["evidence"][0]["file"], ".swarm/interview.jsonl")
        idx = json5io.load(os.path.join(self.root, STATE_DIR, "facts", "index.json5"))
        self.assertIn("interview.q-01", idx["facts"])
        # consumido por team (regra 8 lê facts/interview.json5)
        from team._shared_tmp.factsio import Facts
        self.assertIn("interview.q-01", [x["id"] for x in Facts(self.root).interview_invariants()])

    def test_literal_answer_and_log_append_only(self):
        self.ask("Q-01")
        cs(self.root, "interview", "record", "--id", "Q-01", "--answer", "  sim, é regra  ")
        with open(os.path.join(self.root, STATE_DIR, "interview.jsonl")) as fh:
            recs = [json.loads(x) for x in fh if x.strip()]
        self.assertEqual([r["type"] for r in recs], ["question", "answer"])
        self.assertEqual(recs[1]["answer"], "  sim, é regra  ")

    def test_batch_limit_and_invalid(self):
        for i in range(8):
            self.assertEqual(self.ask("Q-%02d" % i)[0], 0)
        code, _, err = self.ask("Q-99")
        self.assertEqual(code, 2)
        self.assertIn("lote cheio", err)
        self.assertEqual(self.ask("Q-00")[0], 2)  # duplicada
        self.assertEqual(cs(self.root, "interview", "record", "--id", "Q-77", "--answer", "x")[0], 2)
        self.assertEqual(cs(self.root, "interview", "record", "--id", "Q-01", "--answer", " ")[0], 2)
        self.assertEqual(cs(self.root, "interview", "ask", "--id", "a b", "--question", "x")[0], 2)

    def test_record_with_question_creates_it(self):
        code, _, err = cs(self.root, "interview", "record", "--id", "Q-9", "--question", "Quem decide?",
                          "--answer", "o CTO")
        self.assertEqual(code, 0, err)
        self.assertEqual(cs(self.root, "interview", "status", "--no-pending")[0], 0)

    def test_stage_check_answers_are_ignored(self):
        with open(os.path.join(self.root, STATE_DIR, "interview.jsonl"), "w") as fh:
            fh.write(json.dumps({"ts": "x", "substage": "init.2", "answer": "claude-code"}) + "\n")
        self.ask("Q-01")
        self.assertEqual(cs(self.root, "interview", "record", "--id", "Q-01", "--answer", "sim")[0], 0)
        self.assertEqual(cs(self.root, "interview", "status", "--no-pending")[0], 0)


if __name__ == "__main__":
    unittest.main()
