"""iter26 (0.14.0): entrada do catálogo (harness + emit); versão relativa."""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def _vt(s):
    return tuple(int(x) for x in s.strip().split("."))


def _cat():
    txt = open(os.path.join(SKILL, "references", "migrations.json5"), encoding="utf-8").read()
    return [m.group(1) for m in re.finditer(r'to:\s*"([\d.]+)"', txt)], txt


class TestCatalogo0140(unittest.TestCase):
    def test_version_nao_menor_que_0140(self):
        v = open(os.path.join(SKILL, "VERSION"), encoding="utf-8").read()
        self.assertGreaterEqual(_vt(v), (0, 14, 0))

    def test_uma_entrada_0140_com_harness_e_emit(self):
        tos, txt = _cat()
        self.assertEqual(tos.count("0.14.0"), 1)
        blk = txt[txt.index('to: "0.14.0"'):]
        self.assertIn('{kind: "harness"}', blk)
        self.assertIn('{kind: "emit"}', blk)

    def test_entradas_crescentes(self):
        tos, _ = _cat()
        self.assertEqual(tos, sorted(tos, key=_vt))


if __name__ == "__main__":
    unittest.main()
