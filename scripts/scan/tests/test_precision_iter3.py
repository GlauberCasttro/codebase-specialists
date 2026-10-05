"""Regressões de PRECISÃO do scan — iteração 3 (PLANO-ITER3.json5, frente_scan).

Cada classe reproduz um defeito medido nos evals da iteração 2 (py-billing, ts-shop, go-polyglot)
num repositório sintético mínimo. Princípio: fato errado é pior que fato ausente.
"""

import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_precision import build, load, scan  # noqa: E402

from cslib import paths  # noqa: E402


def facts(root, layer):
    return load(root, layer)["facts"]


def by_id(root, layer):
    return {f["id"]: f for f in facts(root, layer)}


# ---------------------------------------------------------------- L10 instruções de agente
class AgentInstructionsAreAList(unittest.TestCase):
    """CLAUDE.md com 3 instruções virava 1 fato (só a linha com 'não'); bullet com continuação na
    linha de baixo era cortado e uma regra condicional virava absoluta (AGENTS.md do ts-shop)."""

    CLAUDE = ("# Notas do time\n\n"
              "- Fale com a Carla (contabilidade) antes de mexer no plano de contas em `src/app.py`.\n"
              "- Fechamento mensal roda no dia 1: não faça deploy entre dia 28 e dia 2.\n"
              "- Toda mudança em valor monetário precisa de um teste com centavo quebrado.\n"
              "- O app antigo ainda manda `driver_id`; o backend usa `courier_id`.\n"
              "\n"
              "<!-- codebase-specialists:begin -->\n"
              "## Núcleo\n\n- Nunca invente isto: é bloco gerado pela própria skill.\n"
              "<!-- codebase-specialists:end -->\n")
    AGENTS = ("# Notes for coding agents\n\n"
              "- We deploy on Fridays only after review. Never bump `express` to 5.x\n"
              "  without the api owner: middleware error handling changed.\n"
              "- Prefer small PRs: one workspace per PR unless the change is a contract.\n")
    MDC = ("---\ndescription: regras do billing\nglobs: src/billing/**,src/shared/**\nalwaysApply: false\n---\n"
           "Só com aprovação do financeiro altere a tabela de alíquotas.\n")
    COPILOT = "Sempre rode `make test` antes de abrir PR.\n"
    GENERATED = ("---\npaths:\n  - \"src/**\"\n---\n"
                 "<!-- codebase-specialists:generated; não edite -->\n\n- Nunca leia isto como instrução do time.\n")

    @classmethod
    def setUpClass(cls):
        cls.root = build({
            "src/app.py": "X = 1\n",
            "CLAUDE.md": cls.CLAUDE,
            "AGENTS.md": cls.AGENTS,
            ".cursor/rules/billing.mdc": cls.MDC,
            ".github/copilot-instructions.md": cls.COPILOT,
            ".claude/rules/cs-dev.md": cls.GENERATED,
        })
        scan(cls.root, "--no-exec", "--layers", "L10")
        cls.instr = {f["id"]: f for f in facts(cls.root, "project_docs") if f["id"].startswith("docs.instr.")}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def of(self, rel):
        return [f for f in self.instr.values() if f["evidence"][0]["file"] == rel]

    def test_every_block_of_claude_md_is_a_fact(self):
        got = self.of("CLAUDE.md")
        self.assertEqual(sorted(f["evidence"][0]["line"] for f in got), [3, 4, 5, 6])
        texts = " ".join(f["claim"] for f in got)
        for needle in ("Fale com a Carla", "não faça deploy", "Toda mudança em valor monetário", "driver_id"):
            self.assertIn(needle, texts)

    def test_note_is_kept_but_marked_as_note(self):
        note = [f for f in self.of("CLAUDE.md") if f["evidence"][0]["line"] == 6][0]
        self.assertFalse(note["data"]["imperative"])
        self.assertTrue(note["claim"].startswith("Nota do time"))
        carla = [f for f in self.of("CLAUDE.md") if f["evidence"][0]["line"] == 3][0]
        self.assertTrue(carla["data"]["imperative"])

    def test_conditional_continuation_not_cut(self):
        got = self.of("AGENTS.md")
        self.assertEqual(len(got), 2)
        bump = [f for f in got if "express" in f["claim"]][0]
        self.assertIn("without the api owner: middleware error handling changed.", bump["claim"])
        self.assertEqual(bump["data"]["end_line"], 4)
        self.assertEqual(bump["confidence"], "high")

    def test_cursor_and_copilot_rules_with_scope(self):
        mdc = self.of(".cursor/rules/billing.mdc")
        self.assertEqual(len(mdc), 1)
        self.assertEqual(mdc[0]["scope"], ["src/billing/**", "src/shared/**"])
        self.assertIn("Só com aprovação", mdc[0]["claim"])
        self.assertEqual(len(self.of(".github/copilot-instructions.md")), 1)

    def test_own_generated_content_is_not_read_back(self):
        self.assertFalse(any("Nunca invente isto" in f["claim"] for f in self.instr.values()))
        self.assertEqual(self.of(".claude/rules/cs-dev.md"), [])


# ---------------------------------------------------------------- L6 ADR
class AdrDecisionsComplete(unittest.TestCase):
    """O fato do ADR cortava a seção de decisão em 300 caracteres (go-polyglot perdeu 3 de 5 decisões) e
    lia só o 1º parágrafo."""

    ADR = ("# ADR 0001 — Migrações append-only\n\n- Status: aceito (2025-02-12)\n\n## Contexto\nX quebrou.\n\n"
           "## Decisão\n"
           "- Migração aplicada **nunca** é editada. `deploy/migrate.sh` grava o sha256 de cada arquivo e aborta\n"
           "  se um arquivo aplicado mudar.\n"
           "- Novo valor de enum = nova migração com `ALTER TYPE delivery_status ADD VALUE`.\n"
           "- Os valores de `DeliveryStatus` em `internal/dispatch/status.go` espelham o enum `delivery_status`.\n"
           "- Down migrations existem para dev; **nunca** rodam em produção (`deploy/rollback.sh` só troca imagem).\n"
           "- Timestamps são `timestamptz` gravados em UTC.\n\n"
           "Parágrafo final da decisão: revisão do DBA para enum.\n\n"
           "## Consequências\nNada a dizer aqui.\n")

    @classmethod
    def setUpClass(cls):
        cls.root = build({"src/app.py": "X = 1\n", "docs/adr/0001-migrations.md": cls.ADR,
                          "docs/adr/0002-one.md": "# ADR 0002 — Um\n\nStatus: aceito\n\n## Decisão\nFaz só uma coisa.\n"})
        scan(cls.root, "--no-exec", "--layers", "L6")
        cls.f = by_id(cls.root, "rationale")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_one_fact_per_decision_item_with_full_text(self):
        base = "rat.adr.docs-adr-0001-migrations.md"
        items = sorted(k for k in self.f if k.startswith(base + ".d"))
        self.assertEqual(len(items), 6)
        claims = " ".join(self.f[k]["claim"] for k in items)
        for needle in ("aborta se um arquivo aplicado mudar.", "ALTER TYPE delivery_status ADD VALUE",
                       "espelham o enum", "nunca rodam em produção (`deploy/rollback.sh` só troca imagem).",
                       "gravados em UTC.", "revisão do DBA para enum."):
            self.assertIn(needle, claims)
        self.assertNotIn("Nada a dizer", claims)
        d4 = [self.f[k] for k in items if "Down migrations" in self.f[k]["claim"]][0]
        self.assertEqual(d4["evidence"][0]["line"], 13)

    def test_summary_fact_not_truncated(self):
        main = self.f["rat.adr.docs-adr-0001-migrations.md"]
        self.assertIn("gravados em UTC.", main["claim"])
        self.assertEqual(main["data"]["decision_items"], 6)

    def test_single_paragraph_adr_has_no_item_facts(self):
        self.assertIn("Faz só uma coisa.", self.f["rat.adr.docs-adr-0002-one.md"]["claim"])
        self.assertFalse(any(k.startswith("rat.adr.docs-adr-0002-one.md.d") for k in self.f))


# ---------------------------------------------------------------- L2/L4 golangci
GO_MOD = "module example.com/fleet\n\ngo 1.22\n\nrequire github.com/jackc/pgx/v5 v5.6.0\n"
GOLANGCI = ("run:\n  timeout: 3m\nlinters:\n  enable:\n    - errcheck\n    - govet\n    - staticcheck\n"
            "    - gofmt\n    - goimports\n    - depguard\nlinters-settings:\n  depguard:\n    rules:\n"
            "      sql-only-in-storage:\n        files: [\"!**/internal/storage/**\"]\n        deny:\n"
            "          - pkg: github.com/jackc/pgx/v5\n            desc: \"SQL lives only in internal/storage\"\n")
STORE = "package storage\n\nimport (\n\t\"context\"\n\n\t\"github.com/jackc/pgx/v5\"\n)\n\nvar _ = pgx.Connect\nvar _ = context.TODO\n"
HANDLER_BAD = "package httpapi\n\nimport \"github.com/jackc/pgx/v5\"\n\nvar _ = pgx.Connect\n"


class GolangciDepguard(unittest.TestCase):
    """L2 dizia 'nenhuma arquitetura declarada' com depguard no .golangci.yml; L4 contava 7 linters (o
    `- pkg:` do depguard entrava na conta) quando o arquivo habilita 6."""

    @classmethod
    def setUpClass(cls):
        cls.root = build({"go.mod": GO_MOD, ".golangci.yml": GOLANGCI,
                          "internal/storage/db.go": STORE, "internal/httpapi/h.go": HANDLER_BAD,
                          "cmd/app/main.go": "package main\n\nfunc main() {}\n"})
        scan(cls.root, "--no-exec", "--layers", "L2,L4")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_depguard_boundary_is_declared_architecture(self):
        f = by_id(self.root, "architecture")
        self.assertNotIn("arch.declared.none", f)
        b = f["arch.declared.golangci-depguard.sql-only-in-storage"]
        self.assertIn("github.com/jackc/pgx/v5", b["claim"])
        self.assertEqual(b["evidence"][0], {"file": ".golangci.yml", "line": 14})
        self.assertTrue(b["data"]["enforced"])
        self.assertEqual(b["data"]["violations"], 1)
        self.assertIn("internal/httpapi/h.go:3", b["claim"])
        self.assertNotIn("internal/storage/db.go:", b["claim"].split("violação")[1].split(";")[0])

    def test_linter_count(self):
        g = [x for x in facts(self.root, "rules") if x["id"] == "rules.cfg.golangci"][0]
        self.assertIn("6 linters habilitados", g["claim"])
        self.assertNotIn("7", g["claim"])


class DepguardNotEnabled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = build({"go.mod": GO_MOD, ".golangci.yml": GOLANGCI.replace("    - depguard\n", ""),
                          "internal/storage/db.go": STORE})
        scan(cls.root, "--no-exec", "--layers", "L2,L4")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_rule_declared_but_not_running_is_medium_and_says_so(self):
        b = by_id(self.root, "architecture")["arch.declared.golangci-depguard.sql-only-in-storage"]
        self.assertEqual(b["confidence"], "medium")
        self.assertIn("não está habilitado", b["claim"])
        g = [x for x in facts(self.root, "rules") if x["id"] == "rules.cfg.golangci"][0]
        self.assertIn("5 linters habilitados", g["claim"])

    def test_unreadable_yaml_never_counts(self):
        root = build({"go.mod": GO_MOD, ".golangci.yml": "linters: &x\n  enable:\n    - errcheck\n",
                      "a.go": "package a\n"})
        try:
            scan(root, "--no-exec", "--layers", "L2,L4")
            g = [x for x in facts(root, "rules") if x["id"] == "rules.cfg.golangci"][0]
            self.assertIn("não lido", g["claim"])
            self.assertNotRegex(g["claim"], r"\d+ linters")
            b = [x for x in facts(root, "architecture") if x["id"].startswith("arch.declared.golangci")][0]
            self.assertEqual(b["confidence"], "low")
        finally:
            shutil.rmtree(root, ignore_errors=True)


class EslintAndRuffBoundaries(unittest.TestCase):
    ESLINT = ('export default [\n  { rules: { "no-console": "error" } },\n  {\n'
              '    files: ["apps/web/**/*.{ts,tsx}"],\n    rules: {\n'
              '      "no-restricted-imports": ["error", {\n'
              '        "patterns": [{ "group": ["@shop/api", "@shop/api/*"], "message": "web talks HTTP only." }]\n'
              '      }]\n    }\n  }\n];\n')
    RUFF = ('line-length = 100\n\n[lint.flake8-tidy-imports.banned-api]\n'
            '"decimal.getcontext".msg = "do not mutate the global decimal context"\n')

    @classmethod
    def setUpClass(cls):
        cls.root = build({"eslint.config.mjs": cls.ESLINT, "ruff.toml": cls.RUFF,
                          "apps/web/src/a.ts": "export const a = 1;\n", "src/x.py": "X = 1\n"})
        scan(cls.root, "--no-exec", "--layers", "L2")
        cls.f = by_id(cls.root, "architecture")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_eslint_boundary_with_files_and_targets(self):
        b = [v for k, v in self.f.items() if k.startswith("arch.declared.eslint-restricted-imports")][0]
        self.assertEqual(b["data"]["files"], ["apps/web/**/*.{ts,tsx}"])
        self.assertEqual(b["data"]["deny"], ["@shop/api", "@shop/api/*"])
        self.assertEqual(b["evidence"][0]["line"], 6)

    def test_ruff_banned_api(self):
        b = self.f["arch.declared.ruff-banned-api.banned-api"]
        self.assertIn("decimal.getcontext", b["claim"])
        self.assertEqual(b["evidence"][0]["line"], 4)


# ---------------------------------------------------------------- L9 glossário e linha da guarda
class GlossaryNameMatchesLocation(unittest.TestCase):
    """gloss.delivery dizia 'canônico Deliveries; definido em dispatch/assign.go:25' — linha do
    `type Delivery struct` com o nome do `type Deliveries struct` (fusão por lema)."""

    @classmethod
    def setUpClass(cls):
        cls.root = build({
            "go.mod": "module example.com/fleet\n\ngo 1.22\n",
            "internal/dispatch/assign.go": ("package dispatch\n\n// Delivery is one parcel.\ntype Delivery struct {\n"
                                            "\tID string\n}\n\nfunc NewDelivery() Delivery { return Delivery{} }\n"
                                            "func Copy(d Delivery) Delivery { return d }\n"),
            "internal/storage/deliveries.go": ("package storage\n\nimport \"example.com/fleet/internal/dispatch\"\n\n"
                                               "// Deliveries persists dispatch.Delivery rows.\ntype Deliveries struct{}\n\n"
                                               "func (s *Deliveries) Create(d dispatch.Delivery) error { return nil }\n"),
        })
        scan(cls.root, "--no-exec", "--layers", "L9")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_canonical_name_and_location_agree(self):
        g = by_id(self.root, "glossary")["gloss.delivery"]
        self.assertEqual(g["data"]["canonical"], "Delivery")
        self.assertIn("canônico Delivery,", g["claim"])
        self.assertEqual(g["evidence"][0], {"file": "internal/dispatch/assign.go", "line": 4})
        self.assertIn("Deliveries também definida(s) em internal/storage/deliveries.go:6", g["claim"])


class GuardLineCitedWhereItIs(unittest.TestCase):
    """Regra de validação citava o `if` na linha do throw (15) — o `if` está na 14."""

    @classmethod
    def setUpClass(cls):
        cls.root = build({
            "src/catalog.ts": ("export class Catalog {\n  upsert(price: number): void {\n"
                               "    if (!Number.isInteger(price) || price < 0) {\n"
                               "      throw new RangeError(\"price must be a non-negative integer\");\n"
                               "    }\n  }\n}\n"),
        })
        scan(cls.root, "--no-exec", "--layers", "L9")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_if_line_and_throw_line(self):
        r = [f for f in facts(self.root, "business_rules") if f["id"].startswith("brule.validation.")][0]
        self.assertIn("src/catalog.ts:3-4", r["claim"])
        self.assertIn("(linha 3)", r["claim"])
        self.assertIn({"file": "src/catalog.ts", "line": 3}, r["evidence"])
        self.assertEqual(r["evidence"][0], {"file": "src/catalog.ts", "line": 4})


# ---------------------------------------------------------------- examples/** (L0, cslib.paths)
class ExamplesAreNotFixtures(unittest.TestCase):
    """examples/python-client (cliente de parceiro) era fixture → ninguém podia ser dono."""

    def test_classify(self):
        self.assertEqual(paths.classify("examples/python-client/client.py"), paths.CAT_EXAMPLE)
        self.assertEqual(paths.classify("samples/demo/main.go"), paths.CAT_EXAMPLE)
        self.assertEqual(paths.classify("tests/examples/case1.json"), paths.CAT_FIXTURE)
        self.assertEqual(paths.classify("src/pkg/testdata/examples/a.txt"), paths.CAT_FIXTURE)
        self.assertEqual(paths.classify("examples/node_modules/x/index.js"), paths.CAT_VENDOR)
        self.assertNotIn(paths.CAT_EXAMPLE, paths.IGNORED_CATEGORIES)
        self.assertIn(paths.CAT_EXAMPLE, paths.NOT_ANALYZED_CATEGORIES)

    def test_inventory_lists_examples_and_stack_ignores_them(self):
        root = build({"go.mod": "module example.com/fleet\n\ngo 1.22\n", "main.go": "package main\n\nfunc main() {}\n",
                      "examples/python-client/client.py": "import requests\n\n\ndef f():\n    return requests.get('x')\n",
                      "examples/python-client/requirements.txt": "requests==2.31.0\n"})
        try:
            scan(root, "--no-exec", "--layers", "L0,L8")
            inv = load(root, "inventory")
            cats = {e["path"]: e["category"] for e in inv["files"]}
            self.assertEqual(cats["examples/python-client/client.py"], "example")
            ex = [f for f in inv["facts"] if f["id"].startswith("inv.example.")]
            self.assertEqual(len(ex), 1)
            self.assertEqual(ex[0]["scope"], ["examples/**"])
            self.assertIn("pode ter dono", ex[0]["claim"])
            stack = load(root, "stack")
            names = [p["name"] for p in stack["stack"]["packages"]] if "stack" in stack else []
            self.assertNotIn("requests", names)
            self.assertNotIn("requests", repr([f["claim"] for f in stack["facts"]]))
        finally:
            shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------- L3 indentação (achado no spot-check)
class IndentByStepNotWidth(unittest.TestCase):
    """App.tsx com 2 espaços e JSX aninhado virava exceção '4 espaços' (contava linhas com 4+ espaços)."""

    def test_unit(self):
        from scan.l3_conventions import indent_unit
        tsx = ["export function App() {", "  return (", "    <main>", "      <h1>x</h1>", "    </main>",
               "  );", "}"]
        self.assertEqual(indent_unit(tsx), ("2 espaços", 2))
        py = ["class A:", "    def f(self,", "          x):", "        return x"]
        self.assertEqual(indent_unit(py)[0], "4 espaços")
        self.assertEqual(indent_unit(["package a", "func f() {", "\treturn", "}"]), ("tabs", 3))
        self.assertEqual(indent_unit(["x = 1", "y = 2"]), (None, None))


# ---------------------------------------------------------------- L1 comunidade (achado no spot-check)
class CommunityPrefixNotOverclaimed(unittest.TestCase):
    """'prefixo comum src/billing' numa comunidade com 5 arquivos em tests/."""

    def test_majority_prefix_is_not_common(self):
        root = build({
            "src/app/a.py": "from src.app import b\n", "src/app/b.py": "from src.app import c\n",
            "src/app/c.py": "X = 1\n", "tests/test_a.py": "from src.app import a\nfrom src.app import b\n",
        })
        try:
            scan(root, "--no-exec", "--layers", "L1")
            cs = [f for f in facts(root, "graph") if f["id"].startswith("graph.community.")]
            self.assertTrue(cs)
            for c in cs:
                if "prefixo comum '" in c["claim"]:
                    pref = c["claim"].split("prefixo comum '")[1].split("'")[0]
                    self.assertTrue(all(s.startswith(pref + "/") for s in c["scope"]), c)
            mixed = [c for c in cs if "tests" in c["claim"] or any(s.startswith("tests/") for s in c["scope"])]
            self.assertTrue(mixed)
            for c in mixed:
                self.assertIn("sem prefixo comum", c["claim"])
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
