"""iter26 (CA-06): tokens reais por despacho medidos no guard; sem transcript = NOT_RUN com motivo; falha visível."""
import json
import os
import tempfile
import unittest

import fixture  # noqa: F401  (põe o engine no sys.path)
import guard


def _asst(i, inp, out, cr=0, cw=0, usage=None):
    u = {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cr,
         "cache_creation_input_tokens": cw} if usage is None else usage
    return json.dumps({"type": "assistant", "message": {"id": i, "model": "claude-sonnet-4-5", "usage": u}})


class TestMeasureUsage(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tr(self, lines):
        p = os.path.join(self.d, "t.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return {"agent_transcript_path": p}

    def test_soma_por_id_distinto(self):
        r = guard._measure_usage(self.tr([_asst("a", 10, 5, 3, 1), _asst("a", 10, 5, 3, 1), _asst("b", 20, 7, 0, 2)]))
        self.assertEqual((r["input_tokens"], r["output_tokens"], r["cache_read_input_tokens"],
                          r["cache_creation_input_tokens"]), (30, 12, 3, 3))
        self.assertEqual(r["procedencia"], "medida")

    def test_sem_transcript_not_run_sem_zero(self):
        for payload in ({}, {"agent_transcript_path": os.path.join(self.d, "nao-existe.jsonl")}):
            r = guard._measure_usage(payload)
            self.assertEqual(r["status"], "NOT_RUN")
            self.assertGreater(len(r["reason"]), 8)
            self.assertNotIn("input_tokens", r)

    def test_transcript_sem_usage_not_run(self):
        r = guard._measure_usage(self.tr([json.dumps({"type": "user", "message": {"content": "Ana"}})]))
        self.assertEqual(r["status"], "NOT_RUN")

    def test_so_invalido_error(self):
        r = guard._measure_usage(self.tr(['{"type": "assistant", "message": {"usage": {"input_tokens": ',
                                          _asst("x", 0, 0, usage={"input_tokens": "mil"})]))
        self.assertEqual(r["status"], "ERROR")
        self.assertNotIn("input_tokens", r)

    def test_valido_com_linha_invalida_conta_as_invalidas(self):
        r = guard._measure_usage(self.tr([_asst("a", 4, 2), '{"usage": [[[']))
        self.assertEqual(r["input_tokens"], 4)
        self.assertEqual(r["linhas_invalidas"], 1)


if __name__ == "__main__":
    unittest.main()
