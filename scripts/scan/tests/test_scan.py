"""Testes do scan (L0–L10) em repositórios sintéticos."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synth  # noqa: E402

from cslib import json5io  # noqa: E402
from cslib.paths import STATE_DIR  # noqa: E402


def facts_dir(root):
    return os.path.join(root, STATE_DIR, "facts")


def load(root, name):
    return json5io.load(os.path.join(facts_dir(root), name + ".json5"))


def read_tree(d):
    out = {}
    for r, _, fs in os.walk(d):
        for f in fs:
            p = os.path.join(r, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, d)] = fh.read()
    return out


class ScanNoExec(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = synth.make_repo()
        cls.res = synth.cs(cls.root, "scan", "--no-exec")
        if cls.res.returncode != 0:
            raise AssertionError(cls.res.stderr.decode())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def test_all_outputs_and_index(self):
        names = ["inventory", "graph", "architecture", "conventions", "rules", "history", "rationale",
                 "operations", "stack", "stack_graph", "glossary", "business_rules", "project_docs"]
        index = json5io.load(os.path.join(facts_dir(self.root), "index.json5"))
        for n in names:
            d = load(self.root, n)
            self.assertTrue(d["facts"], n)
            for f in d["facts"]:
                self.assertEqual(index[f["id"]], n)
                self.assertTrue(f["evidence"])

    def test_fixture_ignored_everywhere(self):
        inv = load(self.root, "inventory")
        cats = {f["path"]: f["category"] for f in inv["files"]}
        self.assertEqual(cats["tests/fixtures/fake_product/app.py"], "fixture")
        self.assertIn("fixture", inv["ignored"])
        for name in ("graph", "glossary", "stack", "conventions"):
            with open(os.path.join(facts_dir(self.root), name + ".json5")) as fh:
                text = fh.read()
            self.assertNotIn("FixtureOnly", text, name)
            self.assertNotIn("leftpad", text, name)
            self.assertNotIn("fake_product/app.py", text.replace("tests/fixtures/fake_product/app.py\"", "")
                             if name != "graph" else text, name)

    def test_lockfile_read(self):
        st = load(self.root, "stack")
        pk = {(p["name"], p["version"]) for p in st["packages"]}
        self.assertIn(("requests", "2.31.0"), pk)
        self.assertIn(("flask", "3.0.0"), pk)
        ids = [f["id"] for f in st["facts"]]
        self.assertIn("stack.python.requests", ids)

    def test_stdlib_split(self):
        st = load(self.root, "stack")
        self.assertIn("enum", st["imports_split"]["python"]["stdlib"])
        self.assertIn("unittest", st["imports_split"]["python"]["stdlib"])

    def test_graph_edges_have_evidence_and_l2_regression(self):
        g = load(self.root, "graph")
        self.assertEqual(g["edge_fields"], ["from", "to", "weight", "line"])
        edges = {(e[0], e[1]): e for e in g["edges"]}
        e = edges[("src/billing/invoice.py", "src/shop/orders.py")]
        self.assertEqual(e[3], 1)
        self.assertIn(("scripts/check.sh", "scripts/lib.sh"), edges)  # shell source
        arch = load(self.root, "architecture")  # L2 consome arestas de 4 campos (regressão)
        self.assertIn(["src/billing", "src/shop", 2], arch["component_edges"])

    def test_representative_per_folder(self):
        inv = load(self.root, "inventory")
        reps = {d["dir"]: d for d in inv["directories"]}
        self.assertEqual(reps["src/shop"]["representative"], "src/shop/money.py")  # mais central
        for d in ("src", "src/shop", "src/billing", "tests", "scripts", "."):
            self.assertIn(d, reps)
        g = load(self.root, "graph")
        self.assertEqual(g["representatives"]["src/shop"], "src/shop/money.py")

    def test_fix_commit_detected(self):
        h = load(self.root, "history")
        fixes = [f for f in h["facts"] if f["id"].startswith("hist.fix.")]
        self.assertEqual(len(fixes), 1)
        self.assertIn("src/shop/orders.py", fixes[0]["data"]["files"])
        self.assertEqual(fixes[0]["evidence"][0]["commit"], fixes[0]["data"]["sha"])

    def test_tests_found_and_operations_declared(self):
        r = load(self.root, "rules")
        units = {u["file"]: u for u in r["test_units"]}
        self.assertEqual(units["tests/test_orders.py"]["tests"], 2)
        self.assertGreaterEqual(units["tests/test_orders.py"]["asserts"], 3)
        ops = load(self.root, "operations")
        cmds = {c["cmd"]: c for c in ops["commands"]}
        self.assertEqual(cmds["make test"]["status"], "declared")
        self.assertEqual(cmds["make test"]["reason"], "--no-exec")

    def test_glossary_and_business_rules(self):
        g = load(self.root, "glossary")
        terms = {t["term"]: t for t in g["terms"]}
        self.assertIn("order item", terms)
        self.assertEqual(terms["order item"]["defined_at"][0]["file"], "src/shop/orders.py")
        self.assertEqual(terms["pedido"]["class"], "business")
        br = load(self.root, "business_rules")
        kinds = {}
        for r in br["rules"]:
            kinds.setdefault(r["kind"], []).append(r)
        val = kinds["validation"][0]
        self.assertEqual(val["file"], "src/shop/orders.py")
        self.assertEqual(val["covered_by"]["file"], "tests/test_orders.py")
        self.assertEqual(kinds["limit"][0]["name"], "MAX_ITEMS_PER_ORDER")
        self.assertEqual(kinds["state"][0]["states"], ["DRAFT", "PAID", "SHIPPED"])
        self.assertTrue(any(r["name"] == "test_order_cannot_exceed_max_items" for r in kinds["test"]))

    def test_project_docs_verified_and_stale(self):
        d = load(self.root, "project_docs")
        readme = next(x for x in d["documents"] if x["file"] == "README.md")
        st = {c["text"]: c["status"] for c in readme["claims"]}
        self.assertEqual(st["make test"], "verified")
        self.assertEqual(st["make deploy-prod"], "stale")
        self.assertEqual(st["src/shop/orders.py"], "verified")
        self.assertEqual(st["src/shop/nao_existe.py"], "stale")
        self.assertEqual(st["requests 2.31"], "verified")

    def test_stack_graph(self):
        sg = load(self.root, "stack_graph")
        ids = {n["id"]: n for n in sg["nodes"]}
        self.assertIn("lang:python", ids)
        self.assertEqual(ids["framework:python:flask"]["version"], "3.0.0")
        self.assertIn({"from": "lang:python", "to": "runtime:python"}, sg["edges"])

    def test_writes_only_specialists(self):
        out = subprocess.run(["git", "-C", self.root, "status", "--porcelain"], stdout=subprocess.PIPE)
        lines = [ln for ln in out.stdout.decode().splitlines() if ln.strip()]
        self.assertEqual(lines, ["?? .swarm/"])

    def test_check_mode(self):
        r = synth.cs(self.root, "scan", "--layers", "L0,L9", "--check")
        self.assertEqual(r.returncode, 0, r.stderr)


class Determinism(unittest.TestCase):
    def test_byte_identical(self):
        root = synth.make_repo()
        try:
            self.assertEqual(synth.cs(root, "scan", "--no-exec").returncode, 0)
            a = read_tree(facts_dir(root))
            self.assertEqual(synth.cs(root, "scan", "--no-exec").returncode, 0)
            b = read_tree(facts_dir(root))
            self.assertEqual(sorted(a), sorted(b))
            for k in a:
                self.assertEqual(a[k], b[k], k)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class Exec(unittest.TestCase):
    def test_test_command_executed_and_verified(self):
        root = synth.make_repo()
        try:
            r = synth.cs(root, "scan", "--layers", "L7", "--timeout", "120")
            self.assertEqual(r.returncode, 0, r.stderr)
            ops = load(root, "operations")
            cmds = {c["cmd"]: c for c in ops["commands"]}
            mt = cmds["make test"]
            self.assertEqual(mt["status"], "verified")
            self.assertEqual(mt["exit"], 0)
            blob = os.path.join(root, mt["output_blob"])
            self.assertTrue(os.path.isfile(blob))
            import hashlib
            with open(blob, "rb") as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), mt["out_sha256"])
            self.assertEqual(cmds["make ghost"]["status"], "declared")  # kind other não executa
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_failing_command_marked_failed(self):
        root = synth.make_repo({"Makefile": "test:\n\texit 3\n"})
        try:
            self.assertEqual(synth.cs(root, "scan", "--layers", "L7").returncode, 0)
            cmds = {c["cmd"]: c for c in load(root, "operations")["commands"]}
            self.assertEqual(cmds["make test"]["status"], "failed")
            self.assertNotEqual(cmds["make test"]["exit"], 0)
        finally:
            shutil.rmtree(root, ignore_errors=True)


class Errors(unittest.TestCase):
    def test_repo_without_git_fails_clearly(self):
        root = synth.make_repo(git_init=False)
        try:
            r = synth.cs(root, "scan", "--no-exec")
            self.assertEqual(r.returncode, 2)
            err = r.stderr.decode()
            self.assertIn("não é um repositório git", err)
            self.assertIn("como resolver", err)
            self.assertFalse(os.path.exists(os.path.join(root, STATE_DIR)))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_no_commits_history_fails_clearly(self):
        root = synth.make_repo(git_init=False)
        try:
            synth.git(root, "init", "-q")
            synth.git(root, "add", "-A")
            r = synth.cs(root, "scan", "--layers", "L5", "--no-exec")
            self.assertEqual(r.returncode, 2)
            self.assertIn("não tem commits", r.stderr.decode())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_unknown_layer_and_check_missing(self):
        root = synth.make_repo()
        try:
            r = synth.cs(root, "scan", "--layers", "L42")
            self.assertEqual(r.returncode, 2)
            self.assertIn("camada desconhecida", r.stderr.decode())
            r = synth.cs(root, "scan", "--layers", "L0", "--check")
            self.assertNotEqual(r.returncode, 0)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_scan_of_repo_with_only_fixtures_fails(self):
        root = tempfile.mkdtemp()
        try:
            synth.write(root, "fixtures/a.py", "x = 1\n")
            synth.git(root, "init", "-q")
            synth.commit(root, "init")
            r = synth.cs(root, "scan", "--no-exec")
            self.assertEqual(r.returncode, 2)
            self.assertIn("nenhum arquivo analisável", r.stderr.decode())
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
