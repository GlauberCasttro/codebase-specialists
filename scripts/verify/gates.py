"""`cs.py verify` — gates G1–G16 (ARCHITECTURE §8-bis…§9) chamando os checks que já existem.

Cada gate vira {id, name, passed, evidence, command}. Gate sem como medir neste alvo = passed:false com
evidence "não medido: …" (nunca omitido). G9–G12, G14, G15 e parte de G16 são propriedades do motor da
skill (o mesmo código instalado no alvo): medidos pelas suítes da própria skill — nunca por script do alvo.
Saída: <alvo>/.swarm/acceptance.json5 {gates[], decision: GO|NO-GO, at, commit}.
"""
import os
import subprocess
import sys

from cslib import gitx, json5io
from facts import store

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CS = os.path.join(SCRIPTS, "cs.py")
TIMEOUT = 900
PRE_VALIDATE = ("init", "scan", "specialize", "round-table-deep-specialize")

GATES = [
    ("G1", "cobertura: todo arquivo de produto com 1 dono; escritores disjuntos"),
    ("G2", "existência: Existence Ratio = 1,0"),
    ("G3", "anti-template: similaridade ≤ 0,35 com o repo de controle"),
    ("G4", "maestria: sonda por agente (território/cross/alucinação/delta)"),
    ("G5", "operação: ≥1 comando de teste verified ou ausência declarada"),
    ("G6", "harness: validador verde e guards bloqueiam sondas negativas"),
    ("G7", "plataformas: artefatos emitidos passam no validador de formato"),
    ("G8", "memória: recall@5 ≥ 0,9 e p95 < 200 ms"),
    ("G9", "sessão: load ≤2k tokens, delta, round-trip idempotente"),
    ("G10", "delegação: transição inválida recusada, despacho sem brief/colisão bloqueado"),
    ("G11", "autonomia: loop, escalada e proibições do modo autônomo"),
    ("G12", "processo: DoR/DoD, Bug sem teste não fica READY, rollup"),
    ("G13", "mapas: árvore, stack × lockfile, deps × grafo, colisão"),
    ("G14", "roteamento: tier barato no trivial, gate ≥ autor, sem model bloqueia"),
    ("G15", "autocorreção: lição injetada, check reprova, promoção, teto"),
    ("G16", "etapas: load ≤2k, done não avança com check falho, retomada"),
]


def _run(argv, cwd, env_extra=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env.pop("CLAUDE_PROJECT_DIR", None)
    if env_extra:
        env.update(env_extra)
    try:
        p = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           stdin=subprocess.DEVNULL, env=env, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return 124, "timeout de %ss" % TIMEOUT
    out = (p.stdout or b"").decode("utf-8", "replace").strip().splitlines()
    return p.returncode, " | ".join(out[-3:])[:400]


def cs(target, *args):
    argv = [sys.executable, CS, "--target", target] + list(args)
    code, tail = _run(argv, target)
    return code, tail, "cs.py " + " ".join(args)


def suite(pkg, pattern, klass=None):
    argv = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", pattern]
    if klass:
        argv += ["-k", klass]
    code, tail = _run(argv, os.path.join(SCRIPTS, pkg))
    return code, tail, "cd scripts/%s && python3 -m unittest discover -s tests -p %s%s" % (
        pkg, pattern, (" -k " + klass) if klass else "")


def gate(gid, name, passed, evidence, command):
    return {"id": gid, "name": name, "passed": bool(passed), "evidence": evidence, "command": command}


def _combine(gid, name, runs):
    ok = all(c == 0 for c, _, _ in runs)
    ev = "; ".join("exit %d: %s" % (c, t) for c, t, _ in runs)
    return gate(gid, name, ok, ev, " && ".join(cmd for _, _, cmd in runs))


def g1(target, name):
    code, tail, cmd = cs(target, "team", "validate", "--stage", "final")
    if code not in (0, 1):
        return gate("G1", name, False, "não medido: team validate exit %d (%s)" % (code, tail), cmd)
    rep = store.read5(store.sp(target, "team-validation.json5"), required=False, default=None)
    r3 = ((rep or {}).get("rules") or {}).get("3")
    if not r3:
        return gate("G1", name, False, "não medido: team-validation.json5 sem regra 3 (%s)" % tail, cmd)
    ok = r3.get("status") == "PASS"
    ev = "regra 3 %s: cobertura %s, sobreposições %s%s" % (r3.get("status"), r3.get("coverage"), r3.get("overlaps"),
                                                         ("; " + r3["errors"][0]) if r3.get("errors") else "")
    return gate("G1", name, ok, ev, cmd)


def g3(target, name, control):
    from probes.antitemplate import DEFAULT_CONTROL
    control = control or DEFAULT_CONTROL  # iteração 1: G3 ficava "não medido" sem fonte de controle
    if not os.path.exists(control):
        return gate("G3", name, False, "não medido: controle ausente (%s)" % control,
                    "cs.py probes antitemplate --control <T>")
    c, t, cmd = cs(target, "probes", "antitemplate", "--control", control)
    return gate("G3", name, c == 0, "exit %d: %s" % (c, t), cmd)


def g5(target, name):
    cmd = "leitura de .swarm/facts/operations.json5"
    ops = store.read5(os.path.join(store.facts_dir(target), "operations.json5"), required=False, default=None)
    if ops is None:
        return gate("G5", name, False, "não medido: operations.json5 ausente (scan L7)", cmd)
    tests = [c for c in ops.get("commands") or [] if c.get("kind") == "test"]
    tests += [dict(f.get("data") or {}, cmd=(f.get("data") or {}).get("command")) for f in ops.get("facts") or []
              if (f.get("data") or {}).get("kind") == "test"]
    ver = [c for c in tests if c.get("status") == "verified"]
    unav = [c for c in tests if c.get("status") == "unavailable"]
    absent = [f for f in ops.get("facts") or [] if f.get("id") == "ops.test.absent"]
    if ver:
        return gate("G5", name, True, "%d comando(s) de teste verified (ex.: `%s` exit %s)" % (
            len(ver), ver[0].get("cmd") or ver[0].get("command"), ver[0].get("exit")), cmd)
    if absent:
        return gate("G5", name, True, "ausência declarada: fato ops.test.absent", cmd)
    if unav:  # existe e é declarado no repo; o ambiente do scan não tem a ferramenta — declaração, nunca verified
        u = unav[0]
        tools = sorted(set(str(c.get("missing_tool") or "?") for c in unav))
        return gate("G5", name, True, "declaração explícita: comando de teste existe e é declarado (`%s`), "
                    "toolchain ausente no ambiente (%s); NÃO executado" % (
                        u.get("cmd") or u.get("command"), ", ".join(tools)), cmd)
    return gate("G5", name, False, "%d comando(s) de teste, nenhum verified e sem declaração de ausência" % len(tests),
                cmd)


def g13(target, name):
    cmd = "emit.maps.check_maps (parte de `cs.py emit validate`)"
    try:
        from emit import maps
        from emit.team import load_team
        team = load_team(target)
        _, data = maps.build(target, team)
        errs = maps.check_maps(target, data)
    except Exception as exc:  # entrada inválida vira gate vermelho com o motivo
        return gate("G13", name, False, "não medido: %s" % exc, cmd)
    col = store.read5(store.sp(target, "knowledge", "collision.json5"), required=False, default=None) or {}
    ev = "%d erro(s) de mapa%s; do_not_parallelize=%d" % (len(errs), (": " + errs[0]) if errs else "",
                                                           len(col.get("do_not_parallelize") or []))
    return gate("G13", name, not errs, ev, cmd)


def g16(target, name):
    run = store.read5(store.sp(target, "run.json5"), required=False, default=None)
    if run is None:
        st = (1, "run.json5 ausente", "leitura de .swarm/run.json5")
    else:
        notdone = [s for s in PRE_VALIDATE if ((run.get("stages") or {}).get(s) or {}).get("status") != "done"]
        st = (1 if notdone else 0, ("etapas não fechadas: %s" % ", ".join(notdone)) if notdone else
              "etapas %s fechadas" % ", ".join(PRE_VALIDATE), "leitura de .swarm/run.json5")
    return _combine("G16", name, [st, suite("stage", "test_*.py")])


def run_gates(target, control=None):
    names = dict(GATES)
    out = []
    out.append(g1(target, names["G1"]))
    c, t, cmd = cs(target, "probes", "existence")
    out.append(gate("G2", names["G2"], c == 0, "exit %d: %s" % (c, t), cmd))
    out.append(g3(target, names["G3"], control))
    c, t, cmd = cs(target, "probes", "check", "--all", "--final")
    out.append(gate("G4", names["G4"], c == 0, "exit %d: %s" % (c, t), cmd))
    out.append(g5(target, names["G5"]))
    c, t, cmd = cs(target, "harness", "selftest")
    out.append(gate("G6", names["G6"], c == 0, "exit %d: %s" % (c, t), cmd))
    c, t, cmd = cs(target, "emit", "validate")
    out.append(gate("G7", names["G7"], c == 0, "exit %d: %s" % (c, t), cmd))
    c, t, cmd = cs(target, "probes", "memory-recall")
    out.append(gate("G8", names["G8"], c == 0, "exit %d: %s" % (c, t), cmd))
    out.append(_combine("G9", names["G9"], [suite("harness", "test_router_session.py", "TestSession")]))
    out.append(_combine("G10", names["G10"], [suite("harness", "test_machines.py", "TestM2M3"),
                                               suite("harness", "test_machines.py", "TestM1"),
                                               suite("harness", "test_guards.py", "TestAgentGuard")]))
    out.append(_combine("G11", names["G11"], [suite("harness", "test_autonomy_install.py", "TestAutonomy")]))
    out[-1]["evidence"] += " (parcial: eval end-to-end de evals/ não roda no verify)"
    out.append(_combine("G12", names["G12"], [suite("harness", "test_machines.py", "TestProcess")]))
    out.append(g13(target, names["G13"]))
    out.append(_combine("G14", names["G14"], [suite("harness", "test_router_session.py", "TestRouter")]))
    out.append(_combine("G15", names["G15"], [suite("memory", "test_mem.py", "TestLessons")]))
    out.append(g16(target, names["G16"]))
    return out


INPUTS = (("team", ("team.json5",)), ("bank", ("probes", "bank.json5")), ("emit_manifest", ("emit", "manifest.json5")),
          ("facts_index", ("facts", "index.json5")), ("harness_manifest", ("harness", "MANIFEST.json5")))
ADVISORY = ("cursor", "copilot", "codex")


def inputs_sha(target):
    """O que o acceptance avaliou: team, banco de sondas, artefatos emitidos, fatos e motor do harness.
    Mudou depois do verify → o acceptance está velho (validate.6/approve não fecham sobre ele)."""
    return {k: store.sha256_file(store.sp(target, *parts)) for k, parts in INPUTS}


def run_platforms(target):
    run = store.read5(store.sp(target, "run.json5"), required=False, default=None) or {}
    plats = run.get("platforms")
    if not plats:
        team = store.read5(store.sp(target, "team.json5"), required=False, default=None) or {}
        plats = team.get("platforms") or []
    return list(plats)


def enforcement(target):
    """{plataforma: hook|instructions} (contrato `enforcement`). `hook` = bloqueio ANTES da escrita (Claude Code
    com cs-guard instalado no .claude/settings.json); `instructions` = instrução + estado por CLI + detecção
    DEPOIS (verify/cs-precommit) — Cursor, Copilot e Codex, e Claude Code sem os hooks instalados."""
    out = {}
    for p in run_platforms(target):
        mode = "instructions"
        if p == "claude-code":
            sp = os.path.join(target, ".claude", "settings.json")
            wrapper = os.path.join(target, ".claude", "hooks", "cs-guard.sh")
            try:
                with open(sp, "r", encoding="utf-8") as fh:
                    hooked = "cs-guard.sh" in fh.read()
            except OSError:
                hooked = False
            if hooked and os.path.isfile(wrapper):
                mode = "hook"
        out[p] = mode
    return out


def acceptance_sha(acc):
    """sha do acceptance SEM o registro da aprovação (approve grava `approval` no próprio arquivo)."""
    core = {k: v for k, v in (acc or {}).items() if not str(k).startswith("approval")}
    return store.sha256_obj(core)


def freshness(target, acc):
    """→ problema ou None: acceptance avaliado sobre as entradas ATUAIS."""
    want = (acc or {}).get("inputs")
    if not want:
        return "acceptance.json5 sem `inputs` (verify antigo): rode `cs.py verify` de novo"
    cur = inputs_sha(target)
    diff = sorted(k for k in set(want) | set(cur) if want.get(k) != cur.get(k))
    if diff:
        return "acceptance velho: %s mudou depois do verify — rode `cs.py verify` de novo" % ", ".join(diff)
    return None


def recorded_check(target):
    """`cs.py verify --recorded` (check de validate.6): o verify rodou sobre o estado atual e gravou GO ou
    NO-GO. NO-GO fecha validate: a decisão (inclusive o NO-GO formal) é do founder em approve."""
    acc = store.read5(store.sp(target, "acceptance.json5"), required=False, default=None)
    if acc is None:
        return False, "acceptance.json5 ausente (rode `cs.py verify`)"
    if acc.get("decision") not in ("GO", "NO-GO"):
        return False, "acceptance sem decisão"
    why = freshness(target, acc)
    if why:
        return False, why
    red = [g["id"] for g in acc.get("gates") or [] if not g.get("passed")]
    return True, "verify registrado: %s%s" % (acc["decision"], (" (vermelhos: %s)" % ", ".join(red)) if red else "")


def non_specialists(target):
    """decisoes.regra_go: agentes do probes/report.json5 que NÃO são `especialista` (nao-especialista aceito ou não,
    em-refino, reprovado) → [(agente, status)]. Sem relatório de sondas: [] (o G4 já reprova por si)."""
    rep = store.read5(store.sp(target, "probes", "report.json5"), required=False, default=None) or {}
    out = []
    for a, r in sorted((rep.get("agents") or {}).items()):
        r = r or {}
        st = r.get("status")
        if st is not None:
            if st != "especialista":
                out.append((a, st))
        elif r.get("decision") is not None and r.get("decision") != "PASS":
            out.append((a, "reprovado"))
    return out


def stale_exams(target):
    """[(agente, motivo)]: exame aprovado feito sobre um cartão diferente do atual (probes/cycles.json5 ×
    team.json5). Entrada ilegível = o próprio G4 já reprova; aqui não derruba o verify."""
    from probes.final import pending_reexam
    try:
        return pending_reexam(target)
    except Exception as exc:  # noqa: BLE001 — vira evidência, nunca exceção
        return [("?", "não medido: %s" % exc)]


def verify(target, control=None, gates_fn=None):
    gates = (gates_fn or run_gates)(target, control)
    ids = [g["id"] for g in gates]
    want = [g for g, _ in GATES]
    for gid, name in GATES:  # nunca omitir um gate
        if gid not in ids:
            gates.append(gate(gid, name, False, "não medido", ""))
    gates.sort(key=lambda g: want.index(g["id"]) if g["id"] in want else 99)
    # regra_go: qualquer agente não especialista (inclusive nao-especialista ACEITO por --allow-non-specialist)
    # ⇒ G4 vermelho e NO-GO — mesmo estado, mesmo veredito em qualquer alvo
    ns = non_specialists(target)
    if ns:
        for g in gates:
            if g["id"] == "G4":
                g["passed"] = False
                g["evidence"] = ("regra_go: %s não é especialista — GO exige todos especialistas; " % ", ".join(
                    "%s (%s)" % x for x in ns)) + (g.get("evidence") or "")
    # exame ligado ao hash do cartão examinado: cartão mudou depois do exame aprovado ⇒ G4 PENDENTE (reexame)
    pend = stale_exams(target)
    if pend:
        for g in gates:
            if g["id"] == "G4":
                g["passed"] = False
                g["evidence"] = ("G4 PENDENTE (reexame): %s; " % "; ".join("%s — %s" % x for x in pend)) + (
                    g.get("evidence") or "")
    decision = "GO" if all(g["passed"] for g in gates) and not ns and not pend else "NO-GO"
    doc = {"schema_version": 1, "gates": gates, "decision": decision, "at": store.now(),
           "commit": gitx.head(target) or "", "enforcement": enforcement(target), "inputs": inputs_sha(target),
           "non_specialist": [a for a, _ in ns], "pending_reexam": [a for a, _ in pend]}
    store.write5(target, store.sp(target, "acceptance.json5"), doc,
                 "acceptance.json5 — gates G1–G16 e decisão GO/NO-GO; gerado por cs.py verify")
    return doc


# ------------------------------------------------------------------ approve

def approvals_path(target):
    return store.sp(target, "approvals.jsonl")


def approve(target, by, decision, note, simulated=False):
    """Decisão do founder (contrato `aprovacao`): `--simulated` quando não há humano (eval/CI) — o acceptance ganha
    `approval: human|simulated` e o relatório mostra `GO (simulado)`. NO-GO é sempre registrável (NO-GO formal)."""
    from cslib import CsError
    if not (by or "").strip():
        raise CsError("--by vazio", "nome de quem decide (founder)")
    if decision not in ("GO", "NO-GO"):
        raise CsError("--decision deve ser GO|NO-GO")
    ap = store.sp(target, "acceptance.json5")
    acc = store.read5(ap, required=False, default=None)
    if acc is None:
        raise CsError("acceptance.json5 ausente", "rode `cs.py verify` antes da aprovação")
    kind = "simulated" if simulated else "human"
    rec = {"ts": store.now(), "by": by.strip(), "decision": decision, "note": (note or "").strip(),
           "approval": kind, "acceptance_sha256": acceptance_sha(acc), "acceptance_decision": acc.get("decision"),
           "acceptance_at": acc.get("at")}
    store.append_jsonl(target, approvals_path(target), rec)
    acc.update({"approval": kind, "approval_decision": decision, "approval_by": rec["by"], "approval_at": rec["ts"]})
    store.write5(target, ap, acc, "acceptance.json5 — gates G1–G16 e decisão GO/NO-GO; gerado por cs.py verify "
                                  "(approval* gravado por cs.py approve)")
    return rec, acc


def approve_check(target, recorded=False):
    """→ (ok, mensagem). Padrão: GO do founder sobre acceptance GO. `recorded` (check de approve.2): uma decisão
    registrada sobre o acceptance ATUAL — GO (exige acceptance GO) ou NO-GO formal."""
    ap = store.sp(target, "acceptance.json5")
    acc = store.read5(ap, required=False, default=None)
    if acc is None:
        return False, "acceptance.json5 ausente (rode `cs.py verify`)"
    why = freshness(target, acc) if acc.get("inputs") else None
    if why:
        return False, why
    if acc.get("decision") != "GO" and not recorded:
        red = [g["id"] for g in acc.get("gates") or [] if not g.get("passed")]
        return False, "acceptance é %s (gates vermelhos: %s)" % (acc.get("decision"), ", ".join(red))
    recs = [r for _, r in store.read_jsonl(approvals_path(target))]
    if not recs:
        return False, "nenhuma decisão do founder registrada (`cs.py approve --by <nome> --decision GO|NO-GO`)"
    last = recs[-1]
    if last.get("acceptance_sha256") not in (acceptance_sha(acc), store.sha256_file(ap)):
        return False, "acceptance.json5 mudou depois da última decisão do founder (%s); aprove de novo" % last.get("ts")
    if str(last.get("ts")) < str(acc.get("at")):
        return False, "decisão do founder é anterior ao acceptance.json5"
    label = "%s%s" % (last.get("decision"), " (simulado)" if last.get("approval") == "simulated" else "")
    if last.get("decision") == "GO" and acc.get("decision") != "GO":
        return False, "founder registrou GO sobre acceptance NO-GO — registre NO-GO (ou corrija os gates)"
    if recorded:
        return True, "decisão %s de %s em %s" % (label, last.get("by"), last.get("ts"))
    if last.get("decision") != "GO":
        return False, "founder decidiu %s em %s%s" % (last.get("decision"), last.get("ts"),
                                                   (": " + last["note"]) if last.get("note") else "")
    return True, "%s aprovado por %s em %s" % (label, last.get("by"), last.get("ts"))


def dumps(doc):
    return json5io.dumps(doc, "cs.py verify")
