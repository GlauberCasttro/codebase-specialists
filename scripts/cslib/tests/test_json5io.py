"""Testes do subconjunto JSON5 (cslib.json5io): ida e volta, rejeição, determinismo, formato."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cslib import json5io  # noqa: E402
from cslib.json5io import Json5Error  # noqa: E402


SAMPLE = {
    "schema_version": 1,
    "layer": "graph",
    "não-ident": "ação \"aspas\" \\ barra\ttab",
    "nested": {"a": 1, "b": [1, 2.5, -3e-05, True, False, None], "c": {}},
    "big": {"k1": 1, "k2": 2, "k3": 3, "k4": [{"x": 1}, {"y": [1, 2]}]},
    "edges": [["a.py", "b.py", 2], ["b.py", "c.py", 1]],
    "empty_list": [],
    "unicode": "emoji \U0001F600 e ç",
}


class RoundTrip(unittest.TestCase):
    def test_roundtrip_equal(self):
        text = json5io.dumps(SAMPLE, "teste — gerado por test_json5io")
        self.assertEqual(json5io.loads(text), SAMPLE)

    def test_deterministic_bytes(self):
        a = json5io.dumps(SAMPLE, "h")
        reordered = dict(reversed(list(SAMPLE.items())))
        b = json5io.dumps(reordered, "h")
        self.assertEqual(a, b)
        self.assertEqual(json5io.dumps(json5io.loads(a), "h"), a)

    def test_format_rules(self):
        text = json5io.dumps({"a": 1, "b": "x"}, "cabecalho")
        self.assertEqual(text, '// cabecalho\n{a: 1, b: "x"}\n')
        text = json5io.dumps({"d": 4, "c": 3, "b": 2, "a": 1})
        self.assertEqual(text, "{\n a: 1,\n b: 2,\n c: 3,\n d: 4\n}\n")
        text = json5io.dumps({"l": [{"x": 1}, {"x": 2}]})
        self.assertEqual(text, "{\n l: [\n  {x: 1},\n  {x: 2}\n ]\n}\n")
        self.assertIn('"não-ident":', json5io.dumps(SAMPLE))

    def test_accepts_subset(self):
        text = """// topo
        /* bloco
           multi */ {
          a: 1, // fim de linha
          "b-c": [1, 2, 3,],
          $d_e: {x: "y",},
          f: -0.5e+3,
        }"""
        self.assertEqual(json5io.loads(text), {"a": 1, "b-c": [1, 2, 3], "$d_e": {"x": "y"}, "f": -500.0})

    def test_file_dump_load(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json5")
            json5io.dump(SAMPLE, p, "arquivo de teste")
            self.assertEqual(json5io.load(p), SAMPLE)
            with open(p, "rb") as fh:
                self.assertTrue(fh.read().startswith(b"// arquivo de teste\n"))


class Rejects(unittest.TestCase):
    BAD = [
        "{a: 'x'}",            # aspas simples
        "{a: 0x10}",           # hex
        "{a: Infinity}",
        "{a: NaN}",
        "{a: +1}",
        "{a: .5}",
        "{a: 5.}",
        '{a: "linha\\\nquebrada"}',
        '{a: "raw\nnewline"}',
        "{a-b: 1}",            # chave não-identificador sem aspas
        "{a: 1, a: 2}",        # duplicada
        "[1,,2]",
        "{a: 1,,}",
        "[1] x",
        "/* aberto",
        "{a: 1",
        "",
        "{a: undefined}",
    ]

    def test_rejects(self):
        for bad in self.BAD:
            with self.assertRaises(Json5Error, msg=bad):
                json5io.loads(bad)

    def test_error_has_position(self):
        with self.assertRaises(Json5Error) as cm:
            json5io.loads("{\n a: 'x'}")
        self.assertIn("linha 2", str(cm.exception))

    def test_writer_rejects_nan_and_types(self):
        for bad in ({"a": float("nan")}, {"a": float("inf")}, {"a": {1, 2}}, {1: "x"}, {"a": b"x"}):
            with self.assertRaises(Json5Error):
                json5io.dumps(bad)

    def test_header_single_line(self):
        with self.assertRaises(Json5Error):
            json5io.dumps({}, "a\nb")


if __name__ == "__main__":
    unittest.main()
