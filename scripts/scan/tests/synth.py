"""Repositórios sintéticos para os testes do scan (tempfile + git real)."""

import os
import subprocess
import sys
import tempfile

SCRIPTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
CS = os.path.join(SCRIPTS, "cs.py")

GIT_ENV = {"GIT_AUTHOR_NAME": "Ana", "GIT_AUTHOR_EMAIL": "ana@x", "GIT_COMMITTER_NAME": "Ana",
           "GIT_COMMITTER_EMAIL": "ana@x", "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
           "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}


def write(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write(text)


def git(root, *args):
    env = dict(os.environ, **GIT_ENV)
    subprocess.run(["git", "-C", root] + list(args), check=True, env=env,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def commit(root, msg):
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", msg)


BASE = {
    "Makefile": ".PHONY: test lint\ntest:\n\tpython3 -m unittest discover -s tests\n\nghost:\n\t@true\n",
    "README.md": ("# Loja\n\nLoja de pedidos.\n\nRode `make test` e `make deploy-prod`.\n"
                  "Veja `src/shop/orders.py` e `src/shop/nao_existe.py`. Usa requests 2.31.\n\n"
                  "## Glossário\n\n- **Pedido**: compra confirmada de um cliente\n"),
    "requirements.txt": "requests==2.31.0\nflask==3.0.0\n",
    "src/shop/__init__.py": "",
    "src/shop/orders.py": (
        "from enum import Enum\n"
        "from src.shop.money import Money\n\n"
        "MAX_ITEMS_PER_ORDER = 20\n\n\n"
        "class OrderStatus(Enum):\n"
        "    DRAFT = 1\n"
        "    PAID = 2\n"
        "    SHIPPED = 3\n\n\n"
        "class OrderItem:\n"
        "    pass\n\n\n"
        "def add_item(order_items, item):\n"
        "    if len(order_items) >= MAX_ITEMS_PER_ORDER:\n"
        "        raise ValueError(\"order cannot exceed max items\")\n"
        "    order_items.append(item)\n"
        "    return order_items\n"),
    "src/shop/money.py": "class Money:\n    def __init__(self, cents: int) -> None:\n        self.cents = cents\n",
    "src/billing/invoice.py": "from src.shop.orders import OrderItem\nfrom src.shop.money import Money\n\n\nclass Invoice:\n    pass\n",
    "tests/test_orders.py": (
        "import unittest\n\nfrom src.shop.orders import add_item, MAX_ITEMS_PER_ORDER\n\n\n"
        "class T(unittest.TestCase):\n"
        "    def test_order_cannot_exceed_max_items(self):\n"
        "        with self.assertRaises(ValueError) as cm:\n"
        "            add_item([0] * MAX_ITEMS_PER_ORDER, 1)\n"
        "        self.assertIn(\"order cannot exceed\", str(cm.exception))\n\n"
        "    def test_add(self):\n"
        "        self.assertEqual(add_item([], 1), [1])\n"),
    "tests/fixtures/fake_product/app.py": "import django\nclass FixtureOnly:\n    pass\n",
    "tests/fixtures/fake_product/package-lock.json": '{"packages": {"node_modules/leftpad": {"version": "9.9.9"}}}',
    "scripts/check.sh": "#!/bin/bash\nset -euo pipefail\n. \"$(dirname \"$0\")/lib.sh\"\n",
    "scripts/lib.sh": "#!/bin/bash\nset -euo pipefail\nsay() { echo \"$1\"; }\n",
}


def make_repo(extra=None, git_init=True):
    root = tempfile.mkdtemp(prefix="cs-scan-")
    files = dict(BASE)
    files.update(extra or {})
    for rel, text in files.items():
        write(root, rel, text)
    if git_init:
        git(root, "init", "-q")
        commit(root, "init: loja")
        write(root, "src/shop/orders.py", files["src/shop/orders.py"] + "\n# ajuste\n")
        write(root, "src/shop/money.py", files["src/shop/money.py"] + "\n# ajuste\n")
        commit(root, "fix: bug no limite de itens porque o total estourava sem validação")
    return root


def cs(root, *args):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run([sys.executable, CS, "--target", root] + list(args), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=env, timeout=600)
