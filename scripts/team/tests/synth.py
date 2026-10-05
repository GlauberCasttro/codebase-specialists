"""Repo sintético + fatos sintéticos (formato §4) para os testes de team e probes."""
import json
import os
import shutil
import sys
import tempfile

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

SHA = "abc1234def5678901234567890abcdef12345678"

FILES = {
    "src/billing/__init__.py": "",
    "src/billing/invoice.py": "from src.shared.money import Money\n\nclass Invoice:\n    \"\"\"Fatura.\"\"\"\n"
                              "    pass\n\n\n\n\ndef charge_customer(invoice, card):\n    return Money(invoice)\n",
    "src/billing/tax.py": "from src.shared.money import Money\n\ndef compute_tax(amount):\n    return Money(amount)\n",
    "src/billing/refund.py": "from src.shared.money import Money\n\n# reembolso\nREFUND_WINDOW_DAYS = 30\n"
                             "def refund(order):\n    return order\n",
    "src/orders/__init__.py": "",
    "src/orders/order.py": "class Order:\n    pass\n",
    "src/orders/cart.py": "from src.shared.db import Session\n\ndef add_item(cart, item):\n    return cart\n",
    "src/orders/checkout.py": "from src.billing.invoice import charge_customer\nfrom src.shared.money import Money\n\n\n"
                              "def checkout(cart):\n    return charge_customer(cart, None)\n",
    "src/catalog/__init__.py": "",
    "src/catalog/product.py": "class Product:\n    pass\n",
    "src/catalog/search.py": "\ndef search_products(q):\n    return []\n",
    "src/catalog/price.py": "from src.shared.money import Money\n\ndef list_price(p):\n    return Money(p)\n",
    "src/shared/__init__.py": "",
    "src/shared/money.py": "class Money:\n    def __init__(self, cents):\n        self.cents = cents\n",
    "src/shared/db.py": "class Session:\n    pass\n",
    "src/tiny/x.py": "from src.catalog.price import list_price\n",
    "web/index.html": "<html></html>\n",
    "web/app.tsx": "export const App = () => null;\n",
    "web/style.css": "body {}\n",
    "tests/test_billing.py": "import unittest\n",
    "tests/test_orders.py": "import unittest\n",
    "db/migrations/001_init.sql": "create table invoice (id int);\n",
    ".github/workflows/ci.yml": "on: push\n",
    "Dockerfile": "FROM python:3.11\n",
    "docs/adr/0001-money.md": "# ADR 1\n\nDinheiro em centavos inteiros, nunca float.\n",
    "README.md": "# synth\n",
    "pyproject.toml": "[project]\nname='synth'\n\n[tool.ruff]\nselect=['E']\n\n\nban-float = true\n",
    "Makefile": "test:\n\tpython3 -m unittest discover -s tests\n",
    "fixtures/sample.json": "{}\n",
    ".claude/agents/old.md": "x\n",
}

EDGES = [
    ["src/billing/invoice.py", "src/shared/money.py"], ["src/billing/tax.py", "src/shared/money.py"],
    ["src/billing/refund.py", "src/shared/money.py"], ["src/orders/cart.py", "src/shared/db.py"],
    ["src/orders/checkout.py", "src/billing/invoice.py"], ["src/orders/checkout.py", "src/shared/money.py"],
    ["src/catalog/price.py", "src/shared/money.py"], ["src/tiny/x.py", "src/catalog/price.py"],
]
SYMBOLS = [
    {"name": "Invoice", "kind": "class", "path": "src/billing/invoice.py", "line": 3, "doc": "Fatura."},
    {"name": "charge_customer", "kind": "function", "path": "src/billing/invoice.py", "line": 10,
     "signature": "charge_customer(invoice, card)"},
    {"name": "compute_tax", "kind": "function", "path": "src/billing/tax.py", "line": 3,
     "signature": "compute_tax(amount)"},
    {"name": "refund", "kind": "function", "path": "src/billing/refund.py", "line": 5, "signature": "refund(order)"},
    {"name": "Order", "kind": "class", "path": "src/orders/order.py", "line": 1},
    {"name": "add_item", "kind": "function", "path": "src/orders/cart.py", "line": 3,
     "signature": "add_item(cart, item)"},
    {"name": "checkout", "kind": "function", "path": "src/orders/checkout.py", "line": 5,
     "signature": "checkout(cart)"},
    {"name": "Product", "kind": "class", "path": "src/catalog/product.py", "line": 1},
    {"name": "search_products", "kind": "function", "path": "src/catalog/search.py", "line": 2,
     "signature": "search_products(q)"},
    {"name": "list_price", "kind": "function", "path": "src/catalog/price.py", "line": 3,
     "signature": "list_price(p)"},
    {"name": "Money", "kind": "class", "path": "src/shared/money.py", "line": 1},
    {"name": "Session", "kind": "class", "path": "src/shared/db.py", "line": 1},
]


def fact(fid, layer, claim, evidence, scope=None, data=None):
    f = {"id": fid, "layer": layer, "claim": claim, "evidence": evidence, "confidence": "high",
         "origin": "mechanical", "scope": scope or [], "fingerprint": "x"}
    if data is not None:
        f["data"] = data
    return f


def layers():
    inv = {"facts": [fact("inv.files", "inventory", "30 arquivos", [{"cmd": "git ls-files", "exit": 0}])],
           "files": [{"path": p, "class": ("fixture" if p.startswith("fixtures/") else
                                           "reserved" if p.startswith(".claude/") else "product")}
                     for p in sorted(FILES)],
           "manifests": ["pyproject.toml"]}
    graph = {"facts": [fact("graph.pagerank", "graph", "Money é o mais central",
                            [{"file": "src/shared/money.py", "line": 1}])],
             "edges": EDGES, "symbols": SYMBOLS,
             "nodes": [{"id": p, "community": 0} for p in sorted(FILES) if p.endswith(".py")]}
    rules = {"facts": [
        fact("rules.neg.no-float-money", "rules", "Nenhum float( em src/billing (0 ocorrências)",
             [{"file": "pyproject.toml", "line": 8}], ["src/billing/**"],
             {"kind": "negative_invariant", "pattern": "float(", "count": 0, "tool": "ruff"}),
        fact("rules.lint.ruff-e", "rules", "ruff seleciona E em src", [{"file": "pyproject.toml", "line": 5}],
             ["src/**"], {"kind": "lint", "tool": "ruff"}),
    ]}
    ops = {"facts": [
        fact("ops.test.unittest", "operations", "testes unittest passam",
             [{"cmd": "python3 -m unittest discover -s tests", "exit": 0}], [],
             {"command": "python3 -m unittest discover -s tests", "status": "verified", "kind": "test",
              "purpose": "a suíte de testes unitários"}),
        fact("ops.lint.ruff", "operations", "lint", [{"file": "pyproject.toml", "line": 4}], ["src/**"],
             {"command": "ruff check src", "status": "verified", "kind": "lint", "purpose": "o lint de src"}),
    ]}
    hist = {"facts": [fact("hist.fix.abc1234", "history", "fix rounding in tax",
                           [{"file": "src/billing/tax.py", "line": 3}], ["src/billing/**"],
                           {"sha": SHA, "subject": "fix rounding in tax", "files": ["src/billing/tax.py"],
                            "kind": "fix"})]}
    rat = {"facts": [fact("rat.adr.money", "rationale", "Dinheiro em centavos (ADR 1)",
                          [{"file": "docs/adr/0001-money.md", "line": 3}], ["src/**"],
                          {"topic": "representar dinheiro como inteiro", "key_terms": ["centavos"]})]}
    gloss = {"facts": [fact("gl.invoice", "glossary", "Invoice é o termo canônico (9x) vs Bill (1x)",
                            [{"file": "src/billing/invoice.py", "line": 3}], ["src/billing/**"],
                            {"canonical": "Invoice", "category": "business", "synonyms": ["Bill"],
                             "never_use": ["Bill"], "definition": "documento de cobrança"})]}
    br = {"facts": [fact("br.refund.window", "business_rules", "Reembolso só até 30 dias",
                         [{"file": "src/billing/refund.py", "line": 4}], ["src/billing/**"],
                         {"subject": "janela de reembolso", "kind": "limit", "value": "30",
                          "test": "tests/test_billing.py"})]}
    return {"inventory": inv, "graph": graph, "rules": rules, "operations": ops, "history": hist,
            "rationale": rat, "glossary": gloss, "business_rules": br}


def make_repo(extra_files=None, drop_layers=(), extra_edges=None, cochange=None, json_ext=".json5"):
    root = os.path.realpath(tempfile.mkdtemp(prefix="cs-synth-"))
    files = dict(FILES)
    files.update(extra_files or {})
    for p, c in files.items():
        full = os.path.join(root, p)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as fh:
            fh.write(c)
    fd = os.path.join(root, ".swarm", "facts")
    os.makedirs(fd)
    ids = []
    for name, data in layers().items():
        if name in drop_layers:
            continue
        if name == "inventory" and extra_files:
            data["files"] += [{"path": p, "class": "product"} for p in sorted(extra_files)]
        if name == "graph" and extra_edges:
            data["edges"] = data["edges"] + [list(e) for e in extra_edges]
        if name == "history" and cochange:
            data["cochange"] = list(cochange)
        ids += [f["id"] for f in data["facts"]]
        _dump(os.path.join(fd, name + json_ext), data)
    _dump(os.path.join(fd, "index" + json_ext), {"facts": sorted(ids)})
    return root


def _dump(path, data):
    """JSON5 do subconjunto (comentário + chaves sem aspas no topo + vírgula final) para exercitar o leitor."""
    body = json.dumps(data, indent=1, sort_keys=True)
    if path.endswith(".json5"):
        body = "// fato sintético de teste\n" + body.replace('\n "facts":', '\n facts:', 1)
        body = body[:-1].rstrip() + ",\n}" if body.rstrip().endswith("}") and len(data) else body
    with open(path, "w") as fh:
        fh.write(body + "\n")


def cleanup(root):
    shutil.rmtree(root, ignore_errors=True)
