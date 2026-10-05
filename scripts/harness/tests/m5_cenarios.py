"""Cenários de COBERTURA da máquina M5 `mandato` (modo autônomo) para test_cobertura_maquinas.py.

Cada cenário recebe o `H` do oráculo de cobertura e só usa a CLI real (`cs-state`, `cs-auto`) e os hooks reais em
subprocesso observado — exatamente como os demais cenários. A montagem do repositório (arquivos, git) é in-process;
o estado (árvore épico→sprint→feature→task da campanha iter10) é criado pela CLI.
Contrato das interfaces: ESPEC interna (não publicada) §2. Objetivo aqui: exercitar
TODA aresta de `machines.mandato`, toda guarda passando e toda guarda recusando (exceto EXCLUSOES_M5, sem caminho legal).
"""
import json
import os
import re
import shlex
import subprocess
import tempfile

HUMAN = "founder"
OBJ = "Desconto no checkout"
REGRESSAO = "python3 -m unittest discover -s tests -t ."
GATES = ("reviewer", "security")
CREATED_RE = re.compile(r"^criad[oa] (\S+) em (\S+)\s*$", re.M)
ORC = "despachos=20,tentativas=40,replanos=3,minutos=600,usd=50"
SD = ".swarm"
try:
    import sys as _sys
    _p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
    from cslib.paths import STATE_DIR as _SD  # noqa: E402
    SD = os.path.basename(str(_SD).rstrip("/")) or SD
except Exception:
    pass

TEAM = {"schema_version": 1, "agents": [
    {"name": "dev-billing", "kind": "dev", "territory": ["src/billing/**", "src/shared/**"]},
    {"name": "dev-members", "kind": "dev", "territory": ["src/members/**", "src/shared/**"]},
    {"name": "qa", "kind": "qa", "territory": ["tests/**"]},
    {"name": "po", "kind": "product", "territory": ["docs/stories/**"]},
    {"name": "reviewer", "kind": "gate", "territory": []},
    {"name": "security", "kind": "gate", "territory": []}]}
RULES = {"facts": [{"id": "rule.billing.cents", "layer": "rules", "claim": "valores em centavos", "scope": ["src/billing/**"],
                    "evidence": [{"file": "src/billing/total.py", "line": 1}], "confidence": "high", "origin": "mechanical",
                    "fingerprint": "x"}]}
TEST_BILLING = ("import importlib.util\nimport unittest\n\n\nclass T(unittest.TestCase):\n    def test_total(self):\n"
                "        s = importlib.util.spec_from_file_location('total', 'src/billing/total.py')\n"
                "        m = importlib.util.module_from_spec(s)\n        s.loader.exec_module(m)\n"
                "        self.assertEqual(m.total([1, 2]), 3)\n")
FILES = {"README.md": "# demo\n", ".gitignore": "__pycache__/\n*.pyc\n",
         "src/billing/total.py": "def total(items):\n    return sum(items)\n", "src/members/model.py": "AGE = 18\n",
         "src/shared/util.py": "X = 0\n", "tests/__init__.py": "", "tests/test_billing.py": TEST_BILLING,
         "accept/__init__.py": "", "docs/stories/README.md": "x\n",
         "spec/feature.md": "# Desconto no checkout\n\nDesconto e perfil no checkout.\n"}
ACS = [("AC-1", "src/billing/discount.py"), ("AC-2", "src/members/profile.py"), ("AC-3", "tests/test_fluxo.py")]
ACS2 = ACS[:2]
ACS_FROZEN = [("AC-1", "src/shared/frozen/rates.py"), ("AC-2", "src/members/profile.py"), ("AC-3", "tests/test_rates.py")]


def N(no, agent, paths, cobre, deps=(), **kw):
    d = {"id": no, "agent": agent, "paths": list(paths), "cobre": list(cobre), "deps": list(deps)}
    d.update(kw)
    return d


NODES = [N("01", "dev-billing", ["src/billing/discount.py"], ["AC-1"]), N("02", "dev-members", ["src/members/profile.py"], ["AC-2"]),
         N("03", "qa", ["tests/test_fluxo.py"], ["AC-3"], deps=["01"])]
NODES2 = NODES[:2]
NODES_FROZEN = [N("01", "dev-billing", ["src/shared/frozen/rates.py"], ["AC-1"]),
                N("02", "dev-members", ["src/members/profile.py"], ["AC-2"]),
                N("03", "qa", ["tests/test_rates.py"], ["AC-3"], deps=["01"])]

EXCLUSOES_M5 = {
    ("guarda_recusa", "mandato", "plan_accept", "waves_computed"): "ondas são CALCULADAS pelo motor; o modelo não as escreve",
    ("guarda_recusa", "mandato", "replan_accept", "waves_computed"): "idem (replano)",
    ("guarda_recusa", "mandato", "plan_accept", "lessons_consulted"): "a busca de lições é feita pelo motor ao entrar em PLANNING",
    ("guarda_recusa", "mandato", "replan_accept", "plan_diff_recorded"): "o diff vN→vN+1 é gravado pelo motor no submit",
    ("guarda_recusa", "mandato", "wave_closed", "no_delegation_in_flight"): "o tick só fecha a onda sem nada em voo",
    ("guarda_recusa", "mandato", "integrate_replan", "replan_trigger"): "o motor só tenta replanejar quando há gatilho",
    ("guarda_recusa", "mandato", "next_feature", "next_feature_queued"): "o motor só tenta next_feature com feature na fila",
    ("guarda_recusa", "mandato", "escalate", "package_recorded"): "o pacote é gravado pelo motor na própria escalada",
    ("guarda_recusa", "mandato", "pause", "in_flight_marked"): "pause marca as delegações em voo (orphan_watch) ele mesmo",
    ("guarda_recusa", "mandato", "resume", "stamp_matches"): "carimbo divergente vira delta impresso, não recusa (§8.2)",
    ("guarda_recusa", "mandato", "wrap_up", "wrap_trigger"): "o motor só encerra com gatilho; stop humano passa por by_human",
    ("guarda_recusa", "mandato", "hand_back", "no_delegation_in_flight"): "hand_back só é tentado sem nada em voo",
    ("guarda_recusa", "mandato", "hand_back", "report_generated"): "o relatório é gerado pelo motor no próprio hand_back",
    ("guarda_recusa", "mandato", "hand_back", "open_items_returned"): "a devolução ao backlog é feita pelo motor no hand_back",
}


# ------------------------------------------------------------------ apoio
def _check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _write(root, rel, txt):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p) or root, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)


def _git(root, *a):
    subprocess.run(["git"] + list(a), cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def ac_id(ac):
    return "accept.test_ac_%s" % ac.split("-")[1]


def crit(ac, path):
    return "%s|Dado o checkout Quando entrego %s Então tem OK|%s" % (ac, path, ac_id(ac))


def ok_text(p):
    b = os.path.basename(p)
    if b.startswith("test_") and p.endswith(".py"):
        return "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):  # OK\n        self.assertTrue(True)\n"
    return "OK = 1\n" if p.endswith(".py") else "OK\n"


def repo(h, acs=ACS, features=None, start=True):
    root = os.path.realpath(tempfile.mkdtemp(prefix="cs-cov-m5-"))
    h.tmp.append(root)
    for r, t in FILES.items():
        _write(root, r, t)
    for ac, p in acs:
        _write(root, "accept/test_ac_%s.py" % ac.split("-")[1],
               "import os\nimport unittest\n\n\nclass A(unittest.TestCase):\n    def test_ac(self):\n        p = %r\n"
               "        self.assertTrue(os.path.isfile(p) and 'OK' in open(p).read())\n" % p)
    _write(root, os.path.join(SD, "team.json5"), json.dumps(TEAM))
    _write(root, os.path.join(SD, "facts", "rules.json5"), json.dumps(RULES))
    _write(root, os.path.join(SD, "facts", "business_rules.json5"), "[]")
    _write(root, os.path.join(SD, "facts", "glossary.json5"), "[]")
    _write(root, os.path.join(SD, "knowledge", "collision.json5"), json.dumps({"do_not_parallelize": []}))
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    h.ok(root, "init")
    _write(root, os.path.join(SD, "harness", "config.json5"),
           json.dumps({"frozen_paths": ["src/shared/frozen/**"], "max_files_per_task": 3}))
    spr = CREATED_RE.findall(h.ok(root, "new", "sprint", "--meta", "entregar desconto").out)[0][0]
    h.ok(root, "start", spr)
    feas = []
    for title, ids in (features or [("Desconto no checkout", [a for a, _ in acs])]):
        s = h.ok(root, "new", "feature", "--title", title, "--sprint", spr, "--aceite",
                 "python3 -m unittest " + " ".join(ac_id(a) for a in ids))
        feas.append(CREATED_RE.findall(s.out)[0][0])
    if start:
        h.ok(root, "start", feas[0])
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root, spr, feas


def a_ok(h, root, *args):
    s = h.auto(root, *args)
    _check(s.code == 0, "cs-auto %s → exit %d (esperado 0)\n%s%s" % (" ".join(args), s.code, s.out[-1200:], s.err[-1200:]))
    return s


def a_no(h, root, *args, **kw):
    """Recusa exit 1; `guards` = guardas de transição com entidade (observador); `nomes` = criação (stderr)."""
    s = h.auto(root, *args)
    _check(s.code == 1, "cs-auto %s deveria ser RECUSADO (exit 1), deu %d\n%s%s" % (" ".join(args), s.code, s.out, s.err))
    h._expect_guards(s, kw.get("guards", ()), args)
    for g in kw.get("nomes", ()):
        _check(("guarda %s:" % g) in s.err, "cs-auto %s: esperava `guarda %s:` no stderr\n%s" % (" ".join(args), g, s.err))
    return s


def hum(args):
    return list(args) + ["--by", HUMAN] + shlex.split(os.environ.get("CS_HUMAN_PROOF_ARGS", ""))


def tick(h, root):
    s = a_ok(h, root, "tick", "--json")
    return json.loads(s.out)


def status(h, root):
    return json.loads(a_ok(h, root, "status", "--json").out)


def estado(h, root):
    return status(h, root).get("estado")


def propose(h, root, fea, acs, nos=3, extra=()):
    args = ["propose", "--feature", fea, "--spec", "spec/feature.md", "--objetivo", OBJ, "--nos", str(nos),
            "--regressao", REGRESSAO]
    for a, p in acs:
        args += ["--criterio", crit(a, p)]
    a_ok(h, root, *(args + list(extra)))


def add_node(h, root, n):
    args = ["plan", "add-node", "--id", n["id"], "--tipo", n.get("tipo", "US"), "--agent", n["agent"],
            "--title", "N%s" % n["id"]]
    for p in n["paths"]:
        args += ["--path", p]
    if n.get("deps"):
        args += ["--deps", ",".join(n["deps"])]
    args += ["--cobre", ",".join(n["cobre"])]
    if n.get("verify"):
        args += ["--verify-cmd", n["verify"]]
    if n.get("teste"):
        args += ["--teste", n["teste"]]
    a_ok(h, root, *args)


def submit(h, root, nodes, motivo=None, ev=None, drv=None):
    for n in nodes:
        add_node(h, root, n)
        if drv is not None:
            drv.nodes[n["id"]] = n
    a_ok(h, root, *(["plan", "submit"] + (["--motivo", motivo] if motivo else []) + (["--evidencia", ev] if ev else [])))


def plan_no(h, root, nodes, guard, motivo=None, ev=None):
    for n in nodes:
        add_node(h, root, n)
    a_no(h, root, *(["plan", "submit"] + (["--motivo", motivo] if motivo else []) + (["--evidencia", ev] if ev else [])),
         guards=[guard])
    a_ok(h, root, "plan", "reset")


def running(h, acs=ACS, nodes=NODES, orc=ORC, nos=None, extra=()):
    root, spr, feas = repo(h, acs)
    propose(h, root, feas[0], acs, nos=nos or max(2, len(nodes)), extra=extra)
    a_ok(h, root, *hum(["approve", "--orcamento", orc]))
    t = tick(h, root)
    _check(t.get("acao") == "PLAN", "CHARTERED → PLAN: %r" % t)
    d = D(h, root, nodes)
    submit(h, root, nodes, drv=d)
    _check(estado(h, root) == "RUNNING", "plan_accept → RUNNING")
    return root, d


class D(object):
    """Executa só as ações de julgamento pedidas pelo tick (como o modelo)."""

    def __init__(self, h, root, nodes=()):
        self.h, self.root = h, root
        self.nodes = dict((n["id"], n) for n in nodes)
        self.mode = {}
        self.default = "ok"
        self.content = {}
        self.inflight = {}
        self.attempt = {}
        self.dispatches = []
        self.on_replan = None
        self.on_plan = None
        self.on_final = None

    def deliver(self, task):
        h, root = self.h, self.root
        info = self.inflight.pop(task)
        no, agent = info["no"], info["agent"]
        m = self.mode.get(no, self.default)
        if m == "abstain":
            h.ok(root, "abstain", task, "--kind", "out_of_territory", "--reason", "outro território", actor=agent)
            return
        files = self.content.get(no) if m == "ok" and no in self.content else {
            p: ({"partial": "PARCIAL = 1\n", "wrong": "ERRADO = 1\n"}.get(m) or ok_text(p)) for p in info["paths"]}
        for p, t in files.items():
            _write(root, p, t)
        a = ["submit", task]
        for p in files:
            a += ["--files-changed", p]
        h.ok(root, *(a + ["--check", "unittest: OK", "--risk", "nenhum", "--handoff-notes", "ok"]), actor=agent)

    def step(self, stop=()):
        """Executa a ação do tick — exceto se ela está em `stop` (aí o tick volta intacto para o cenário agir)."""
        h, root = self.h, self.root
        t = tick(h, root)
        act = t.get("acao")
        if act in stop and act not in ("FIM", "ASK_HUMAN"):
            return t
        if act == "PLAN":
            _check(self.on_plan is not None, "PLAN inesperado: %r" % t)
            self.on_plan(self, t)
        elif act == "REPLAN":
            _check(self.on_replan is not None, "REPLAN inesperado: %r" % t)
            self.on_replan(self, t)
        elif act == "DISPATCH":
            no = str(t.get("no"))
            h.ok(root, "dispatch", t["alvo"], "--manual", "--model", t.get("model") or "sonnet")
            self.attempt[no] = self.attempt.get(no, 0) + 1
            self.inflight[t["alvo"]] = {"no": no, "agent": t["agente"],
                                        "paths": (self.nodes.get(no) or {}).get("paths") or t.get("paths") or []}
            self.dispatches.append((t["alvo"], no, t["agente"]))
        elif act == "IDLE_WAIT":
            _check(self.inflight, "IDLE_WAIT sem nada em voo")
            for task in list(self.inflight):
                self.deliver(task)
        elif act == "REVIEW":
            h.ok(root, "review", t["alvo"], "--by", t["agente"], "--verdict", "PASS", "--findings", "conferido arquivo:1")
        elif act == "REFLECT":
            ref = t["evidencia"][0]["ref"]
            a_ok(h, root, "reflect", t["alvo"], "--texto", "falhou %s; muda: OK" % ref, "--evidencia", ref)
        elif act == "ANSWER_ORPHAN":
            a_ok(h, root, "orphan", t["alvo"])
            self.inflight.pop(t["alvo"], None)
        elif act == "FINAL_REVIEW":
            if self.on_final:
                self.on_final(self, t)
                self.on_final = None
            a_ok(h, root, "final-review", "--by", t["agente"], "--verdict", "PASS", "--findings", "aceite verde conferido")
        elif act == "RESUME":
            a_ok(h, root, "resume")
        elif act == "REPORT":
            a_ok(h, root, "report")
        else:
            _check(act in ("ASK_HUMAN", "FIM"), "ação desconhecida: %r" % t)
        return t

    def run(self, stop=("FIM", "ASK_HUMAN"), until=None, n=160):
        for _ in range(n):
            t = self.step(stop)
            if (until and until(self, t)) or t.get("acao") in stop:
                return t
        raise AssertionError("piloto não convergiu em %d ticks" % n)


def ate_replanning(h, orc=ORC):
    root, d = running(h, orc=orc)
    d.mode["02"] = "partial"
    t = d.run(stop=("REPLAN", "FIM", "ASK_HUMAN"))
    _check(t.get("acao") == "REPLAN", "DAG esgotado com aceite 2/3 → REPLAN: %r" % t)
    return root, d, t


def ate_aguardar(h):
    root, d = running(h, acs=ACS_FROZEN, nodes=NODES_FROZEN)
    t = d.run()
    _check(t.get("acao") == "ASK_HUMAN", "ramo congelado → AWAITING_HUMAN quando nada mais roda: %r" % t)
    return root, d


# ------------------------------------------------------------------ cenários
def m5_proposta_aprovacao_emenda_aborto(h):
    root, spr, feas = repo(h, ACS2)
    base = ["--spec", "spec/feature.md", "--objetivo", OBJ, "--nos", "2", "--regressao", REGRESSAO]
    good = ["--criterio", crit(*ACS2[0]), "--criterio", crit(*ACS2[1])]
    a_no(h, root, "propose", "--feature", "FEA-999", *(base + good), nomes=["target_exists"])
    a_no(h, root, "propose", "--feature", feas[0], "--spec", "spec/nao.md", *(base[2:] + good), nomes=["spec_present"])
    a_no(h, root, "propose", "--feature", feas[0], *(base + ["--criterio", "AC-1|Dado x Quando y Então z|accept.test_nao_existe", good[2], good[3]]),
         nomes=["acceptance_executable"])
    a_no(h, root, "propose", "--feature", feas[0], *(base + ["--criterio", "AC-1|Dado x Quando y Então verde|tests.test_billing", good[2], good[3]]),
         nomes=["acceptance_red"])
    a_no(h, root, "propose", "--feature", feas[0], *(base + good + ["--classe", "pergunta"]), nomes=["class_allowed"])
    a_no(h, root, "propose", "--feature", feas[0], *(base[:4] + ["--nos", "1"] + base[6:] + good), nomes=["not_trivial"])
    a_ok(h, root, "propose", "--feature", feas[0], *(base + good))
    a_no(h, root, "propose", "--feature", feas[0], *(base + good), nomes=["no_open_mandate"])
    a_no(h, root, "amend", "--by", "orchestrator", "--reason", "x", guards=["by_human"])
    a_no(h, root, *hum(["amend"]), guards=["reason_present"])
    a_ok(h, root, *hum(["amend", "--reason", "orçamento", "--orcamento", ORC]))            # amend PROPOSED
    a_no(h, root, "approve", "--by", "orchestrator", guards=["by_human"])
    _write(root, "src/billing/discount.py", "OK = 1\n")
    _write(root, "src/members/profile.py", "OK = 1\n")
    a_no(h, root, *hum(["approve"]), guards=["acceptance_red"])
    os.remove(os.path.join(root, "src/billing/discount.py"))
    os.remove(os.path.join(root, "src/members/profile.py"))
    a_no(h, root, "abort", "--by", "dev-billing", "--reason", "x", guards=["by_human"])
    a_no(h, root, *hum(["abort"]), guards=["reason_present"])
    a_ok(h, root, *hum(["abort", "--reason", "rejeitada"]))                                 # abort PROPOSED
    _check(estado(h, root) == "ABORTED", "abort → ABORTED")


def m5_plano_recusas(h):
    root, spr, feas = repo(h, ACS)
    propose(h, root, feas[0], ACS)
    a_ok(h, root, *hum(["approve", "--orcamento", ORC]))
    _check(tick(h, root).get("acao") == "PLAN", "PLAN")
    a, b, c = NODES
    plan_no(h, root, [N("01", "dev-billing", ["src/billing/discount.py"], ["AC-1", "AC-2", "AC-3"])], "not_trivial")
    plan_no(h, root, [dict(a, deps=["02"]), dict(b, deps=["01"]), c], "dag_acyclic")
    plan_no(h, root, [a, b], "dag_covers_acceptance")
    plan_no(h, root, [dict(a, paths=["src/members/x.py"]), b, c], "nodes_in_territory")
    plan_no(h, root, [dict(a, paths=["src/billing/%s.py" % x for x in "abcd"]), b, c], "nodes_fit_horizon")
    root2, spr2, feas2 = repo(h, ACS)
    propose(h, root2, feas2[0], ACS)
    a_ok(h, root2, *hum(["approve", "--orcamento", "despachos=2,tentativas=40,replanos=3,minutos=600"]))
    tick(h, root2)
    plan_no(h, root2, NODES, "plan_within_budget")


def m5_fluxo_feliz_com_pausas(h):
    root, spr, feas = repo(h, ACS)
    propose(h, root, feas[0], ACS)
    a_ok(h, root, *hum(["approve", "--orcamento", ORC]))
    _check(tick(h, root).get("acao") == "PLAN", "PLAN")
    a_ok(h, root, "pause")                                                                 # pause PLANNING
    a_ok(h, root, "resume")                                                                # resume → PLANNING
    _check(estado(h, root) == "PLANNING", "resume volta a PLANNING")
    d = D(h, root, NODES)
    submit(h, root, NODES, drv=d)
    d.run(until=lambda dd, t: len(dd.dispatches) >= 1)
    h.hook(root, "pre-compact", {"hook_event_name": "PreCompact", "trigger": "auto"})       # pause RUNNING
    _check(estado(h, root) == "PAUSED", "PreCompact → PAUSED")
    h.hook(root, "session-start", {"hook_event_name": "SessionStart", "source": "compact"})  # resume → RUNNING
    _check(estado(h, root) == "RUNNING", "SessionStart → RUNNING")

    def final(dd, t):
        a_no(h, root, "final-review", "--by", "dev-billing", "--verdict", "PASS", "--findings", "eu",
             guards=["final_review_pass"])
        a_ok(h, root, "pause")                                                             # pause INTEGRATING
        a_ok(h, root, "resume")
        _check(estado(h, root) == "INTEGRATING", "resume volta a INTEGRATING")
    d.on_final = final
    d.run()
    _check(estado(h, root) == "DONE", "fluxo feliz → DONE")


def m5_replano_recusas_escalada_e_pausa(h):
    root, d, t = ate_replanning(h)
    ref = t["evidencia"][0]["ref"]
    n4 = N("04", "dev-members", ["src/members/profile.py"], ["AC-2"])
    plan_no(h, root, [n4], "replan_cites_evidence", motivo="acho")
    a_ok(h, root, "plan", "edit-node", "--id", "02", "--path", "src/members/outro.py")
    a_no(h, root, "plan", "submit", "--motivo", "AC-2", "--evidencia", ref, guards=["accepted_nodes_untouched"])
    a_ok(h, root, "plan", "reset")
    plan_no(h, root, [dict(n4, deps=["05"]), N("05", "dev-members", ["src/members/p5.py"], ["AC-2"], deps=["04"])],
            "dag_acyclic", motivo="AC-2", ev=ref)
    plan_no(h, root, [N("04", "qa", ["tests/test_x.py"], ["AC-3"])], "dag_covers_acceptance", motivo="AC-2", ev=ref)
    plan_no(h, root, [dict(n4, paths=["src/billing/x.py"])], "nodes_in_territory", motivo="AC-2", ev=ref)
    plan_no(h, root, [dict(n4, paths=["src/members/%s.py" % x for x in "abcd"])], "nodes_fit_horizon", motivo="AC-2", ev=ref)
    a_ok(h, root, "pause")                                                                 # pause REPLANNING
    a_ok(h, root, "resume")
    a_no(h, root, "escalate", "--condicao", "inventada", "--evidencia", "spec/feature.md:1", guards=["escalation_condition"])
    a_ok(h, root, "escalate", "--condicao", "material_ambiguity", "--evidencia", "spec/feature.md:1")  # escalate REPLANNING
    a_ok(h, root, *hum(["resolve", "--choice", "retomar", "--decision", "segue"]))
    _check(estado(h, root) == "REPLANNING", "retomar volta a REPLANNING")
    submit(h, root, [n4], motivo="AC-2 vermelho", ev=ref, drv=d)                             # replan_accept
    d.run()
    _check(estado(h, root) == "DONE", "replano → DONE")


def m5_replano_acima_do_orcamento(h):
    root, d, t = ate_replanning(h, orc="despachos=4,tentativas=40,replanos=3,minutos=600")
    plan_no(h, root, [N("04", "dev-members", ["src/members/profile.py"], ["AC-2"]),
                      N("05", "dev-members", ["src/members/p5.py"], ["AC-2"])],
            "plan_within_budget", motivo="AC-2", ev=t["evidencia"][0]["ref"])


def m5_replanos_esgotados(h):
    root, d, t = ate_replanning(h, orc="despachos=20,tentativas=40,replanos=1,minutos=600")
    d.mode["04"] = "partial"
    submit(h, root, [N("04", "dev-members", ["src/members/profile.py"], ["AC-2"])], motivo="AC-2", ev=t["evidencia"][0]["ref"], drv=d)
    t = d.run()
    _check(t.get("acao") == "ASK_HUMAN", "replanos esgotados → escalada suave (INTEGRATING → AWAITING_HUMAN)")


def m5_regressao(h):
    root, d = running(h, acs=ACS2, nodes=[N("01", "dev-billing", ["src/billing/discount.py", "src/billing/total.py"], ["AC-1"],
                                            verify="python3 -m unittest accept.test_ac_1"), NODES[1]])
    d.content["01"] = {"src/billing/discount.py": "OK = 1\n", "src/billing/total.py": "def total(items):\n    return 0\n"}
    d.content["03"] = {"src/billing/total.py": "def total(items):  # OK\n    return sum(items)\n"}
    t = d.run(stop=("REPLAN", "FIM", "ASK_HUMAN"))
    _check(t.get("acao") == "REPLAN", "regressão → REPLAN")
    submit(h, root, [N("03", "dev-billing", ["src/billing/total.py"], ["AC-1"], tipo="FIX", teste="tests.test_billing")],
           motivo="regressão tests.test_billing", ev=t["evidencia"][0]["ref"], drv=d)
    d.run()
    _check(estado(h, root) == "DONE", "regressão corrigida → DONE")


def m5_escalada_em_planning_e_stop(h):
    root, spr, feas = repo(h, ACS2)
    propose(h, root, feas[0], ACS2, nos=2)
    a_ok(h, root, *hum(["approve", "--orcamento", ORC]))
    tick(h, root)
    a_ok(h, root, "escalate", "--condicao", "material_ambiguity", "--evidencia", "spec/feature.md:1")  # escalate PLANNING
    a_no(h, root, *hum(["resolve", "--choice", "trocar-agente", "--agent", "dev-members", "--decision", "x"]),
         guards=["choice_in_package"])
    a_no(h, root, *hum(["resolve", "--choice", "descartar-ramo", "--decision", "x"]), guards=["choice_in_package"])
    a_ok(h, root, *hum(["resolve", "--choice", "retomar", "--decision", "spec vale"]))
    _check(estado(h, root) == "PLANNING", "retomar → PLANNING")
    a_ok(h, root, *hum(["stop", "--reason", "parou no planejamento"]))                     # wrap_up PLANNING
    D(h, root).run()
    _check(estado(h, root) == "HANDED_BACK", "stop → HANDED_BACK")


def m5_escalada_local_e_saidas_humanas(h):
    root, d = ate_aguardar(h)
    for ch, extra, g in (("retomar", [], "resolve_resume"), ("trocar-agente", ["--agent", "dev-members"], "resolve_reroute"),
                         ("descartar-ramo", [], "resolve_drop")):
        a_no(h, root, "resolve", "--choice", ch, "--decision", "x", "--by", "orchestrator", *extra, guards=["by_human"])
        a_no(h, root, *hum(["resolve", "--choice", ch] + extra), guards=["decision_present"])
    a_no(h, root, *hum(["resolve", "--choice", "trocar-agente", "--agent", "qa", "--decision", "x"]), guards=["new_agent_valid"])
    a_no(h, root, "amend", "--by", "orchestrator", "--reason", "x", guards=["by_human"])
    a_no(h, root, *hum(["amend"]), guards=["reason_present"])
    a_no(h, root, "abort", "--by", "orchestrator", "--reason", "x", guards=["by_human"])
    a_no(h, root, *hum(["abort"]), guards=["reason_present"])
    a_ok(h, root, *hum(["resolve", "--choice", "retomar", "--decision", "pode escrever"]))  # resolve_resume
    d.run()
    _check(estado(h, root) == "DONE", "retomar → DONE")
    root, d = ate_aguardar(h)
    a_ok(h, root, *hum(["resolve", "--choice", "trocar-agente", "--agent", "dev-members", "--decision", "troca"]))
    d.run()
    _check(estado(h, root) == "DONE", "trocar-agente → DONE")
    root, d = ate_aguardar(h)
    a_ok(h, root, *hum(["resolve", "--choice", "descartar-ramo", "--decision", "descarta"]))  # resolve_drop → wrap INTEGRATING
    d.run()
    _check(estado(h, root) == "HANDED_BACK", "descartar-ramo → HANDED_BACK")
    root, d = ate_aguardar(h)
    a_ok(h, root, *hum(["resolve", "--choice", "emendar", "--decision", "emenda"]))          # amend AWAITING_HUMAN
    _check(estado(h, root) == "PROPOSED", "emendar → PROPOSED")
    root, d = ate_aguardar(h)
    a_ok(h, root, *hum(["resolve", "--choice", "encerrar", "--decision", "encerra"]))        # wrap_up AWAITING_HUMAN
    d.run()
    _check(estado(h, root) == "HANDED_BACK", "encerrar → HANDED_BACK")
    root, d = ate_aguardar(h)
    a_ok(h, root, *hum(["resolve", "--choice", "abortar", "--decision", "aborta"]))          # abort AWAITING_HUMAN
    _check(estado(h, root) == "ABORTED", "abortar → ABORTED")


def m5_hack(h):
    root, d = running(h, acs=ACS2, nodes=NODES2)
    d.run(until=lambda dd, t: len(dd.dispatches) >= 1)
    p = {"tool_name": "Write", "tool_use_id": "tu-w", "tool_input": {"file_path": os.path.join(root, "accept/test_ac_1.py")},
         "cwd": root, "agent_id": "ag-1", "agent_type": d.dispatches[0][2]}
    _check(h.hook(root, "pre-write", p).code == 2, "subagente editando o aceite é bloqueado")
    _check(tick(h, root).get("acao") == "ASK_HUMAN", "tentativa → escalada dura global (RUNNING → AWAITING_HUMAN)")
    root, d = running(h, acs=ACS2, nodes=NODES2)
    d.run(until=lambda dd, t: len(dd.dispatches) >= 1)
    _write(root, "accept/test_ac_1.py", "import unittest\n\n\nclass A(unittest.TestCase):\n    def test_ac(self):\n"
                                        "        self.assertTrue(True)\n")
    _check(tick(h, root).get("acao") == "ASK_HUMAN", "aceite alterado por fora → escalada dura global")
    a_no(h, root, *hum(["resolve", "--choice", "retomar", "--decision", "segue"]), guards=["choice_in_package"])


def m5_orcamento_soft(h):
    acs = [("AC-%d" % i, p) for i, p in enumerate(["src/billing/a.py", "src/members/b.py", "src/billing/c.py",
                                                    "src/members/d.py", "src/billing/e.py"], 1)]
    ags = ["dev-billing", "dev-members"] * 3
    nodes = [N("%02d" % i, ags[i - 1], [acs[i - 1][1]], [acs[i - 1][0]], deps=(["%02d" % (i - 1)] if i > 1 else []))
             for i in range(1, 6)]
    root, d = running(h, acs=acs, nodes=nodes, orc="despachos=5,tentativas=20,replanos=3,minutos=600", nos=5)
    d.run()                                                                                # wrap_up RUNNING → hand_back
    _check(estado(h, root) == "HANDED_BACK", "80% de despachos → HANDED_BACK")


def m5_stop_humano_replanning_e_pausado(h):
    root, d, t = ate_replanning(h)
    a_ok(h, root, *hum(["stop", "--reason", "parou no replano"]))                          # wrap_up REPLANNING
    d.on_replan = None
    d.run()
    _check(estado(h, root) == "HANDED_BACK", "stop em REPLANNING → HANDED_BACK")
    root, d = running(h, acs=ACS2, nodes=NODES2)
    a_ok(h, root, "pause")
    a_ok(h, root, *hum(["stop", "--reason", "parou na pausa"]))                            # wrap_up PAUSED
    D(h, root).run()
    _check(estado(h, root) == "HANDED_BACK", "stop em PAUSED → HANDED_BACK")


def m5_sprint(h):
    root, spr, feas = repo(h, ACS2, features=[("Desconto", ["AC-1"]), ("Perfil", ["AC-2"])], start=False)
    a_ok(h, root, "propose", "--sprint", spr, "--spec", "spec/feature.md", "--objetivo", OBJ, "--nos", "4",
         "--regressao", REGRESSAO)
    a_ok(h, root, *hum(["approve", "--orcamento", ORC]))
    plans = {feas[0]: [N("01", "dev-billing", ["src/billing/discount.py"], ["AC-1"]),
                       N("02", "qa", ["tests/test_desc.py"], ["AC-1"], deps=["01"])],
             feas[1]: [N("04", "dev-members", ["src/members/profile.py"], ["AC-1"]),
                       N("05", "qa", ["tests/test_perfil.py"], ["AC-1"], deps=["04"])]}
    d = D(h, root)
    d.mode["01"] = "partial"
    d.on_plan = lambda dd, t: submit(h, root, plans[t["feature"]], drv=dd)
    d.on_replan = lambda dd, t: submit(h, root, [N("03", "dev-billing", ["src/billing/discount.py"], ["AC-1"])],
                                       motivo="AC-1 vermelho", ev=t["evidencia"][0]["ref"], drv=dd)

    def final(dd, t):
        a_no(h, root, "final-review", "--by", "dev-billing", "--verdict", "PASS", "--findings", "eu",
             guards=["final_review_pass"])
    d.on_final = final
    d.run(n=240)
    _check(estado(h, root) == "DONE", "sprint com 2 features → DONE (next_feature)")


def m5_sem_progresso(h):
    acs = [("AC-1", "src/billing/a.py"), ("AC-2", "src/members/b.py")]
    root, d = running(h, acs=acs, nodes=[N("01", "dev-billing", ["src/billing/a.py"], ["AC-1"]),
                                         N("02", "dev-members", ["src/members/b.py"], ["AC-2"])],
                      orc="despachos=40,tentativas=80,replanos=5,minutos=600")
    d.default = "abstain"
    seq = [2]

    def on_replan(dd, t):
        a, b = "%02d" % (seq[0] + 1), "%02d" % (seq[0] + 2)
        seq[0] += 2
        submit(h, root, [N(a, "dev-billing", ["src/billing/a%s.py" % a], ["AC-1"]),
                         N(b, "dev-members", ["src/members/b%s.py" % b], ["AC-2"])],
               motivo="abstenção", ev=t["evidencia"][0]["ref"], drv=dd)
    d.on_replan = on_replan
    d.run()                                                                                # wrap_up INTEGRATING (no_progress)
    _check(estado(h, root) == "HANDED_BACK", "sem progresso → HANDED_BACK")


CENARIOS = [m5_proposta_aprovacao_emenda_aborto, m5_plano_recusas, m5_fluxo_feliz_com_pausas,
            m5_replano_recusas_escalada_e_pausa, m5_replano_acima_do_orcamento, m5_replanos_esgotados, m5_regressao,
            m5_escalada_em_planning_e_stop, m5_escalada_local_e_saidas_humanas, m5_hack, m5_orcamento_soft,
            m5_stop_humano_replanning_e_pausado, m5_sprint, m5_sem_progresso]
