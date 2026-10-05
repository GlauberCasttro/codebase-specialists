"""team.json sintético (2 devs, 1 gate, 1 qa) + facts/ mínimos, num repo temporário."""
import json
import os
import tempfile
from pathlib import Path


def team():
    return {
        "schema_version": 1,
        "repo": {"name": "loja", "commit": "abc123", "root": "/tmp/loja"},
        "platforms": ["claude-code", "cursor", "copilot", "codex"],
        "veredito_enum": ["PASS", "FAIL", "NEEDS_SPECIALIST"],
        "core": {"lines": [
            {"text": "Testes: `python3 -m unittest discover -s tests` (exit 0 em 1,2 s)", "facts": ["ops.test"]},
            {"text": "Lint: `ruff check src` (exit 0)", "facts": ["ops.lint"]},
        ]},
        "agents": [
            {
                "name": "dev-billing", "kind": "dev",
                "territory": ["src/billing/**"], "reads": ["src/shared/**"],
                "tools": ["Read", "Grep", "Glob", "Bash", "Edit", "Write"], "model": "inherit",
                "card": {
                    "description": "Use para mudar cobrança: cálculo de total, cupons e boletos em src/billing.",
                    "mission": "Mantém o cálculo de cobrança em src/billing correto e coberto por teste.",
                    "knows": [{"text": "Valores monetários são int em centavos (`src/billing/money.py`)",
                               "facts": ["conv.money.cents"]}],
                    "refuses": [{"text": "nunca usa float para dinheiro", "why": "arredondamento quebrou totais",
                                 "facts": ["hist.fix.f00"]}],
                    "done_when": "`python3 -m unittest tests.test_billing` sai 0",
                    "playbooks": [{"title": "Novo tipo de cupom",
                                   "steps": ["Adicione a regra em `src/billing/coupons.py`",
                                             "Cubra em `tests/test_billing.py`"]}],
                    "rules": [{"text": "Sem import de src/web em src/billing", "check": "lint-imports",
                               "facts": ["arch.layers"]}],
                    "footguns": [{"text": "Cupom aplicado depois do frete dobrou desconto",
                                  "facts": ["hist.fix.f00"]}],
                    "anchors": ["src/billing/total.py"],
                },
                "facts_used": ["conv.money.cents"], "invariants": ["rule.no-float-money"],
            },
            {
                "name": "dev-web", "kind": "dev",
                "territory": ["src/web/**"], "reads": [],
                "tools": ["Read", "Grep", "Glob", "Bash", "Edit", "Write"], "model": "sonnet",
                "card": {
                    "description": "Use para mudar rotas HTTP e templates em src/web.",
                    "mission": "Mantém as rotas de src/web finas, delegando regra a src/billing.",
                    "knows": [], "refuses": [{"text": "Calcular preço na rota", "why": "regra mora em billing"}],
                    "done_when": "`python3 -m unittest tests.test_web` sai 0",
                    "playbooks": [], "rules": [], "footguns": [], "anchors": [],
                },
                "facts_used": [], "invariants": [],
            },
            {
                "name": "reviewer", "kind": "gate", "territory": [], "reads": ["src/**"],
                "tools": ["Read", "Grep", "Glob", "Bash"], "model": "inherit",
                "card": {
                    "description": "Use para revisar uma entrega antes do aceite; devolve PASS, FAIL ou NEEDS_SPECIALIST.",
                    "mission": "Revisa diffs contra invariantes e testes; não edita.",
                    "knows": [], "refuses": [{"text": "editar código", "why": "gate não pode ser autor"}],
                    "done_when": "veredito gravado com evidência",
                    "playbooks": [], "rules": [], "footguns": [], "anchors": [],
                },
                "facts_used": [], "invariants": ["rule.no-float-money"],
            },
            {
                "name": "qa", "kind": "ops", "territory": ["tests/**"], "reads": ["src/**"],
                "tools": ["Read", "Grep", "Glob", "Bash", "Edit", "Write"], "model": "inherit",
                "card": {
                    "description": "Use para escrever ou consertar testes em tests/.",
                    "mission": "Mantém tests/ como prova executável das regras.",
                    "knows": [], "refuses": [{"text": "Editar src/", "why": "QA não escreve produção"}],
                    "done_when": "`python3 -m unittest discover -s tests` sai 0",
                    "playbooks": [], "rules": [], "footguns": [], "anchors": [],
                },
                "facts_used": [], "invariants": [],
            },
        ],
    }


def facts():
    return {
        "rules.json": {"facts": [{"id": "rule.no-float-money", "claim": "Nenhum float em src/billing",
                                  "evidence": [{"file": "src/billing/money.py", "line": 1}]}]},
        "glossary.json": {"terms": [
            {"canonical": "Boleto", "definition": "título de cobrança bancária",
             "where": "src/billing/boleto.py:3", "never_use": ["Bill"], "count": 12, "kind": "business"},
            {"canonical": "Cupom", "definition": "desconto aplicado ao total",
             "where": "src/billing/coupons.py:1", "never_use": [], "count": 9, "kind": "business"},
            {"canonical": "Rota", "definition": "handler HTTP", "where": "src/web/app.py:1", "count": 3},
        ]},
        "business_rules.json": {"rules": [
            {"rule": "Cupom é aplicado antes do frete", "where": "src/billing/total.py:10",
             "test": "tests/test_billing.py::test_cupom"},
            {"rule": "Boleto vence em 3 dias úteis", "where": "src/billing/boleto.py:8", "source": "founder"},
        ]},
    }


PRODUCT = ["src/billing/total.py", "src/billing/coupons.py", "src/billing/boleto.py", "src/billing/money.py",
           "src/web/app.py", "src/shared/util.py", "tests/test_billing.py", "tests/test_web.py"]


def scan_facts():
    files = [{"path": p, "category": "product", "lang": "python", "loc": 10 + i} for i, p in enumerate(PRODUCT)]
    files.append({"path": "tests/fixtures/sample.json", "category": "fixture", "lang": "json"})
    return {
        "inventory.json5": {"layer": "inventory", "files": files,
                            "languages": {"python": {"files": 8, "loc": 100, "code": True}},
                            "ignored": {"fixture": {"tests/fixtures/": 1}}, "facts": []},
        "graph.json5": {"layer": "graph",
                        "nodes": [{"path": p, "pagerank": 0.1 if p != "src/billing/money.py" else 0.4, "in": 1}
                                  for p in PRODUCT],
                        "edges": [["src/web/app.py", "src/billing/total.py", 1],
                                  ["src/billing/total.py", "src/billing/money.py", 1]], "facts": []},
        "stack.json5": {"layer": "stack", "packages": [
            {"eco": "python", "name": "requests", "version": "2.32.3", "source": "requirements.txt",
             "line": 1, "direct": True}], "facts": []},
    }


def knowledge_maps():
    return {
        "deps.json5": {"nodes": [{"id": "dev-billing"}, {"id": "dev-web"}],
                       "edges": [{"from": "dev-web", "to": "dev-billing", "count": 1}]},
        "collision.json5": {"nodes": [{"id": "dev-billing"}, {"id": "dev-web"}],
                            "edges": [["dev-web", "dev-billing"]]},
    }


def make_repo():
    root = Path(tempfile.mkdtemp(prefix="cs-emit-"))
    for p in PRODUCT:
        (root / p).parent.mkdir(parents=True, exist_ok=True)
        (root / p).write_text("x = 1\n")
    write_team(root, team())
    fdir = root / ".swarm" / "facts"
    fdir.mkdir(parents=True, exist_ok=True)
    for name, data in list(facts().items()) + list(scan_facts().items()):
        name = name if name.endswith(".json5") else name + "5"
        (fdir / name).write_text("// fixture\n" + json.dumps(data, ensure_ascii=False))
    kdir = root / ".swarm" / "knowledge"
    kdir.mkdir(parents=True, exist_ok=True)
    for name, data in knowledge_maps().items():
        (kdir / name).write_text("// fixture (construtor de team)\n" + json.dumps(data, ensure_ascii=False))
    return str(os.path.realpath(str(root)))


def write_team(root, data):
    d = Path(root) / ".swarm"
    d.mkdir(parents=True, exist_ok=True)
    (d / "team.json5").write_text("// fixture\n" + json.dumps(data, ensure_ascii=False, indent=2))
