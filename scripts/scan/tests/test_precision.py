"""Regressões de PRECISÃO do scan (iteração 1 de evals: 7–9 de 10 fatos conferidos errados).

Cada classe reproduz um defeito de DEFEITOS.json5 (frente_scan) num repositório sintético mínimo.
Princípio: fato errado é pior que fato ausente — na dúvida o scan omite ou marca confidence low.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402

from cslib import json5io  # noqa: E402
from cslib.paths import STATE_DIR  # noqa: E402


def load(root, name):
    return json5io.load(os.path.join(root, STATE_DIR, "facts", name + ".json5"))


def build(files):
    root = tempfile.mkdtemp(prefix="cs-prec-")
    for rel, text in files.items():
        synth.write(root, rel, text)
    synth.git(root, "init", "-q")
    synth.commit(root, "init")
    return root


def scan(root, *extra):
    r = synth.cs(root, "scan", "--timeout", "60", *extra)
    if r.returncode != 0:
        raise AssertionError(r.stderr.decode())
    return r


def stale_facts(root):
    return [f for f in load(root, "project_docs")["facts"] if f["id"].startswith("docs.stale.")]


def rules_at(root, rel, line=None):
    out = []
    for f in load(root, "business_rules")["facts"]:
        ev = f["evidence"][0]
        if ev.get("file") == rel and (line is None or ev.get("line") == line):
            out.append(f)
    return out


# ---------------------------------------------------------------- ADR (L6)
class AdrStatusPortuguese(unittest.TestCase):
    """ADR com status em PT ('aceito', 'Aceita', 'Status: aceito') era lido como unknown."""

    @classmethod
    def setUpClass(cls):
        cls.root = build({
            "src/app.py": "X = 1\n",
            "docs/adr/0001-a.md": "# ADR 0001 — A\n\n- Status: aceito (2025-03-04)\n\n## Decisão\nFaz A.\n",
            "docs/adr/0002-b.md": "# ADR 0002 — B\n\nStatus: Aceita\n\n## Decisão\nFaz B.\n",
            "docs/adr/0003-c.md": "# ADR 0003 — C\n\n**Status:** proposto\n\n## Decisão\nFaz C.\n",
            "docs/adr/0004-d.md": "# ADR 0004 — D\n\n## Status\n\nSubstituído pelo ADR 0003\n",
            "docs/adr/0005-e.md": "# ADR 0005 — E\n\nNada aqui.\n",
        })
        scan(cls.root, "--no-exec", "--layers", "L6")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def status(self, name):
        for f in load(self.root, "rationale")["facts"]:
            if f["evidence"][0]["file"] == "docs/adr/" + name:
                return f
        raise AssertionError(name)

    def test_pt_statuses_normalized(self):
        self.assertEqual(self.status("0001-a.md")["data"]["status"], "accepted")
        self.assertEqual(self.status("0001-a.md")["data"]["status_raw"], "aceito")
        self.assertEqual(self.status("0002-b.md")["data"]["status"], "accepted")
        self.assertEqual(self.status("0003-c.md")["data"]["status"], "proposed")
        self.assertEqual(self.status("0004-d.md")["data"]["status"], "superseded")

    def test_missing_status_is_unknown_not_guessed(self):
        f = self.status("0005-e.md")
        self.assertEqual(f["data"]["status"], "unknown")
        self.assertIn("status: unknown", f["claim"])


# ---------------------------------------------------------------- cobertura (L9)
TS_SHOP = {
    "package.json": '{"name": "shop", "private": true, "workspaces": ["packages/*", "apps/*"],\n'
                    ' "scripts": {"test": "node --test"}}\n',
    "apps/web/package.json": '{"name": "@shop/web", "dependencies": {"@shop/shared": "1.0.0"}}\n',
    "apps/web/src/formatPrice.ts": (
        "export function formatPrice(cents: number): string {\n"
        "  if (!Number.isInteger(cents)) throw new TypeError(\"price must be integer cents\");\n"
        "  return String(cents);\n"
        "}\n"),
    "apps/web/src/cart.ts": (
        "import type { Sku } from \"@shop/shared\";\n"
        "export const UI_LIMIT_QTY = 5;\n"
        "export function clamp(q: number): number { return Math.min(q, UI_LIMIT_QTY); }\n"
        "export function onlyHere(q: number): number {\n"
        "  if (q < 0) throw new RangeError(\"quantity must be positive\");\n"
        "  return q;\n"
        "}\n"),
    "apps/web/src/cart.test.ts": (
        "import { test } from \"node:test\";\n"
        "import assert from \"node:assert/strict\";\n"
        "import { formatPrice } from \"./formatPrice.ts\";\n"
        "\n"
        "test(\"formatPrice renders integer cents\", () => {\n"
        "  assert.equal(formatPrice(100), \"100\");\n"
        "  assert.throws(() => formatPrice(12.5), TypeError);\n"
        "});\n"),
    "packages/shared/package.json": '{"name": "@shop/shared", "exports": {".": "./src/index.ts"}}\n',
    "packages/shared/src/index.ts": "export * from \"./sku.ts\";\n",
    "packages/shared/src/sku.ts": (
        "export type Sku = string & { readonly __brand: \"Sku\" };\n"
        "export const SKU_PATTERN = /^[A-Z]{3}-\\d{4}$/;\n"
        "export function parseSku(raw: string): Sku {\n"
        "  const value = raw.trim().toUpperCase();\n"
        "  if (!SKU_PATTERN.test(value)) {\n"
        "    throw new Error(`invalid SKU \"${raw}\": expected AAA-0000`);\n"
        "  }\n"
        "  return value as Sku;\n"
        "}\n"),
    "packages/shared/src/sku.test.ts": (
        "import { test } from \"node:test\";\n"
        "import assert from \"node:assert/strict\";\n"
        "import { parseSku } from \"./sku.ts\";\n"
        "\n"
        "test(\"parseSku normalizes\", () => {\n"
        "  assert.equal(parseSku(\" tsh-0042 \"), \"TSH-0042\");\n"
        "  assert.throws(() => parseSku(\"TSH42\"), /invalid SKU/);\n"
        "});\n"),
}

PY_BILLING = {
    "src/billing/__init__.py": "",
    "src/billing/errors.py": ("class BillingError(Exception):\n    pass\n\n\n"
                              "class LedgerImbalance(BillingError):\n    pass\n\n\n"
                              "class Orphan(BillingError):\n    pass\n"),
    "src/billing/journal.py": (
        "from billing.errors import LedgerImbalance\n\n\n"
        "class Journal:\n"
        "    def post(self, debits, credits):\n"
        "        self._check_balanced(debits, credits)\n"
        "        return (debits, credits)\n\n"
        "    @staticmethod\n"
        "    def _check_balanced(debits, credits):\n"
        "        if debits != credits:\n"
        "            raise LedgerImbalance(\n"
        "                \"debits %d != credits %d\" % (debits, credits)\n"
        "            )\n"),
    "src/billing/fees.py": (
        "DAYS_PER_MONTH = 30  # commercial month\n"
        "DEFAULT_TERMS_DAYS = 30\n"
        "LATE_FINE_BP = 200  # 2% fine\n\n\n"
        "def due_in(days=DEFAULT_TERMS_DAYS):\n"
        "    return days\n\n\n"
        "def late_fee(total, days):\n"
        "    return total * LATE_FINE_BP // 10000 + days * total // DAYS_PER_MONTH\n\n\n"
        "def strict(days):\n"
        "    if days < 0:\n"
        "        raise ValueError(\"days must be positive\")\n"),
    "src/billing/money.py": (
        "from billing.errors import BillingError\n\n\n"
        "class CurrencyMismatch(BillingError):\n    pass\n\n\n"
        "class Money:\n"
        "    def __init__(self, cents, currency):\n"
        "        self.cents, self.currency = cents, currency\n\n"
        "    def _same(self, other):\n"
        "        if other.currency != self.currency:\n"
        "            raise CurrencyMismatch(\"%s != %s\" % (self.currency, other.currency))\n\n"
        "    def __add__(self, other):\n"
        "        self._same(other)\n"
        "        return Money(self.cents + other.cents, self.currency)\n"),
    "src/billing/amount.py": (
        "from billing.errors import BillingError\n\n\n"
        "class BadAmount(BillingError):\n    pass\n\n\n"
        "class Amount:\n"
        "    def __init__(self, cents, currency):\n"
        "        if not isinstance(cents, int):\n"
        "            raise BadAmount(\"cents must be int\")\n"
        "        if currency not in (\"BRL\",):\n"
        "            raise BadAmount(\"unsupported currency\")\n"),
    "tests/test_amount.py": (
        "import unittest\n\n"
        "from billing.amount import Amount, BadAmount\n\n\n"
        "class AmountTest(unittest.TestCase):\n"
        "    def test_rejects_float(self):\n"
        "        with self.assertRaises(BadAmount):\n"
        "            Amount(1.5, \"BRL\")\n"),
    "src/billing/gateway.py": (
        "from billing.errors import Orphan\n\n\n"
        "def charge(body):\n"
        "    if body[\"status\"] == 402:\n"
        "        raise Orphan(body.get(\"reason\", \"declined\"))\n"),
    "tests/test_money.py": (
        "import unittest\n\n"
        "from billing.money import CurrencyMismatch, Money\n\n\n"
        "class MoneyTest(unittest.TestCase):\n"
        "    def test_currency_mismatch(self):\n"
        "        with self.assertRaises(CurrencyMismatch):\n"
        "            Money(1, \"BRL\") + Money(1, \"USD\")\n"),
    "src/billing/orphan.py": (
        "from billing.errors import Orphan\n\n\n"
        "def nobody_tests_me(x):\n"
        "    if x < 0:\n"
        "        raise Orphan(\"x must be positive\")\n"
        "    return x\n"),
    "tests/test_journal.py": (
        "import unittest\n\n"
        "from billing.errors import LedgerImbalance\n"
        "from billing.journal import Journal\n\n\n"
        "class JournalTest(unittest.TestCase):\n"
        "    def test_rejects_unbalanced_entry(self):\n"
        "        with self.assertRaises(LedgerImbalance):\n"
        "            Journal().post(100, 99)\n"),
    "tests/test_fees.py": (
        "import unittest\n\n"
        "from billing.fees import due_in, late_fee\n\n\n"
        "class FeeTest(unittest.TestCase):\n"
        "    def test_fee(self):\n"
        "        self.assertEqual(late_fee(30000, 1), 1600)\n\n"
        "    def test_due(self):\n"
        "        self.assertEqual(due_in(), 30)\n"),
}


class CoverageBySymbolAndImport(unittest.TestCase):
    """Regra marcada 'sem teste que cubra' quando há teste (formatPrice, sku, py-billing)."""

    @classmethod
    def setUpClass(cls):
        cls.ts = build(TS_SHOP)
        cls.py = build(PY_BILLING)
        scan(cls.ts, "--no-exec", "--layers", "L9")
        scan(cls.py, "--no-exec", "--layers", "L9")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.ts, ignore_errors=True)
        shutil.rmtree(cls.py, ignore_errors=True)

    def one(self, root, rel, line=None):
        fs = rules_at(root, rel, line)
        self.assertTrue(fs, "nenhuma regra em %s:%s" % (rel, line))
        return fs[0]

    def test_exception_asserted_by_test_that_imports_and_calls(self):
        f = self.one(self.ts, "apps/web/src/formatPrice.ts", 2)
        self.assertNotIn("sem teste", f["claim"])
        self.assertEqual(f["data"]["test"].split(":")[0], "apps/web/src/cart.test.ts")
        self.assertIn(f["data"]["coverage"], ("message", "exception"))

    def test_regex_in_throws_matches_message(self):
        f = self.one(self.ts, "packages/shared/src/sku.ts", 6)
        self.assertEqual(f["data"]["coverage"], "message")
        self.assertEqual(f["data"]["test"].split(":")[0], "packages/shared/src/sku.test.ts")

    def test_pattern_constant_is_a_rule_exercised_by_test(self):
        f = self.one(self.ts, "packages/shared/src/sku.ts", 2)
        self.assertEqual(f["data"]["subject"], "SKU_PATTERN")
        self.assertIn("packages/shared/src/sku.test.ts", f["claim"])

    def test_private_helper_reached_through_public_method(self):
        f = self.one(self.py, "src/billing/journal.py")
        self.assertNotIn("sem teste", f["claim"])
        self.assertIn("tests/test_journal.py", f["claim"])

    def test_constant_used_by_tested_function_is_asserted_by_value(self):
        # iteração 4: o teste confere o resultado da função que usa a constante (valor derivado) → coberto
        for name in ("DAYS_PER_MONTH", "LATE_FINE_BP", "DEFAULT_TERMS_DAYS"):
            f = [x for x in rules_at(self.py, "src/billing/fees.py") if x["data"]["subject"] == name]
            self.assertTrue(f, name)
            self.assertIn("tests/test_fees.py", f[0]["claim"])
            self.assertNotIn("sem teste", f[0]["claim"])
            self.assertNotIn("não prova", f[0]["claim"])
            self.assertEqual(f[0]["data"]["coverage"], "asserted")
            self.assertEqual(f[0]["data"]["test"].split(":")[0], "tests/test_fees.py")

    def test_untested_module_is_reported_without_overclaiming(self):
        f = self.one(self.py, "src/billing/orphan.py")
        self.assertIsNone(f["data"]["test"])
        self.assertEqual(f["data"]["coverage"], "none")
        self.assertNotIn("coberto", f["claim"])
        self.assertEqual(f["confidence"], "low")  # nenhum teste importa: pode ser testado por CLI

    def test_imported_module_but_rule_not_reached(self):
        f = [x for x in rules_at(self.py, "src/billing/fees.py") if x["data"]["kind"] == "validation"][0]
        self.assertEqual(f["data"]["coverage"], "none")
        self.assertEqual(f["confidence"], "medium")
        self.assertIn("tests/test_fees.py", f["claim"])

    def test_exception_raised_at_single_site_reached_by_operator(self):
        f = self.one(self.py, "src/billing/money.py", 14)
        self.assertEqual(f["data"]["coverage"], "exception")
        self.assertEqual(f["data"]["test"].split(":")[0], "tests/test_money.py")

    def test_same_exception_twice_in_tested_function_is_not_claimed(self):
        for line in (11, 13):
            f = self.one(self.py, "src/billing/amount.py", line)
            self.assertEqual(f["data"]["coverage"], "exercised", f["claim"])
            self.assertIsNone(f["data"]["test"])
            self.assertIn("ambíguo", f["claim"])
            self.assertIn("tests/test_amount.py:9 chama `Amount`", f["claim"])  # a chamada, não o assert

    def test_dict_key_is_not_the_message(self):
        f = self.one(self.py, "src/billing/gateway.py")
        self.assertNotIn("reason", f["claim"])

    def test_untested_function_in_tested_module(self):
        f = self.one(self.ts, "apps/web/src/cart.ts", 5)
        self.assertEqual(f["data"]["coverage"], "none")


# ---------------------------------------------------------------- docs (L10)
class DocsFalseStale(unittest.TestCase):
    """Comentário em bloco lido como alvo de make; caminho relativo de ADR; workspace npm; scripts da raiz."""

    @classmethod
    def setUpClass(cls):
        files = dict(TS_SHOP)
        files.update({
            "package.json": '{"name": "shop", "private": true, "workspaces": ["packages/*", "apps/*"],\n'
                            ' "scripts": {"test": "node --test", "lint": "eslint .", "typecheck": "tsc -b"}}\n',
            ".github/workflows/ci.yml": "jobs:\n  c:\n    steps:\n      - run: npm run lint\n"
                                        "      - run: npm run typecheck\n",
            "Makefile": "test:\n\tnode --test\n\ncheck-money:\n\tnode -e 1\n",
            "src/billing/ledger/accounts.py": "CASH = 1\n",
            "docs/adr/0002-ledger.md": ("# ADR 0002\n\n- Status: aceito\n\n"
                                        "O plano de contas fica em `ledger/accounts.py`.\n"),
            "README.md": ("# shop\n\n| `@shop/shared` | `packages/shared` |\n| `@shop/web` | `apps/web` |\n\n"
                          "Nunca importe `@shop/api/inventory` no web.\n\n"
                          "```\nmake test        # PYTHONPATH=src python3 -m unittest discover -s tests -v\n"
                          "make check-money # check-money + ruff check\n"
                          "npm run lint      # eslint flat config\n"
                          "npm run typecheck # tsc -b\n"
                          "npm run e2e       # Playwright\n"
                          "make deploy-prod\n```\n"),
        })
        cls.root = build(files)
        scan(cls.root, "--no-exec")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def claims(self, rel):
        d = load(self.root, "project_docs")
        doc = next(x for x in d["documents"] if x["file"] == rel)
        return doc["claims"]

    def test_only_true_stale(self):
        stale = sorted(f["claim"] for f in stale_facts(self.root))
        self.assertEqual(len(stale), 2, stale)
        self.assertTrue(any("npm run e2e" in s for s in stale))
        self.assertTrue(any("deploy-prod" in s for s in stale))

    def test_comment_after_hash_is_not_a_make_target(self):
        st = {c["text"]: c["status"] for c in self.claims("README.md") if c["kind"] == "command"}
        self.assertEqual(st["make test"], "verified")
        self.assertEqual(st["make check-money"], "verified")

    def test_root_scripts_seen_even_if_ci_declares_same_command(self):
        st = {c["text"]: c["status"] for c in self.claims("README.md") if c["kind"] == "command"}
        self.assertEqual(st["npm run lint"], "verified")
        self.assertEqual(st["npm run typecheck"], "verified")

    def test_relative_path_in_adr_resolved_by_suffix(self):
        cl = [c for c in self.claims("docs/adr/0002-ledger.md") if c["text"] == "ledger/accounts.py"]
        self.assertEqual(cl[0]["status"], "verified")

    def test_workspace_package_names_are_not_paths(self):
        cl = {c["text"]: c for c in self.claims("README.md")}
        self.assertEqual(cl["@shop/shared"]["kind"], "package")
        self.assertEqual(cl["@shop/shared"]["status"], "verified")
        self.assertNotEqual(cl["@shop/api/inventory"]["status"], "stale")  # workspace inexistente: não verificável


# ---------------------------------------------------------------- grafo (L1)
class WorkspaceImportsAreInternal(unittest.TestCase):
    """@shop/shared tratado como import externo → 0 arestas entre workspaces."""

    @classmethod
    def setUpClass(cls):
        cls.root = build(TS_SHOP)
        scan(cls.root, "--no-exec", "--layers", "L1")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_edge_to_workspace_entry(self):
        g = load(self.root, "graph")
        edges = {(e[0], e[1]) for e in g["edges"]}
        self.assertIn(("apps/web/src/cart.ts", "packages/shared/src/index.ts"), edges)
        self.assertIn(("packages/shared/src/index.ts", "packages/shared/src/sku.ts"), edges)
        self.assertNotIn("@shop/shared", g["external"].get("typescript", {}))
        self.assertFalse([f for f in g["facts"] if f["id"].startswith("graph.external.") and "shop" in f["id"]])
        line = [e[3] for e in g["edges"] if e[0] == "apps/web/src/cart.ts"][0]
        self.assertEqual(line, 1)


# ---------------------------------------------------------------- operação (L7)
class OperationsPrecision(unittest.TestCase):
    """Ferramenta ausente ≠ failed; nunca inventar comando; alvos de check executados; --if-present."""

    @classmethod
    def setUpClass(cls):
        cls.root = build({
            "Makefile": (".PHONY: test lint check-money fmt\n"
                         "test:\n\tpython3 -c \"print('ok')\"\n\n"
                         "lint: check-money\n\tzz-missing-linter-cs check src\n\n"
                         "check-money:\n\tpython3 -c \"print('money ok')\"\n\n"
                         "check-inner:\n\tsh -c 'zz-missing-inner-cs'\n\n"
                         "fails-check:\n\tpython3 -c \"import sys; sys.exit(3)\"\n\n"
                         "fmt:\n\tzz-missing-fmt -w .\n"),
            "src/app.py": "X = 1\n",
            "tests/test_app.py": "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_a(self):\n"
                                 "        self.assertTrue(True)\n",
            "package.json": ('{"name": "mono", "private": true, "workspaces": ["packages/*"],\n'
                             ' "scripts": {"test": "npm run test --workspaces --if-present",\n'
                             '             "typecheck": "tsc -b"}}\n'),
            "packages/a/package.json": '{"name": "@m/a", "scripts": {"test": "node -e 1"}}\n',
            "packages/b/package.json": '{"name": "@m/b", "scripts": {"build": "node -e 1"}}\n',
            "README.md": "# x\n\nRode `make lint` e `make test`.\n",
        })
        scan(cls.root, "--layers", "L7,L10")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def cmds(self):
        return {c["cmd"]: c for c in load(self.root, "operations")["commands"]}

    def test_missing_tool_in_recipe_is_unavailable(self):
        c = self.cmds()["make lint"]
        self.assertEqual(c["status"], "unavailable")
        self.assertEqual(c["missing_tool"], "zz-missing-linter-cs")

    def test_exit_127_inside_command_is_unavailable(self):
        c = self.cmds()["make check-inner"]
        self.assertEqual(c["status"], "unavailable")
        self.assertEqual(c["missing_tool"], "zz-missing-inner-cs")

    def test_node_modules_bin_missing_is_unavailable(self):
        c = self.cmds()["npm run typecheck"]
        self.assertEqual(c["status"], "unavailable")
        self.assertIn("tsc", c["missing_tool"])

    def test_real_failure_stays_failed(self):
        c = self.cmds()["make fails-check"]
        self.assertEqual(c["status"], "failed")

    def test_check_targets_are_executed(self):
        c = self.cmds()["make check-money"]
        self.assertEqual(c["kind"], "check")
        self.assertEqual(c["status"], "verified")

    def test_format_is_not_executed(self):
        self.assertEqual(self.cmds()["make fmt"]["status"], "declared")

    def test_never_infers_commands(self):
        for c in self.cmds().values():
            self.assertNotEqual(c["origin"], "inferred", c["cmd"])
        self.assertNotIn("python3 -m unittest discover -s tests", self.cmds())

    def test_unavailable_does_not_make_readme_stale(self):
        self.assertEqual(stale_facts(self.root), [])

    def test_if_present_footgun(self):
        f = [x for x in load(self.root, "operations")["facts"] if x["id"] == "ops.footgun.if-present"]
        self.assertEqual(len(f), 1)
        self.assertIn("packages/b", f[0]["claim"])
        self.assertNotIn("packages/a", f[0]["claim"])

    def test_summary_counts_unavailable(self):
        s = load(self.root, "operations")["summary"]
        self.assertGreaterEqual(s["unavailable"], 3)


# ---------------------------------------------------------------- constantes (L9)
class ConstantValues(unittest.TestCase):
    """Valor de constante errado (15 em vez de 900000): extrair o literal da definição inteira."""

    @classmethod
    def setUpClass(cls):
        cls.root = build({
            "src/r.ts": ("/** expires after 15 minutes */\n"
                         "export const RESERVATION_TTL_MS = 15 * 60 * 1000;\n"
                         "export const MAX_QTY = 10; // 5 in the old app\n"
                         "export const WINDOW_SIZE = BASE * 2;\n"),
            "src/f.py": "LIMIT_CENTS = 10_000  # 5 reais\n",
        })
        scan(cls.root, "--no-exec", "--layers", "L9")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def lim(self, name):
        for f in load(self.root, "business_rules")["facts"]:
            if f["data"]["kind"] == "limit" and f["data"]["subject"] == name:
                return f
        raise AssertionError(name)

    def test_expression_evaluated(self):
        f = self.lim("RESERVATION_TTL_MS")
        self.assertEqual(f["data"]["value"], "900000")
        self.assertEqual(f["data"]["expr"], "15 * 60 * 1000")
        self.assertIn("900000", f["claim"])

    def test_comment_not_read_as_value(self):
        self.assertEqual(self.lim("MAX_QTY")["data"]["value"], "10")
        self.assertEqual(self.lim("LIMIT_CENTS")["data"]["value"], "10000")

    def test_non_literal_has_no_value_and_low_confidence(self):
        f = self.lim("WINDOW_SIZE")
        self.assertIsNone(f["data"]["value"])
        self.assertEqual(f["confidence"], "low")


# ---------------------------------------------------------------- Go + SQL (L0/L9)
class GoAndSqlRules(unittest.TestCase):
    """go-polyglot: 1 regra detectada; SQL fora do inventário."""

    @classmethod
    def setUpClass(cls):
        cls.root = build({
            "go.mod": "module example.com/fleet\n\ngo 1.22\n",
            "internal/dispatch/status.go": (
                "package dispatch\n\n"
                "type DeliveryStatus string\n\n"
                "const (\n"
                "\tStatusCreated   DeliveryStatus = \"created\"\n"
                "\tStatusAssigned  DeliveryStatus = \"assigned\"\n"
                "\tStatusDelivered DeliveryStatus = \"delivered\"\n"
                ")\n\n"
                "var allowedTransitions = map[DeliveryStatus][]DeliveryStatus{\n"
                "\tStatusCreated:   {StatusAssigned},\n"
                "\tStatusAssigned:  {StatusDelivered},\n"
                "\tStatusDelivered: {},\n"
                "}\n\n"
                "func CanTransition(from, to DeliveryStatus) bool {\n"
                "\tfor _, s := range allowedTransitions[from] {\n"
                "\t\tif s == to {\n\t\t\treturn true\n\t\t}\n\t}\n\treturn false\n}\n"),
            "internal/dispatch/assign.go": (
                "package dispatch\n\n"
                "// MaxActivePerCourier is the business limit of deliveries a courier carries at once.\n"
                "const MaxActivePerCourier = 3\n\n"
                "func HasRoom(active int) bool { return active < MaxActivePerCourier }\n"),
            "internal/dispatch/assign_test.go": (
                "package dispatch\n\nimport \"testing\"\n\n"
                "func TestHasRoomRespectsCapacity(t *testing.T) {\n"
                "\tif HasRoom(MaxActivePerCourier) {\n\t\tt.Fatal(\"full courier\")\n\t}\n}\n\n"
                "func TestTerminal(t *testing.T) {\n"
                "\tif CanTransition(StatusDelivered, StatusCreated) {\n\t\tt.Fatal(\"terminal\")\n\t}\n}\n"),
            "internal/tracking/eta.go": ("package tracking\n\nconst MinSpeedKmh = 8.0\n\nconst earthRadiusKm = 6371.0\n\n"
                                         "func ETA(km, speed float64) float64 {\n"
                                         "\tif speed < MinSpeedKmh {\n\t\tspeed = MinSpeedKmh\n\t}\n"
                                         "\treturn km / speed\n}\n"),
            "internal/tracking/eta_test.go": ("package tracking\n\nimport \"testing\"\n\n"
                                              "func TestETAUsesSpeedFloor(t *testing.T) {\n"
                                              "\tif ETA(8, 0) != 1 {\n"
                                              "\t\tt.Fatal(\"stopped courier must use MinSpeedKmh\")\n\t}\n}\n"),
            "migrations/0002_status.up.sql": ("-- enum\n"
                                              "CREATE TYPE delivery_status AS ENUM ('created', 'assigned', 'delivered');\n"),
            "migrations/0003_cap.up.sql": ("CREATE TABLE courier_load (\n    active integer NOT NULL,\n"
                                           "    CONSTRAINT courier_load_max_active CHECK (active BETWEEN 0 AND 3)\n);\n"),
            "deploy/lib.sh": "#!/usr/bin/env bash\nset -euo pipefail\nlog() { echo \"$1\"; }\n",
            "deploy/rollback.sh": "#!/usr/bin/env bash\nset -euo pipefail\necho rollback\n",
            "deploy/migrate.sh": ("#!/usr/bin/env bash\nset -euo pipefail\n"
                                  "die() { echo \"$1\" >&2; exit 1; }\n"
                                  "[ \"$a\" = \"$b\" ] || die \"migration $v was edited after being applied (sha mismatch)\"\n"),
        })
        scan(cls.root, "--no-exec", "--layers", "L0,L9")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def facts(self):
        return load(self.root, "business_rules")["facts"]

    def by(self, kind, subject):
        for f in self.facts():
            if f["data"]["kind"] == kind and f["data"]["subject"] == subject:
                return f
        raise AssertionError("%s %s ausente: %s" % (kind, subject, [x["id"] for x in self.facts()]))

    def test_go_camelcase_constants(self):
        f = self.by("limit", "MaxActivePerCourier")
        self.assertEqual(f["data"]["value"], "3")
        self.assertIn("internal/dispatch/assign_test.go", f["claim"])
        self.assertEqual(self.by("limit", "MinSpeedKmh")["data"]["value"], "8.0")
        self.assertFalse([x for x in self.facts() if x["data"]["subject"] == "earthRadiusKm"])

    def test_identifier_inside_string_is_not_a_reference(self):
        f = self.by("limit", "MinSpeedKmh")
        self.assertNotEqual(f["data"]["coverage"], "reference")  # o nome só aparece na mensagem do t.Fatal
        self.assertEqual(f["data"]["coverage"], "asserted")  # `if ETA(8, 0) != 1 { t.Fatal }` confere o valor
        self.assertEqual(f["data"]["test"].split(":")[0], "internal/tracking/eta_test.go")

    def test_state_referenced_through_members(self):
        s = self.by("state", "DeliveryStatus")
        self.assertEqual(s["data"]["coverage"], "reference")

    def test_go_transition_map_and_typed_enum(self):
        t = self.by("transition", "allowedTransitions")
        self.assertIn(["StatusCreated", "StatusAssigned"], t["data"]["value"])
        self.assertIn("internal/dispatch/assign_test.go", t["claim"])
        s = self.by("state", "DeliveryStatus")
        self.assertEqual(s["data"]["value"], ["StatusCreated", "StatusAssigned", "StatusDelivered"])

    def test_sql_enum_and_check(self):
        e = self.by("state", "delivery_status")
        self.assertEqual(e["data"]["value"], ["created", "assigned", "delivered"])
        c = self.by("constraint", "courier_load_max_active")
        self.assertIn("BETWEEN 0 AND 3", c["claim"])

    def test_shell_die_with_mismatch(self):
        self.assertTrue(rules_at(self.root, "deploy/migrate.sh", 4))

    def test_shell_strict_mode_reads_grouped_o(self):
        scan(self.root, "--no-exec", "--layers", "L3")
        f = [x for x in load(self.root, "conventions")["facts"] if x["id"] == "conv.shell.strict-mode"]
        self.assertIn("set -euo pipefail", f[0]["claim"])

    def test_sql_in_inventory(self):
        ids = [f["id"] for f in load(self.root, "inventory")["facts"]]
        self.assertIn("inv.lang.sql", ids)


class ConventionWording(unittest.TestCase):
    """`require_env` relatado como "exceção snake_case" a uma maioria "lowercase" (snake é lowercase)."""

    def test_lowercase_dominant_merges_into_snake_case(self):
        from scan.l3_conventions import COMPAT, Counter, style_of
        c = Counter("naming.function.shell", "nomes de funções em shell")
        for i, name in enumerate(["die", "log", "warn", "require_env", "load_cfg"]):
            c.add("deploy/lib.sh", i + 1, style_of(name))
        s = c.summarize(COMPAT)
        self.assertEqual(s["dominant"], "snake_case")
        self.assertEqual(s["exceptions_total"], 0)
        self.assertEqual(s["level"], "lei")


if __name__ == "__main__":
    unittest.main()
