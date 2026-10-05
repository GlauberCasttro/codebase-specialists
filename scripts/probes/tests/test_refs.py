"""cslib/refs.py — classificador único (iteração 3, contrato `refs`). Casos reais das notas da iteração 2."""
import os
import sys
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SCRIPTS)

from cslib import refs  # noqa: E402
from team._shared_tmp.cardtext import extract_refs  # noqa: E402


class TestClassify(unittest.TestCase):
    def test_kinds(self):
        cases = {
            "src/billing/invoice.py": "path", "src/billing/invoice.py:10": "path", "Makefile": "path",
            "src/**/*.test.ts": "glob", "packages/*/src/**": "glob",
            "@shop/shared": "package", "@shop/api/*": "package",
            "npm test": "command", "node src/server.ts": "command", "./scripts/x.sh a": "command",
            "Journal.post": "symbol", "charge_customer": "symbol", "Money.percent": "symbol",
            "Money.percent/Money.allocate": "symbol",
            "//": "prose", "->": "prose", "dinheiro em centavos": "prose", "https://x.y/z": "prose",
            "42": "prose", "money": "prose",
        }
        for tok, want in sorted(cases.items()):
            self.assertEqual(refs.classify(tok), want, tok)

    def test_bare_text_needs_known_extension(self):
        self.assertEqual(refs.classify("Money.percent/Money.allocate", backticked=False), "symbol")
        self.assertEqual(refs.classify("a/b.allocate", backticked=False), "prose")
        self.assertEqual(refs.classify("src/x.py", backticked=False), "path")

    def test_alternatives(self):
        self.assertEqual(refs.split_alternatives("go.mod/go.sum"), ["go.mod", "go.sum"])
        self.assertEqual(refs.split_alternatives("Money.percent/Money.allocate"), ["Money.percent", "Money.allocate"])
        self.assertEqual(refs.split_alternatives("src/a.py"), ["src/a.py"])

    def test_extract_from_panel_prose(self):
        # iteração 2: `team core from-panel` lia `//`, `Money.percent` e prosa como caminho
        text = ("Nunca use `//` para dinheiro; use `Money.percent/Money.allocate` (ver src/money.py:12) e "
                "importe de `@shop/shared`. Rode `npm test`.")
        got = [(k, v, ln) for k, v, ln, _ in refs.extract(text)]
        self.assertIn(("symbol", "Money.percent", None), got)
        self.assertIn(("symbol", "Money.allocate", None), got)
        self.assertIn(("package", "@shop/shared", None), got)
        self.assertIn(("command", "npm test", None), got)
        self.assertIn(("path", "src/money.py", 12), got)
        self.assertFalse([g for g in got if g[1] == "//"])

    def test_cardtext_uses_refs(self):
        got = extract_refs("`//` e `@shop/shared` e `src/**/*.test.ts` e `make test` [unverified]")
        self.assertEqual(got, [("path", "src/**/*.test.ts", None), ("command", "make test", "marked")])


if __name__ == "__main__":
    unittest.main()
