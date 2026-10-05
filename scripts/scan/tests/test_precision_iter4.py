"""Regressões de PRECISÃO do scan — iteração 4 (PLANO-ITER4.json5, frente_docs_scan_eval).

Defeito medido na iteração 3 (notes.md de py-billing e go-polyglot): o L9 dizia "alcançável por teste
... (não prova esta regra)" para regra que o teste PROVA pelo valor esperado/derivado da constante:
- py: tests/test_late_fees.py:15 `assertEqual(late_fee(Money(300000), 1).cents, 6100)` (LATE_FINE_BP,
  MONTHLY_INTEREST_BP, DAYS_PER_MONTH);
- go: eta_test.go:18 `if got := ETA(8, 0); got != time.Hour { t.Fatalf(...) }` (brule.limit.minspeedkmh);
- ts: `assert.throws(() => checkout(cart(11, 1), ...), RangeError)` (MAX_QTY_PER_LINE).
E o contrário (fato errado é pior que fato ausente): chamar sem conferir não vira cobertura, e exceção
que duas validações do fecho levantam não prova nenhuma delas. Nenhum fato diz "não prova" por palpite.
"""

import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_precision import build, load, scan  # noqa: E402

PY = {
    "pyproject.toml": "[project]\nname = \"billing\"\nversion = \"0.1.0\"\n",
    "src/billing/__init__.py": "",
    "src/billing/errors.py": "class InvalidAmount(Exception):\n    pass\n",
    "src/billing/late_fees.py": (
        "LATE_FINE_BP = 200            # 2% fine\n"
        "MONTHLY_INTEREST_BP = 100     # 1% a month\n"
        "DAYS_PER_MONTH = 30           # commercial month\n\n\n"
        "def late_fee(total, days):\n"
        "    if days <= 0:\n"
        "        return 0\n"
        "    fine = total * LATE_FINE_BP // 10000\n"
        "    daily = total * MONTHLY_INTEREST_BP // (DAYS_PER_MONTH * 10000)\n"
        "    return fine + daily * days\n"),
    "src/billing/terms.py": (
        "GRACE_DAYS = 5\n\n\n"
        "def grace(days):\n"
        "    return days + GRACE_DAYS\n"),
    "src/billing/money.py": (
        "from billing.errors import InvalidAmount\n\n"
        "MAX_CENTS = 1000000000\n\n\n"
        "def make(cents):\n"
        "    if not isinstance(cents, int):\n"
        "        raise InvalidAmount(\"cents must be int\")\n"
        "    if cents > MAX_CENTS:\n"
        "        raise InvalidAmount(\"amount above the maximum\")\n"
        "    return cents\n"),
    "tests/__init__.py": "",
    "tests/test_late_fees.py": (
        "import unittest\n\n"
        "from billing.late_fees import late_fee\n\n\n"
        "class LateFeeTest(unittest.TestCase):\n"
        "    def test_fine_and_one_day_of_interest(self):\n"
        "        # 2% of R$ 3.000,00 = 6000; 1% a.m. / 30 * 1 day = 100\n"
        "        self.assertEqual(late_fee(300000, 1), 6100)\n"),
    "tests/test_terms.py": (
        "import unittest\n\n"
        "from billing.terms import grace\n\n\n"
        "class TermsTest(unittest.TestCase):\n"
        "    def test_grace_runs(self):\n"
        "        grace(3)\n"
        "        self.assertTrue(True)\n"),
    "tests/test_money.py": (
        "import unittest\n\n"
        "from billing.errors import InvalidAmount\n"
        "from billing.money import make\n\n\n"
        "class MoneyTest(unittest.TestCase):\n"
        "    def test_rejects_float(self):\n"
        "        with self.assertRaises(InvalidAmount):\n"
        "            make(10.5)\n"),
}

GO = {
    "go.mod": "module example.com/fleet\n\ngo 1.22\n",
    "internal/tracking/eta.go": (
        "package tracking\n\nimport \"time\"\n\n"
        "// MinSpeedKmh is the floor used for ETA.\nconst MinSpeedKmh = 8.0\n\n"
        "func ETA(remainingKm, speedKmh float64) time.Duration {\n"
        "\tif speedKmh < MinSpeedKmh {\n\t\tspeedKmh = MinSpeedKmh\n\t}\n"
        "\treturn time.Duration(remainingKm / speedKmh * float64(time.Hour))\n}\n"),
    "internal/tracking/eta_test.go": (
        "package tracking\n\nimport (\n\t\"testing\"\n\t\"time\"\n)\n\n"
        "func TestETAUsesSpeedFloor(t *testing.T) {\n"
        "\tif got := ETA(8, 0); got != time.Hour {\n"
        "\t\tt.Fatalf(\"stopped courier must use MinSpeedKmh, got %v\", got)\n\t}\n}\n"),
}

TS = {
    "package.json": "{\"name\": \"shop\", \"type\": \"module\"}\n",
    "src/orders/rules.ts": (
        "export const MAX_QTY_PER_LINE = 10;\n\n"
        "export function assertLineQuantity(quantity: number): void {\n"
        "  if (quantity < 1 || quantity > MAX_QTY_PER_LINE) {\n"
        "    throw new RangeError(`quantity must be in 1..${MAX_QTY_PER_LINE}`);\n"
        "  }\n}\n"),
    "src/orders/checkout.ts": (
        "import { assertLineQuantity } from \"./rules.ts\";\n\n"
        "export function checkout(qty: number): number {\n"
        "  if (qty === 0) throw new Error(\"cannot checkout an empty cart\");\n"
        "  assertLineQuantity(qty);\n"
        "  return qty;\n}\n"),
    "src/orders/checkout.test.ts": (
        "import { test } from \"node:test\";\n"
        "import assert from \"node:assert/strict\";\n"
        "import { checkout } from \"./checkout.ts\";\n\n"
        "test(\"quantity per line is limited to 10\", () => {\n"
        "  assert.throws(() => checkout(11), RangeError);\n"
        "});\n"),
}


def facts(root):
    return load(root, "business_rules")["facts"]


def by_subject(root, subject):
    for f in facts(root):
        if f["data"]["subject"] == subject and f["data"]["kind"] != "validation":
            return f
    raise AssertionError("%s ausente: %s" % (subject, [x["id"] for x in facts(root)]))


class TestedByDerivedValue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.py, cls.go, cls.ts = build(PY), build(GO), build(TS)
        for r in (cls.py, cls.go, cls.ts):
            scan(r, "--no-exec", "--layers", "L9")

    @classmethod
    def tearDownClass(cls):
        for r in (cls.py, cls.go, cls.ts):
            shutil.rmtree(r, ignore_errors=True)

    def test_python_constants_proved_by_expected_value(self):
        for name in ("LATE_FINE_BP", "MONTHLY_INTEREST_BP", "DAYS_PER_MONTH"):
            f = by_subject(self.py, name)
            self.assertEqual(f["data"]["coverage"], "asserted", f["claim"])
            self.assertEqual(f["data"]["test"], "tests/test_late_fees.py:9", f["claim"])
            self.assertNotIn("não prova", f["claim"])

    def test_go_speed_floor_proved_by_if_fatal(self):
        f = by_subject(self.go, "MinSpeedKmh")
        self.assertEqual(f["data"]["coverage"], "asserted", f["claim"])
        self.assertEqual(f["data"]["test"].split(":")[0], "internal/tracking/eta_test.go")
        self.assertNotIn("não prova", f["claim"])

    def test_ts_limit_proved_by_unique_exception_in_closure(self):
        f = by_subject(self.ts, "MAX_QTY_PER_LINE")
        self.assertEqual(f["data"]["coverage"], "asserted", f["claim"])
        self.assertEqual(f["data"]["test"].split(":")[0], "src/orders/checkout.test.ts")

    def test_call_without_assertion_is_not_coverage(self):
        f = by_subject(self.py, "GRACE_DAYS")
        self.assertEqual(f["data"]["coverage"], "exercised", f["claim"])
        self.assertIsNone(f["data"]["test"])
        self.assertNotIn("não prova", f["claim"])  # não determinado ≠ não prova
        self.assertIn("não é determinável", f["claim"])

    def test_exception_shared_by_two_validations_does_not_prove_constant(self):
        f = by_subject(self.py, "MAX_CENTS")
        self.assertEqual(f["data"]["coverage"], "exercised", f["claim"])  # 2 validações levantam InvalidAmount
        self.assertIsNone(f["data"]["test"])

    def test_no_fact_says_not_proved(self):
        for root in (self.py, self.go, self.ts):
            for f in facts(root):
                self.assertNotIn("não prova", f["claim"], f["id"])
                self.assertNotIn("nenhum teste prova", f["claim"], f["id"])


if __name__ == "__main__":
    unittest.main()
