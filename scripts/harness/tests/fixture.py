"""Fixture compartilhada: repo git sintético com team.json5, fatos, config e estado iniciado."""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.dirname(HERE)
ENGINE = os.path.join(HARNESS, "engine")
MEMORY = os.path.join(os.path.dirname(HARNESS), "memory")
for p in (ENGINE, MEMORY, HARNESS):
    if p not in sys.path:
        sys.path.insert(0, p)

import j5  # noqa: E402

TEAM = {
    "schema_version": 1,
    "agents": [
        {"name": "dev-billing", "kind": "dev", "territory": ["src/billing/**"], "card": {
            "footguns": [{"text": "arredondar centavos antes de somar quebra totais", "facts": ["rule.billing.cents"]}]}},
        {"name": "dev-members", "kind": "dev", "territory": ["src/members/**"]},
        {"name": "po", "kind": "product", "territory": ["docs/stories/**"]},
        {"name": "reviewer", "kind": "gate", "territory": []},
        {"name": "security", "kind": "gate", "territory": []},
    ],
}
FACTS_RULES = [
    {"id": "rule.billing.cents", "layer": "rules", "claim": "valores monetários em centavos inteiros", "scope": ["src/billing/**"],
     "evidence": [{"file": "src/billing/total.py", "line": 1}], "confidence": "high", "origin": "mechanical", "fingerprint": "x"},
    {"id": "rule.global.utf8", "layer": "rules", "claim": "arquivos em UTF-8", "scope": ["**"],
     "evidence": [{"file": "README.md"}], "confidence": "high", "origin": "mechanical", "fingerprint": "x"},
]
BUSINESS = [
    {"id": "br.billing.max-discount", "rule": "desconto máximo de 30% por pedido", "scope": ["src/billing/**"],
     "evidence": [{"file": "src/billing/total.py", "line": 2}]},
    {"id": "br.members.age", "rule": "usuário precisa ter 18 anos ou mais", "scope": ["src/members/**"],
     "evidence": [{"file": "src/members/model.py", "line": 1}]},
]
GLOSSARY = [{"id": "term.invoice", "term": "invoiceTotal", "canonical": "invoice total", "never_use": ["fatura_total"],
             "scope": ["src/billing/**"], "evidence": [{"file": "src/billing/total.py", "line": 1}]}]


def git(root, *args):
    subprocess.run(["git"] + list(args), cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def make_repo(with_state=True, with_collision=None, no_invariant_scope=False, no_rules=False):
    root = os.path.realpath(tempfile.mkdtemp(prefix="cs-harness-"))
    files = {
        "README.md": "# demo\n",
        ".gitignore": "__pycache__/\n*.pyc\n",
        "src/billing/total.py": "def total(items):\n    return sum(items)\n",
        "src/billing/tax.py": "RATE = 0\n",
        "src/members/model.py": "AGE = 18\n",
        "tests/test_billing.py": "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
        "tests/__init__.py": "",
        "docs/stories/README.md": "stories\n",
        "spec/feat.md": "spec\n",
        "accept/test_accept.py": "import unittest\nclass A(unittest.TestCase):\n    def test_feature(self):\n        import os\n        self.assertTrue(os.path.exists('src/billing/discount.py'))\n",
        "accept/__init__.py": "",
    }
    for rel, txt in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(txt)
    sp = os.path.join(root, ".swarm")
    os.makedirs(os.path.join(sp, "facts"))
    with open(os.path.join(sp, "team.json5"), "w") as f:
        f.write(j5.dumps(TEAM))
    rules = [dict(r) for r in FACTS_RULES]
    if no_invariant_scope or no_rules:
        rules = [r for r in rules if r["id"] != "rule.billing.cents"]
    with open(os.path.join(sp, "facts", "rules.json5"), "w") as f:
        f.write(j5.dumps({"facts": rules}))
    with open(os.path.join(sp, "facts", "business_rules.json5"), "w") as f:
        f.write(j5.dumps([] if no_rules else BUSINESS))
    with open(os.path.join(sp, "facts", "glossary.json5"), "w") as f:
        f.write(j5.dumps(GLOSSARY))
    if with_collision is not None:
        os.makedirs(os.path.join(sp, "knowledge"))
        with open(os.path.join(sp, "knowledge", "collision.json5"), "w") as f:
            f.write(j5.dumps(with_collision))
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    if with_state:
        import engine
        engine.init_state(root)
    return root


def rm(root):
    shutil.rmtree(root, ignore_errors=True)


A = "lead"


def process(root, klass="pequena", story_type="us"):
    """épico ACTIVE → feature READY → story READY → sessão em PLANNING com a classe dada."""
    import cmds
    cmds.add_epic(root, A, "Billing", "cobrar certo", "receita")
    cmds.level_transition(root, A, "epic", "EPIC-1", "activate")
    cmds.add_feature(root, A, "EPIC-1", "Desconto", "spec/feat.md", ["python3 -m unittest accept.test_accept"],
                     ["accept/test_accept.py"])
    cmds.level_transition(root, A, "feature", "FEAT-1", "ready")
    cmds.add_story(root, A, "us", "FEAT-1", "Como cliente quero desconto", as_a="cliente", i_want="desconto",
                   so_that="pagar menos",
                   criteria=[{"id": "AC-1", "gherkin": "Dado pedido Quando aplico Então desconta", "test": "tests.test_billing"}])
    cmds.level_transition(root, A, "story", "US-1", "ready")
    cmds.session_start(root, A, "implementar desconto")
    cmds.session_cmd(root, A, "triage", {"class": klass, "why": "teste"})
    cmds.session_cmd(root, A, "plan")


def task_spec(agent="dev-billing", paths=("src/billing/discount.py",), title="criar desconto", wave=1, **kw):
    s = {"story": "US-1", "agent": agent, "title": title, "goal": "aplicar desconto porque FEAT-1 exige",
         "allowed_paths": list(paths), "verification_command": "python3 -m unittest discover -s tests -t .",
         "acceptance_criteria": ["AC-1|desconto aplicado ao total do pedido|test:tests.test_billing"],
         "briefing": {"references": ["src/billing/total.py:1"], "scope": {"in": ["desconto"], "out": ["tax: outra task"]}},
         "wave": wave}
    s.update(kw)
    return s


def dispatched(root, klass="pequena", **kw):
    """Fluxo até T-1 DISPATCHED (modelo recomendado declarado)."""
    import cmds
    import hcore
    process(root, klass)
    cmds.add_task(root, A, task_spec(**kw), ready=True)
    cmds.session_cmd(root, A, "execute")
    d = hcore.find(hcore.load_board(root), "deleg", "T-1.d1")
    cmds.dispatch(root, A, "T-1.d1", model=d["route"]["model"], tool_use_id="tu-1", procedencia="declarada-no-despacho")
    return "T-1"


def write(root, rel, txt="X = 1\n"):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(txt)


def submit_ok(root, tid="T-1", rel="src/billing/discount.py"):
    import cmds
    write(root, rel)
    cmds.submit(root, "dev-billing", tid, {"files_changed": [rel], "checks_run": ["unittest: OK"], "risks": [],
                                           "handoff_notes": "ok"})
