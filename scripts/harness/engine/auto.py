#!/usr/bin/env python3
"""cs-auto — piloto do modo autônomo `mandato` (máquina M5 em machines.json5 → machines.mandato).

Princípio do founder: TUDO que é mecânico é deste script — próxima ação, ondas, verify, accept, close de task,
integração (regressão + aceite por critério), progresso, orçamento (corte de 80%), parada, escalada, retomada e órfãos.
O modelo só executa os nós de julgamento que o `tick` pede (PLAN/REPLAN, DISPATCH, REVIEW, REFLECT, FINAL_REVIEW,
ANSWER_ORPHAN). Portões HUMANOS (approve, amend, resolve, stop, abort) exigem `--by <humano>` e o guard bloqueia o
modelo de rodá-los. O `approve` exige ainda a SENHA do humano digitada no terminal (engine/senha.py: stdin tty +
/dev/tty sem eco; nada por argumento, ambiente ou pipe) e grava no evento `mandato.approve` um SELO HMAC (mandato,
hash do plano, orçamento, seq, ts). `senha definir` e `conferir` (recalcula as HMACs) também são atos humanos.
Antes de qualquer avanço o motor confere o selo do último approve na cadeia (formato, mandato, orçamento e hash do
plano atual); sem a senha ele NÃO verifica a HMAC — só o `cs-auto conferir` do humano verifica.

Toda transição de M5 passa por engine.transition (guardas em engine.GUARDS, eventos encadeados `mandato.<transição>` com
`de`, `para`, `guardas` e, na recusa interna, `guardas_recusadas`). Recusa pela CLI: exit 1 com `guarda <nome>: <problema>`
no stderr. Relógio: CS_NOW (hcore.now_dt). Estado em árvore (iter10): os nós do plano viram tasks da feature ativa.

  cs-auto propose|approve|amend|abort|stop|resolve|tick|status|plan|reflect|orphan|final-review|escalate|pause|resume|
          spend|report|senha definir|conferir   (python3 auto.py --root <alvo> ...; ver ESPEC campanha-M5 §2.3)
"""
import argparse
import copy
import hmac
import json
import os
import re
import shlex
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(os.path.dirname(os.path.dirname(HERE)), "memory")):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import hcore  # noqa: E402
import j5  # noqa: E402
import engine  # noqa: E402
import senha  # noqa: E402
from hcore import Refused, StateError  # noqa: E402

KIND = "mandato"
W = ("PLANNING", "RUNNING", "INTEGRATING", "REPLANNING")
TERMINAL = ("DONE", "HANDED_BACK", "ABORTED")
COUNTED = ("CHARTERED",) + W + ("WRAPPING_UP",)
WAITING = ("PROPOSED", "AWAITING_HUMAN", "PAUSED")
FLIGHT = ("DISPATCHED", "RETURNED", "VERIFIED", "REVIEWED")
OPCOES = ("retomar", "trocar-agente", "emendar", "descartar-ramo", "encerrar", "abortar")
OPCOES_SEM_NO = ("retomar", "emendar", "encerrar", "abortar")
OPCOES_ALTERADO = ("emendar", "encerrar", "abortar")
CHOICE_TR = {"retomar": "resolve_resume", "trocar-agente": "resolve_reroute", "descartar-ramo": "resolve_drop",
             "emendar": "amend", "encerrar": "wrap_up", "abortar": "abort"}
HUMAN_CMDS = ("approve", "amend", "abort", "stop", "resolve", "senha", "conferir")
PROOF_CMDS = ("amend", "abort", "stop", "resolve")   # aceitam argumentos extras ($CS_HUMAN_PROOF_ARGS legado); approve NÃO
# avanços autônomos: só passam com o selo da aprovação conferido (formato, mandato, orçamento, hash do plano)
ADVANCE_TR = ("plan", "plan_accept", "tick", "wave_closed", "integrate_ok", "integrate_replan", "integrate_done",
              "next_feature", "replan_accept", "resume")
PLANO_KEYS = ("alvo", "features", "spec", "objetivo", "classe", "rigor", "portoes", "regressao", "criterios")
CLASSES_OK = ("feature", "risco")
CLASSES_AVULSA = ("pequena", "trivial")
HEADER = "gerado por cs-auto (motor do mandato) — não editar à mão: cs-state validate acusa a edição"
PROTECT_MARK = "aceite/spec assinado do mandato"
RUNNABLE = ("novo", "planejado", "pronto", "rejeitado", "trocar")
PIPE = ("voo", "retornado", "verificado", "revisado")
SETTLED_BAD = ("descartado", "travado", "congelado", "devolvido", "bloqueado", "sem_task")
STOP_MAX_BLOCKS = 3
TEST_ID_RE = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)+$")
FAIL_RE = re.compile(r"^(?:FAIL|ERROR): \S+ \(([\w.]+)\)", re.M)
PYTEST_FAIL_RE = re.compile(r"^FAILED (\S+\.py)(?:::\S+)?", re.M)
NODE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,15}$")


class Syntax(Exception):
    """Erro de sintaxe do comando (exit 2, como o argparse)."""


def G(name, msg):
    return "guarda %s: %s" % (name, msg)


def M():
    return hcore.machines()["machines"][KIND]


def mcfg(key, default=None):
    return M().get(key, default)


# ================================================================ leitura
def all_mandates(board):
    return board.get("mandatos") or []


def current(board):
    ms = all_mandates(board)
    return ms[-1] if ms else None


def open_mandate(board):
    for m in reversed(all_mandates(board)):
        if m.get("state") not in TERMINAL:
            return m
    return None


def ctx_of(root, actor="lead"):
    return engine.Ctx(root, hcore.load_board(root), actor)


def view(ctx):
    import tree
    return tree.T(ctx, dry=True)


def pasta_rel(m):
    z = "archive" if m.get("state") in TERMINAL else "state"
    return "%s/%s/mandatos/%s" % (hcore.STATE_DIR, z, m["id"])


def draft_path(root, mid):
    return os.path.join(hcore.state_paths(root)["state_dir"], "mandatos", "%s.rascunho.json5" % mid)


def stop_path(root):
    return os.path.join(hcore.state_paths(root)["state_dir"], "mandatos", "stop-hook.json5")


def plano_nos(m):
    return list(((m.get("plano") or {}).get("nos")) or [])


def feature_nos(m, fea=None):
    fea = fea or m.get("feature_ativa")
    return [n for n in plano_nos(m) if n.get("feature") == fea]


def criterios_de(m, fea=None):
    fea = fea or m.get("feature_ativa")
    return [c for c in m.get("criterios") or [] if c.get("feature") == fea]


def timeout_of(root):
    try:
        return int(hcore.load_config(root).get("verify_timeout_s", 900))
    except Exception:
        return 900


def _parse_dt(s):
    if not s:
        return None
    from datetime import datetime, timezone
    try:
        v = s[:-1] + "+00:00" if s.endswith("Z") else s
        d = datetime.fromisoformat(v)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def clock(m):
    """Minutos ATIVOS: soma só os intervalos em estado de trabalho, cada um limitado (lacuna longa não conta)."""
    rel = dict(m.get("relogio") or {})
    now = hcore.now_dt()
    prev = _parse_dt(rel.get("visto_em"))
    mins = float(rel.get("minutos") or 0)
    if prev is not None and m.get("state") in COUNTED:
        delta = max(0.0, (now - prev).total_seconds() / 60.0)
        mins += min(delta, float(mcfg("active_gap_cap_min", 10)))
    return {"minutos": round(mins, 4), "visto_em": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")}


def S(mid, field, value):
    return ["set", engine.ref(KIND, mid), field, value]


# ================================================================ critérios, testes, medição
def test_file(root, test_id):
    parts = test_id.split(".")
    for k in range(len(parts), 0, -1):
        rel = "/".join(parts[:k])
        if os.path.isfile(os.path.join(root, rel + ".py")):
            return rel + ".py"
        if k == len(parts) and os.path.isfile(os.path.join(root, rel, "__init__.py")):
            return rel + "/__init__.py"
    return None


def cmd_files(root, cmd):
    out = []
    try:
        toks = shlex.split(cmd or "")
    except ValueError:
        toks = (cmd or "").split()
    for t in toks:
        f = None
        if TEST_ID_RE.match(t):
            f = test_file(root, t)
        elif "/" in t and os.path.isfile(os.path.join(root, t)):
            f = hcore.norm_rel(t)
        if f and f not in out:
            out.append(f)
    return out


def crit_files(root, c):
    if c.get("teste"):
        f = test_file(root, c["teste"])
        return [f] if f else []
    return cmd_files(root, c.get("cmd"))


def crit_exec_problem(root, c):
    if c.get("teste"):
        if not test_file(root, c["teste"]):
            return "%s: teste %s não existe (nenhum arquivo resolve o test-id)" % (c["id"], c["teste"])
        return None
    ep = engine.executable_problem(root, c.get("cmd") or "")
    return ("%s: %s" % (c["id"], ep)) if ep else None


def parse_criterios(root, cfg, items, feature):
    out = []
    for i, raw in enumerate(items or []):
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) == 2:
            parts = ["AC-%d" % (i + 1)] + parts
        if len(parts) != 3 or not parts[0] or not parts[2]:
            raise Syntax("--criterio deve ser 'AC-n|Dado … Quando … Então …|<test-id ou comando>': %r" % raw)
        cid, texto, ref = parts
        c = {"id": cid, "texto": texto.replace("|", "/"), "feature": feature}
        if " " in ref:
            c["comando"] = ref
            c["cmd"] = ref
        else:
            c["teste"] = ref
            c["cmd"] = engine.resolve_test(cfg, ref) or ref
        out.append(c)
    return out


def falhas(root, text):
    out = []
    for full in FAIL_RE.findall(text or ""):
        parts = full.split(".")
        ident = full
        for k in range(len(parts), 0, -1):
            if os.path.isfile(os.path.join(root, "/".join(parts[:k]) + ".py")):
                ident = ".".join(parts[:k])
                break
        if ident not in out:
            out.append(ident)
    for f in PYTEST_FAIL_RE.findall(text or ""):
        if f not in out:
            out.append(f)
    return out


def medir(root, m, fea=None, todos=False, regressao=True, crits=None):
    T = timeout_of(root)
    if crits is None:
        crits = (m.get("criterios") or []) if todos else criterios_de(m, fea)
    aceite = []
    for c in crits:
        r = engine.run_cmd(root, c["cmd"], T)
        aceite.append({"id": c["id"], "feature": c.get("feature"), "verde": r["exit_code"] == 0, "exit": r["exit_code"],
                       "output_sha256": r["output_sha256"], "cmd": c["cmd"]})
    reg = None
    if regressao and m.get("regressao"):
        r = engine.run_cmd(root, m["regressao"], T)
        reg = {"exit": r["exit_code"], "output_sha256": r["output_sha256"], "falhas": falhas(root, r["tail"]),
               "cmd": m["regressao"], "tail": (r.get("tail") or "")[-500:]}
    return {"aceite": aceite, "regressao": reg, "at": hcore.now_iso(), "feature": fea}


def reg_ok(m, reg):
    if not reg:
        return True
    if reg.get("exit") == 0:
        return True
    base = ((m.get("baseline") or {}).get("regressao")) or {}
    if base.get("exit") not in (0, None):
        return set(reg.get("falhas") or []) <= set(base.get("falhas") or []) and bool(reg.get("falhas"))
    return False


# ================================================================ ondas e DAG
def node_conflict(ctx, a, b):
    if a.get("agent") == b.get("agent"):
        return "mesmo agente"
    if hcore.scopes_overlap(a.get("paths") or [], b.get("paths") or []):
        return "arquivo comum"
    r = engine.collision_reason(ctx, a.get("agent"), b.get("agent"))
    return r or None


def compute_waves(ctx, nodes):
    """Camadas topológicas × coloração (arquivo comum, do_not_parallelize, mesmo agente); ids em ordem estável."""
    by = dict((n["id"], n) for n in nodes)
    layer = {}

    def lay(i, seen=()):
        if i in layer:
            return layer[i]
        if i in seen:
            return 0
        ds = [d for d in by[i].get("deps") or [] if d in by]
        layer[i] = 0 if not ds else 1 + max(lay(d, seen + (i,)) for d in ds)
        return layer[i]
    for i in by:
        lay(i)
    out = []
    for L in sorted(set(layer.values())):
        subs = []
        for i in sorted([x for x in by if layer[x] == L]):
            for sw in subs:
                if not any(node_conflict(ctx, by[i], by[j]) for j in sw):
                    sw.append(i)
                    break
            else:
                subs.append([i])
        out += subs
    return out


def find_cycle(nodes):
    by = dict((n["id"], n) for n in nodes)
    color = {}
    stack = []

    def dfs(i):
        color[i] = 1
        stack.append(i)
        for d in by[i].get("deps") or []:
            if d not in by:
                continue
            if color.get(d) == 1:
                return stack[stack.index(d):] + [d]
            if not color.get(d):
                c = dfs(d)
                if c:
                    return c
        stack.pop()
        color[i] = 2
        return None
    for i in sorted(by):
        if not color.get(i):
            c = dfs(i)
            if c:
                return c
    return None


def descendants(nodes, root_id):
    out = []
    frontier = [root_id]
    while frontier:
        cur = frontier.pop(0)
        for n in nodes:
            if cur in (n.get("deps") or []) and n["id"] not in out and n["id"] != root_id:
                out.append(n["id"])
                frontier.append(n["id"])
    return out


# ================================================================ nós: classificação (fonte única do agendamento)
def congelados(m):
    out = []
    for e in m.get("escaladas") or []:
        if e.get("aberta") and e.get("tipo") == "dura_local":
            for x in e.get("nos") or []:
                if x not in out:
                    out.append(x)
    return out


def open_escalations(m, tipo=None):
    return [e for e in m.get("escaladas") or [] if e.get("aberta") and (tipo is None or e.get("tipo") == tipo)]


def normalize_output(s):
    """Saída normalizada para "mesma falha": sem hashes, números (tempos, contagens) e espaços variáveis."""
    s = re.sub(r"[0-9a-f]{8,}", "#", s or "")
    s = re.sub(r"\d+", "#", s)
    return re.sub(r"\s+", " ", s).strip()


def verify_events(root):
    """{deleg_id: [(sig, agent?, exit)]} das verificações REPROVADAS (cadeia de eventos)."""
    recs, _, _ = hcore.read_chain(hcore.state_paths(root)["events"])
    out = {}
    for r in recs:
        if r.get("type") != "delegation.verify":
            continue
        d = r.get("data") or {}
        if not d.get("problems"):
            continue
        g = d.get("gate") or {}
        sig = hcore.sha256_bytes(("%s|%s|%s" % (g.get("exit_code"), normalize_output(g.get("tail")), "|".join(sorted(
            normalize_output(p) for p in d.get("problems") or [])))).encode("utf-8"))
        out.setdefault(r.get("entity"), []).append({"sig": sig, "exit": g.get("exit_code"), "seq": r.get("seq"),
                                                    "output_sha256": g.get("output_sha256"), "tail": g.get("tail"),
                                                    "problems": d.get("problems")})
    return out


def task_fail_history(t, vev):
    """Falhas de verify da task em ordem: [(agent, sig)]."""
    out = []
    for d in t.get("delegations") or []:
        for x in vev.get(d["id"]) or []:
            out.append((d["agent"], x["sig"], x["seq"]))
    return sorted(out, key=lambda x: x[2])


def alt_agent(ctx, n, t):
    used = {d["agent"] for d in t.get("delegations") or []}
    gates = hcore.gate_agents(ctx.team)
    for a in sorted(((ctx.team or {}).get("agents") or []), key=lambda x: x.get("name") or ""):
        name = a.get("name")
        if not name or name in gates or name in used or a.get("kind") == "gate":
            continue
        terr = list(a.get("territory") or [])
        if terr and all(hcore.pattern_within(p, terr) for p in t.get("allowed_paths") or n.get("paths") or []):
            return name
    return None


def classify(ctx, tv, m, fea=None, vev=None):
    import tree
    nodes = plano_nos(m)
    sel = [n for n in nodes if fea is None or n.get("feature") == fea]
    frozen = set(congelados(m))
    info = {}
    order = []
    for n in sel:
        it = tv.get(n.get("task")) if n.get("task") else None
        t = tv.m2(it) if (it and it.get("m2")) else None
        d = engine.latest_deleg(t) if t else None
        z = tree.zone_of(it["path"]) if it else None
        st = t["status"] if t else "DRAFT"
        ds = d["state"] if d else None
        if it is None:
            cls = "sem_task"
        elif n["id"] in frozen and st not in ("ACCEPTED", "DROPPED") and ds not in FLIGHT and \
                not (t is None and z == "backlog"):
            cls = "congelado"
        elif t is None:
            cls = "devolvido" if z == "backlog" else ("descartado" if it.get("closed") else "novo")
        elif st == "ACCEPTED":
            cls = "aceito"
        elif st == "DROPPED" or ds == "DROPPED":
            cls = "descartado"
        elif ds in FLIGHT:
            cls = {"DISPATCHED": "voo", "RETURNED": "retornado", "VERIFIED": "verificado", "REVIEWED": "revisado"}[ds]
        elif ds == "BRIEFED":
            cls = "pronto"
        elif ds == "PLANNED":
            cls = "planejado"
        elif ds == "REJECTED":
            cls = "rejeitado"
            if st == "BLOCKED":
                cls = "travado"
            else:
                if vev is None:
                    vev = verify_events(ctx.root)
                hist = task_fail_history(t, vev)
                if len(hist) >= 2 and hist[-1][0] == hist[-2][0] == d["agent"] and hist[-1][1] == hist[-2][1]:
                    cls = "trocar" if alt_agent(ctx, n, t) else "travado"
        else:
            cls = "travado"
        info[n["id"]] = {"n": n, "it": it, "t": t, "d": d, "status": st, "ds": ds, "cls": cls, "runnable": False}
        order.append(n["id"])
    allnodes = dict((n["id"], n) for n in nodes)
    for nid in order:
        x = info[nid]
        if x["cls"] not in RUNNABLE:
            continue
        deps = [d for d in x["n"].get("deps") or [] if d in allnodes]
        dcls = [info[d]["cls"] if d in info else "aceito" for d in deps]
        if all(c == "aceito" for c in dcls):
            x["runnable"] = True
        elif any(c in SETTLED_BAD for c in dcls):
            x["cls"] = "bloqueado"
        else:
            x["cls"] = "esperando"
    # 2ª passada: "esperando" atrás de um "bloqueado" também fica bloqueado
    changed = True
    while changed:
        changed = False
        for nid in order:
            x = info[nid]
            if x["cls"] == "esperando" and any(info.get(d, {}).get("cls") == "bloqueado" for d in x["n"].get("deps") or []):
                x["cls"] = "bloqueado"
                changed = True
    return info, order


def pending(info):
    return [nid for nid, x in info.items() if x["runnable"] or x["cls"] in ("esperando",) or x["cls"] in PIPE]


def nodes_in_pipeline(info):
    return [nid for nid, x in info.items() if x["cls"] in PIPE]


def authors(m, ctx=None, tv=None):
    out = set(n.get("agent") for n in plano_nos(m))
    if ctx is not None and tv is not None:
        for n in plano_nos(m):
            it = tv.get(n.get("task")) if n.get("task") else None
            t = tv.m2(it) if (it and it.get("m2")) else None
            for d in (t or {}).get("delegations") or []:
                out.add(d.get("agent"))
    return out


def pick_gate(ctx, m, tv=None, exclude=()):
    gates = sorted(hcore.gate_agents(ctx.team))
    au = authors(m, ctx, tv)
    for g in gates:
        if g not in au and g not in exclude:
            return g
    return gates[0] if gates else None


# ================================================================ orçamento
def usage(ctx, tv, m):
    desp = tent = 0
    for n in plano_nos(m):
        it = tv.get(n.get("task")) if n.get("task") else None
        t = tv.m2(it) if (it and it.get("m2")) else None
        if t:
            a = int(t.get("attempts") or 0)
            tent += a
            if a > 0:
                desp += 1
    if m.get("aprovado"):
        base = set(m.get("consultas_base") or [])
        desp += len([c for c in ctx.board.get("consults") or [] if c.get("id") not in base])
    gasto = m.get("gasto") or {}
    return {"despachos": desp, "tentativas": tent, "replanos": int(m.get("replanos") or 0),
            "minutos": float((m.get("relogio") or {}).get("minutos") or 0),
            "usd_medido": float(gasto.get("usd_medido") or 0), "usd_autodeclarado": float(gasto.get("usd_autodeclarado") or 0)}


def budget_ratio(m, u):
    o = m.get("orcamento") or {}
    worst, dim = 0.0, None
    for k, uk in (("despachos", "despachos"), ("tentativas", "tentativas"), ("minutos", "minutos"), ("usd", "usd_medido")):
        lim = o.get(k)
        if not lim:
            continue
        r = float(u[uk]) / float(lim)
        if r > worst:
            worst, dim = r, k
    return worst, dim


def orcamento_view(m, u):
    o = m.get("orcamento") or {}
    out = {}
    for k in ("despachos", "tentativas", "replanos", "minutos"):
        out[k] = {"usado": u[k] if k != "minutos" else round(u[k], 2), "limite": o.get(k)}
    out["usd"] = {"medido": u["usd_medido"], "autodeclarado": u["usd_autodeclarado"], "limite": o.get("usd")}
    return out


def derive_budget(n, rigor):
    n = max(2, int(n or 2))
    desp = 2 * n + 2
    return {"despachos": desp, "tentativas": 2 * desp, "replanos": {"lean": 1, "paranoid": 3}.get(rigor or "", 2),
            "minutos": max(60, 45 * n), "usd": None}


def parse_orcamento(s):
    out = {}
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise Syntax("--orcamento: use chave=valor (despachos=,tentativas=,replanos=,minutos=,usd=): %r" % part)
        k, v = [x.strip() for x in part.split("=", 1)]
        if k not in ("despachos", "tentativas", "replanos", "minutos", "usd"):
            raise Syntax("--orcamento: chave desconhecida %r" % k)
        try:
            f = float(v)
        except ValueError:
            raise Syntax("--orcamento: valor não numérico em %r" % part)
        out[k] = int(f) if f == int(f) and k != "usd" else f
    return out


# ================================================================ guardas M5 (registradas em engine.GUARDS por engine.M5_GUARDS)
def _contract(ent, a):
    return a.get("_contrato") or ent


def g_target_exists(ctx, kind, ent, a):
    import tree
    c = _contract(ent, a)
    alvo = c.get("alvo") or {}
    tv = view(ctx)
    it = tv.get(alvo.get("id") or "")
    want = alvo.get("tipo")
    if it is None or it.get("kind") != want:
        return [G("target_exists", "%s %s inexistente na árvore (cs-state find %s)" % (want, alvo.get("id"), alvo.get("id")))]
    if tree.zone_of(it["path"]) == "archive":
        return [G("target_exists", "%s %s está fechado (archive/)" % (want, it["id"]))]
    if want == "sprint" and not c.get("features"):
        return [G("target_exists", "sprint %s sem features abertas" % it["id"])]
    return []


def g_class_allowed(ctx, kind, ent, a):
    k = a.get("classe") or "feature"
    if k == "pergunta":
        return [G("class_allowed", "classe pergunta não tem entrega: use cs-state ask (faixa consulta)")]
    if k in CLASSES_AVULSA:
        return [G("class_allowed", "classe %s não precisa de mandato: use task avulsa (cs-state new task --avulsa ...)" % k)]
    if k not in CLASSES_OK:
        return [G("class_allowed", "classe %r desconhecida (feature|risco)" % k)]
    if k == "risco" and not a.get("portoes"):
        return [G("class_allowed", "classe risco exige --portao <glob> (o que só passa pelo portão humano)")]
    return []


def g_spec_present(ctx, kind, ent, a):
    spec = (_contract(ent, a).get("spec") or "").strip()
    if not spec or not os.path.isfile(os.path.join(ctx.root, spec)):
        return [G("spec_present", "spec %r inexistente (passe --spec <arquivo da spec>)" % spec)]
    return []


def g_acceptance_executable(ctx, kind, ent, a):
    c = _contract(ent, a)
    crits = c.get("criterios") or []
    if not crits:
        return [G("acceptance_executable", "nenhum critério de aceite (--criterio 'AC-n|texto|<test-id ou comando>')")]
    P = []
    for x in crits:
        p = crit_exec_problem(ctx.root, x)
        if p:
            P.append(G("acceptance_executable", p))
    return P


def _measure_once(ctx, ent, a):
    if a.get("_med") is None:
        c = _contract(ent, a)
        crits = [x for x in c.get("criterios") or [] if not crit_exec_problem(ctx.root, x)]
        a["_med"] = medir(ctx.root, c, crits=crits, regressao=False)
    return a["_med"]


def g_acceptance_red(ctx, kind, ent, a):
    med = _measure_once(ctx, ent, a)
    verdes = [x for x in med["aceite"] if x["verde"]]
    reaprov = bool(ent.get("aprovacoes")) if ent and ent.get("id") else False
    if not reaprov:
        return [G("acceptance_red", "%s já está verde (exit 0: %s) — critério verde não prova entrega" % (
            x["id"], x["cmd"])) for x in verdes]
    if med["aceite"] and len(verdes) == len(med["aceite"]):
        return [G("acceptance_red", "todos os critérios já estão verdes: nada a entregar (encerre ou aborte)")]
    tv = view(ctx)
    info, _ = classify(ctx, tv, ent, None)
    cov = set()
    for nid, x in info.items():
        if x["cls"] == "aceito":
            cov |= set(x["n"].get("cobre") or [])
    return [G("acceptance_red", "%s ficou verde sem nó ACCEPTED que o cubra" % x["id"]) for x in verdes if x["id"] not in cov]


def g_no_open_mandate(ctx, kind, ent, a):
    om = open_mandate(ctx.board)
    if om and om.get("id") != (ent or {}).get("id"):
        return [G("no_open_mandate", "%s ainda aberto (estado %s): um mandato por vez" % (om["id"], om.get("state")))]
    return []


def g_not_trivial(ctx, kind, ent, a):
    if "_plano" in a:
        if len(a["_plano"] or []) < 2:
            return [G("not_trivial", "plano de %d nó: mandato é para ≥2 nós — use task avulsa" % len(a["_plano"] or []))]
        return []
    try:
        n = int(a.get("nos") or 0)
    except (TypeError, ValueError):
        n = 0
    if n < 2:
        return [G("not_trivial", "--nos %s (<2): trabalho de 1 nó não precisa de mandato — use task avulsa" % (a.get("nos")))]
    return []


def human_proof_problems(ctx, a):
    """Requisito extra da guarda by_human: nenhum. A prova humana do `approve` é a SENHA digitada no terminal
    (cmd_approve → senha.pedir_chave, antes da transição) — nunca argumento: $CS_HUMAN_PROOF_ARGS está morto."""
    return []


def g_by_human(ctx, kind, ent, a):
    by = (a.get("by") or "").strip()
    if not by:
        return [G("by_human", "--by <humano> obrigatório: portão HUMANO (o modelo/orquestrador nunca o aprova)")]
    if by.lower() in engine.NOT_HUMAN or by == ctx.actor or (ctx.team and hcore.team_agent(ctx.team, by)):
        return [G("by_human", "--by %r não é humano: orquestrador/agentes/gates não passam por portão humano" % by)]
    return [G("by_human", p) for p in human_proof_problems(ctx, a)]


def _plan(a):
    return a.get("_plano") or []


def g_dag_acyclic(ctx, kind, ent, a):
    nodes = _plan(a) + list(a.get("_outros") or [])
    P = []
    seen = set()
    for n in nodes:
        if n["id"] in seen:
            P.append(G("dag_acyclic", "id de nó duplicado: %s" % n["id"]))
        seen.add(n["id"])
    for n in _plan(a):
        for d in n.get("deps") or []:
            if d not in seen:
                P.append(G("dag_acyclic", "nó %s depende de %s, que não existe no plano" % (n["id"], d)))
            if d == n["id"]:
                P.append(G("dag_acyclic", "nó %s depende de si mesmo" % n["id"]))
    cyc = find_cycle(_plan(a))
    if cyc:
        P.append(G("dag_acyclic", "ciclo nas dependências: %s" % " → ".join(cyc)))
    return P


def g_dag_covers(ctx, kind, ent, a):
    crits = a.get("_criterios") or []
    ids = [c["id"] for c in crits]
    P = []
    for n in _plan(a):
        for ac in n.get("cobre") or []:
            if ac not in ids:
                P.append(G("dag_covers_acceptance", "nó %s cobre %s, que não é critério do mandato (%s)" % (
                    n["id"], ac, ", ".join(ids))))
    if a.get("_replano"):
        red = a.get("_vermelhos") or []
        eleg = set(a.get("_elegiveis") or [])
        for ac in red:
            if not [n for n in _plan(a) if n["id"] in eleg and ac in (n.get("cobre") or [])]:
                P.append(G("dag_covers_acceptance", "critério %s segue vermelho e nenhum nó novo/pendente o cobre "
                           "(replano tem de atacar o vermelho)" % ac))
        return P
    for ac in ids:
        if not [n for n in _plan(a) if ac in (n.get("cobre") or [])]:
            P.append(G("dag_covers_acceptance", "critério %s sem nó que o cubra (--cobre %s)" % (ac, ac)))
    return P


def g_nodes_in_territory(ctx, kind, ent, a):
    P = []
    gates = hcore.gate_agents(ctx.team)
    for n in _plan(a):
        ag = n.get("agent")
        if not hcore.team_agent(ctx.team, ag):
            P.append(G("nodes_in_territory", "nó %s: agente %r não existe em team.json5" % (n["id"], ag)))
            continue
        if ag in gates:
            P.append(G("nodes_in_territory", "nó %s: %s é gate (gate não recebe task de escrita)" % (n["id"], ag)))
            continue
        terr = ctx.territory(ag)
        for p in n.get("paths") or []:
            try:
                rp = hcore.norm_rel(p)
            except StateError as e:
                P.append(G("nodes_in_territory", "nó %s: %s" % (n["id"], e)))
                continue
            if hcore.is_reserved(rp):
                P.append(G("nodes_in_territory", "nó %s: %s é área reservada do harness" % (n["id"], rp)))
            elif not terr or not hcore.pattern_within(rp, terr):
                P.append(G("nodes_in_territory", "nó %s: %s fora do território de %s (%s)" % (
                    n["id"], rp, ag, ", ".join(terr) or "sem território")))
    return P


def g_nodes_fit_horizon(ctx, kind, ent, a):
    mx = int(ctx.cfg.get("max_files_per_task") or 5)
    return [G("nodes_fit_horizon", "nó %s tem %d paths (> max_files_per_task=%d): quebre em nós menores" % (
        n["id"], len(n.get("paths") or []), mx)) for n in _plan(a) if len(n.get("paths") or []) > mx]


def g_plan_within_budget(ctx, kind, ent, a):
    novos = [n for n in _plan(a) if not n.get("task")]
    lim = (ent.get("orcamento") or {}).get("despachos")
    if not lim:
        return []
    usado = int(a.get("_desp_usado") or 0)
    rest = int(lim) - usado
    if len(novos) > rest:
        return [G("plan_within_budget", "%d nó(s) novo(s) > %d despacho(s) restante(s) do orçamento (%d/%d usados): "
                  "peça ao humano mais orçamento (cs-auto amend) ou reduza o plano" % (len(novos), rest, usado, lim))]
    return []


def g_waves_computed(ctx, kind, ent, a):
    ondas = a.get("_ondas") or []
    got = set(x for w in ondas for x in w)
    miss = [n["id"] for n in _plan(a) if n["id"] not in got]
    return [G("waves_computed", "ondas não cobrem os nós %s" % ", ".join(miss))] if miss else []


def g_lessons_consulted(ctx, kind, ent, a):
    return [] if ent.get("licoes_consultadas") else [G("lessons_consulted", "busca de lições não registrada (o motor a "
                                                                            "faz ao entrar em PLANNING)")]


def evidence_refs(m):
    return [e.get("ref") for e in ((m.get("replano") or {}).get("evidencia") or []) if e.get("ref")]


def file_line_ok(root, ref):
    mm = re.match(r"^(.+):(\d+)$", ref or "")
    if not mm:
        return False
    p = os.path.join(root, mm.group(1))
    if not os.path.isfile(p):
        return False
    try:
        with open(p, "rb") as f:
            n = f.read().count(b"\n") + 1
    except OSError:
        return False
    return 1 <= int(mm.group(2)) <= n


def g_replan_cites(ctx, kind, ent, a):
    P = []
    if not (a.get("motivo") or "").strip():
        P.append(G("replan_cites_evidence", "--motivo obrigatório (por que o plano muda)"))
    ev = (a.get("evidencia") or "").strip()
    refs = evidence_refs(ent)
    if not ev:
        P.append(G("replan_cites_evidence", "--evidencia obrigatória: cite um evidencia[].ref do REPLAN (%s)" % (
            ", ".join(refs[:3]) or "arquivo:linha")))
    elif ev not in refs and not file_line_ok(ctx.root, ev):
        P.append(G("replan_cites_evidence", "evidência %r não é do sinal externo (use evidencia[].ref do tick: %s)" % (
            ev, ", ".join(refs[:3]))))
    rp = ent.get("replano") or {}
    if rp.get("gatilho") == "regressao":
        broken = rp.get("testes") or []
        fix = [n for n in _plan(a) if not n.get("task") and n.get("tipo") == "FIX" and n.get("teste") in broken]
        if broken and not fix:
            P.append(G("replan_cites_evidence", "replano de regressão exige nó --tipo FIX --teste <test-id que quebrou> "
                       "(%s)" % ", ".join(broken)))
    return P


NODE_FIELDS = ("tipo", "agent", "title", "paths", "deps", "cobre", "verify", "teste")


def g_accepted_untouched(ctx, kind, ent, a):
    P = []
    draft = dict((n["id"], n) for n in _plan(a))
    for n in a.get("_aceitos") or []:
        d = draft.get(n["id"])
        if d is None:
            P.append(G("accepted_nodes_untouched", "nó %s está ACCEPTED e sumiu do plano (nós aceitos são imutáveis)" %
                       n["id"]))
            continue
        diff = [k for k in NODE_FIELDS if (d.get(k) or None) != (n.get(k) or None)]
        if diff:
            P.append(G("accepted_nodes_untouched", "nó %s está ACCEPTED: %s não podem mudar no replano" % (
                n["id"], ", ".join(diff))))
    return P


def g_plan_diff_recorded(ctx, kind, ent, a):
    return []


def g_regression_green(ctx, kind, ent, a):
    reg = (a.get("_med") or {}).get("regressao")
    if reg_ok(ent, reg):
        return []
    return [G("regression_green", "regressão vermelha vs baseline: %s (exit %s; quebrou: %s)" % (
        reg.get("cmd"), reg.get("exit"), ", ".join(reg.get("falhas") or []) or "?"))]


def g_pending_nodes(ctx, kind, ent, a):
    if a.get("_pendentes"):
        return []
    return [G("pending_nodes", "DAG esgotado: nenhum nó executável pendente na feature %s" % ent.get("feature_ativa"))]


def g_replan_trigger(ctx, kind, ent, a):
    return [] if a.get("_gatilho") else [G("replan_trigger", "sem gatilho de replano")]


def g_replans_left(ctx, kind, ent, a):
    lim = int((ent.get("orcamento") or {}).get("replanos") or 0)
    used = int(ent.get("replanos") or 0)
    return [] if used < lim else [G("replans_left", "replanos esgotados (%d/%d)" % (used, lim))]


def g_acceptance_all_green(ctx, kind, ent, a):
    med = a.get("_med") or medir(ctx.root, ent, ent.get("feature_ativa"), regressao=False)
    red = [x for x in med["aceite"] if not x["verde"]]
    if not med["aceite"]:
        return [G("acceptance_all_green", "feature sem critérios medidos")]
    return [G("acceptance_all_green", "aceite incompleto: %s vermelho (exit %s)" % (x["id"], x["exit"])) for x in red]


def review_of(m, fea=None):
    fea = fea or m.get("feature_ativa")
    for r in reversed(m.get("revisoes_finais") or []):
        if r.get("feature") == fea and r.get("versao") == (m.get("plano") or {}).get("versao"):
            return r
    return None


def g_final_review_pass(ctx, kind, ent, a):
    r = a.get("revisao") or review_of(ent)
    if not r:
        return [G("final_review_pass", "revisão final pendente (FINAL_REVIEW por um gate ≠ autores)")]
    P = []
    by = r.get("by")
    if by not in hcore.gate_agents(ctx.team):
        P.append(G("final_review_pass", "%s não é gate: a revisão final é de um gate ≠ autores dos nós" % by))
    elif by in authors(ent, ctx, view(ctx)):
        P.append(G("final_review_pass", "%s é autor de nó da frente: revisão final pelo autor não vale" % by))
    if r.get("verdict") != "PASS":
        P.append(G("final_review_pass", "revisão final %s (%s)" % (r.get("verdict"), (r.get("findings") or "")[:200])))
    if not (r.get("findings") or "").strip():
        P.append(G("final_review_pass", "revisão final sem achados (--findings)"))
    return P


def feature_queue(m):
    fa = m.get("feature_ativa")
    fs = m.get("features") or []
    if fa not in fs:
        return []
    return fs[fs.index(fa) + 1:]


def g_next_feature_queued(ctx, kind, ent, a):
    return [] if feature_queue(ent) else [G("next_feature_queued", "nenhuma feature na fila do mandato")]


def g_escalation_condition(ctx, kind, ent, a):
    c = a.get("condicao")
    allowed = mcfg("escalation_conditions") or []
    if c not in allowed:
        return [G("escalation_condition", "condição %r não é de escalada (%s); citar invariante não escala" % (
            c, ", ".join(allowed)))]
    return []


def g_package_recorded(ctx, kind, ent, a):
    pk = a.get("_pacote")
    return [] if pk and pk.get("id") and pk.get("opcoes") else [G("package_recorded", "pacote de escalada não montado")]


def _esc_for(ent, a):
    if a.get("_esc") is not None:
        return a["_esc"]
    eid = a.get("escalada")
    es = open_escalations(ent)
    if eid:
        es = [e for e in es if e.get("id") == eid]
    return es[-1] if es else None


def g_choice_in_package(ctx, kind, ent, a):
    esc = _esc_for(ent, a)
    if not esc:
        return [G("choice_in_package", "nenhuma escalada aberta para resolver")]
    ch = a.get("choice")
    if ch not in (esc.get("opcoes") or []):
        return [G("choice_in_package", "opção %r fora do pacote %s (opções: %s)" % (ch, esc.get("id"),
                                                                                    ", ".join(esc.get("opcoes") or [])))]
    return []


def g_decision_present(ctx, kind, ent, a):
    return [] if (a.get("decision") or "").strip() else [G("decision_present", "--decision '<decisão do humano>' "
                                                                               "obrigatório (entra no brief e no evento)")]


def g_new_agent(ctx, kind, ent, a):
    esc = _esc_for(ent, a)
    na = a.get("agent")
    if not esc or not esc.get("no"):
        return [G("new_agent_valid", "escalada sem nó: trocar de agente não se aplica")]
    n = dict((x["id"], x) for x in plano_nos(ent)).get(esc["no"]) or {}
    if not na or not hcore.team_agent(ctx.team, na):
        return [G("new_agent_valid", "--agent deve existir em team.json5 (veio %r)" % na)]
    if na in hcore.gate_agents(ctx.team):
        return [G("new_agent_valid", "%s é gate: não recebe task de escrita" % na)]
    tv = view(ctx)
    it = tv.get(n.get("task") or "")
    t = tv.m2(it) if (it and it.get("m2")) else None
    cur = (engine.latest_deleg(t) or {}).get("agent") if t else n.get("agent")
    if na == cur:
        return [G("new_agent_valid", "%s já é o agente do nó %s (use retomar)" % (na, n.get("id")))]
    terr = ctx.territory(na)
    bad = [p for p in n.get("paths") or [] if not terr or not hcore.pattern_within(p, terr)]
    if bad:
        return [G("new_agent_valid", "paths do nó %s fora do território de %s: %s" % (n.get("id"), na, ", ".join(bad)))]
    return []


def g_no_flight(ctx, kind, ent, a):
    tv = view(ctx)
    info, _ = classify(ctx, tv, ent, None)
    fl = nodes_in_pipeline(info)
    return [G("no_delegation_in_flight", "nós em voo/verificação: %s" % ", ".join(fl))] if fl else []


def g_in_flight_marked(ctx, kind, ent, a):
    return []


def g_stamp_matches(ctx, kind, ent, a):
    return []


def g_wrap_trigger(ctx, kind, ent, a):
    g = a.get("gatilho")
    if g not in (mcfg("wrap_triggers") or []):
        return [G("wrap_trigger", "gatilho %r inválido" % g)]
    if g in ("stop_humano", "encerrar"):
        return [p.replace("guarda by_human:", "guarda wrap_trigger:") for p in g_by_human(ctx, kind, ent, a)]
    return []


def g_report_generated(ctx, kind, ent, a):
    return [] if a.get("_relatorio") else [G("report_generated", "relatório não gerado")]


def g_open_items_returned(ctx, kind, ent, a):
    return []


M5_GUARD_IMPL = {
    "target_exists": g_target_exists, "class_allowed": g_class_allowed, "spec_present": g_spec_present,
    "acceptance_executable": g_acceptance_executable, "acceptance_red": g_acceptance_red,
    "no_open_mandate": g_no_open_mandate, "not_trivial": g_not_trivial, "by_human": g_by_human,
    "dag_acyclic": g_dag_acyclic, "dag_covers_acceptance": g_dag_covers, "nodes_in_territory": g_nodes_in_territory,
    "nodes_fit_horizon": g_nodes_fit_horizon, "plan_within_budget": g_plan_within_budget,
    "waves_computed": g_waves_computed, "lessons_consulted": g_lessons_consulted, "regression_green": g_regression_green,
    "pending_nodes": g_pending_nodes, "replan_trigger": g_replan_trigger, "replans_left": g_replans_left,
    "acceptance_all_green": g_acceptance_all_green, "final_review_pass": g_final_review_pass,
    "next_feature_queued": g_next_feature_queued, "replan_cites_evidence": g_replan_cites,
    "accepted_nodes_untouched": g_accepted_untouched, "plan_diff_recorded": g_plan_diff_recorded,
    "escalation_condition": g_escalation_condition, "package_recorded": g_package_recorded,
    "choice_in_package": g_choice_in_package, "decision_present": g_decision_present,
    "in_flight_marked": g_in_flight_marked, "stamp_matches": g_stamp_matches, "wrap_trigger": g_wrap_trigger,
    "report_generated": g_report_generated, "open_items_returned": g_open_items_returned,
}


# ================================================================ transição (sempre engine.transition) e commit
def _guard_of(p):
    mm = re.match(r"^guarda ([a-z_]+)\s*:", p or "")
    return mm.group(1) if mm else None


def refusals(tname, err):
    out = []
    for p in err.problems:
        g = _guard_of(p)
        if g:
            out.append({"transicao": tname, "guarda": g, "problema": p[:300]})
    return out


def tr(ctx, mid, tname, a=None, extra=None, data=None, recusadas=None):
    """engine.transition da M5 + campos de evento (de, para, guardas[, guardas_recusadas])."""
    a = a if a is not None else {}
    m = ctx.find(KIND, mid)
    de = (m or {}).get("state")
    if tname in ADVANCE_TR and m is not None and de not in ("PROPOSED",) + TERMINAL:
        P = selo_problems(ctx.root, m)   # ponto central: nenhum avanço autônomo sem o selo do approve conferido
        if P:
            raise Refused(P, hint=SELO_HINT)
    box = {}

    def ext(to, probs):
        ops = [S(mid, "relogio", clock(m))]
        if to in ("PAUSED", "AWAITING_HUMAN"):
            ops.append(S(mid, "anterior", de))
        box["to"] = to
        if extra:
            ops += extra(to) or []
        return ops
    ev = engine.transition(ctx, KIND, mid, tname, a, ext)
    t = M()["transitions"][tname]
    ev.data.update({"de": de, "para": box.get("to"), "guardas": list(t.get("guards") or [])})
    if recusadas:
        ev.data["guardas_recusadas"] = list(recusadas)
    if data:
        ev.data.update(data)
    return ev


def commit(root, actor, build):
    return engine.commit(root, actor, build)


def commit_tree(root, actor, build):
    import tree
    return tree.run_build(root, actor, build)


def attempt(root, actor, mid, tname, a=None, extra=None, data=None, recusadas=None, with_tree=None):
    """Tenta a transição num commit próprio. Recusada → Refused (nada gravado)."""
    if with_tree:
        def b(tv):
            evs = [tr(tv.ctx, mid, tname, a, (lambda to: extra(to, tv)) if extra else None, data, recusadas)]
            if tv.ops or tv.board_ops:
                evs.append(tv.event("mandato", mid, {"mandato": mid, "transicao": tname}))
            return evs
        return commit_tree(root, actor, b)
    return commit(root, actor, lambda ctx: [tr(ctx, mid, tname, a, extra, data, recusadas)])


# ================================================================ árvore: tasks dos nós
def node_spec(m, n):
    crit = dict((c["id"], c.get("texto") or "") for c in m.get("criterios") or [] if c.get("feature") == n.get("feature"))
    tipo = (n.get("tipo") or "US").upper()
    spec = {"tipo": tipo, "agent": n["agent"], "allowed_paths": list(n["paths"]),
            "verify_cmd": n.get("verify") or m.get("regressao") or "",
            "como": "mandato %s (%s)" % (m["id"], m.get("objetivo") or ""), "quero": n.get("title") or n["id"],
            "para": m.get("objetivo") or "entregar o aceite do mandato",
            "criterio": ["%s|%s|" % (ac, (crit.get(ac) or "critério %s do mandato %s" % (ac, m["id"])).replace("|", "/"))
                         for ac in n.get("cobre") or []]}
    if n.get("teste"):
        spec["teste"] = n["teste"]
    if tipo == "FIX":
        spec["fixes"] = "%s:regressao" % m["id"]
    if tipo == "BUG":
        spec["reproducao"] = n.get("teste")
    return spec


def create_node_tasks(tv, m, nodes):
    import tree
    out = []
    for n in nodes:
        if n.get("task"):
            out.append(n)
            continue
        it = tree.add_task_item(tv, node_spec(m, n), n.get("title") or n["id"], "feature", n["feature"],
                                extra={"mandato": m["id"], "no": n["id"]})
        nn = dict(n)
        nn["task"] = it["id"]
        out.append(nn)
    return out


def tree_note(root, actor, task_id, acao, **kw):
    def b(tv):
        it = tv.get(task_id)
        if it is None:
            return []
        it = tv.items[it["id"]]
        tv.note(it, acao, **kw)
        tv.put(it)
        return [tv.event(acao, it["id"], {"mandato": kw.get("mandato")})]
    commit_tree(root, actor, b)


def tree_start(root, actor, task_id):
    import tree
    commit_tree(root, actor, lambda tv: tree.start(tv, task_id))


def tree_close(root, actor, task_id, summary):
    import tree
    try:
        commit_tree(root, actor, lambda tv: tree.close(tv, task_id, summary))
        return True
    except Refused:
        return False


# ================================================================ mecânica (só o motor)
def frozen_escalation_packages(ctx, m, nodes, existing):
    """Escaladas locais (dura_local) de nós que escrevem em frozen_paths ou casam --portao (risco)."""
    frozen = ctx.cfg.get("frozen_paths") or []
    gates = m.get("portoes") or []
    have = set()
    for e in m.get("escaladas") or []:
        if e.get("tipo") == "dura_local":
            have.add(e.get("no"))
    out = []
    n0 = len(m.get("escaladas") or []) + len(existing)
    lib = set(m.get("liberados") or [])
    covered = set()
    for n in sorted(nodes, key=lambda x: x["id"]):
        if n["id"] in have or n["id"] in lib or n["id"] in covered:
            continue
        cond = None
        if frozen and hcore.scopes_overlap(n.get("paths") or [], frozen):
            cond, why = "frozen_write", "nó %s escreve em área congelada (%s)" % (n["id"], ", ".join(frozen))
        elif gates and hcore.scopes_overlap(n.get("paths") or [], gates):
            cond, why = "risk_gate", "nó %s casa o portão de risco (%s)" % (n["id"], ", ".join(gates))
        if not cond:
            continue
        nos = [n["id"]] + descendants(nodes, n["id"])
        covered |= set(nos)
        n0 += 1
        out.append(new_package(m, "ESC-%d" % n0, "dura_local", cond, nos, list(OPCOES), why, no=n["id"]))
    return out


def new_package(m, eid, tipo, cond, nos, opcoes, why, no=None, evidencia=None):
    ts = hcore.now_iso().replace(":", "").replace("-", "").replace(".", "")[:15]
    return {"id": eid, "tipo": tipo, "condicao": cond, "no": no, "nos": list(nos), "opcoes": list(opcoes),
            "por_que": why, "evidencia": evidencia or [], "aberta": True, "criada_em": hcore.now_iso(),
            "de": m.get("state"), "arquivo": "escalada-%s-%s.json5" % (ts, eid)}


def reconcile_escalations(root, actor):
    """Escaladas locais: nó congelado = delegação M2 ESCALATED (start + escalate); resolvida → retry/reroute/drop."""
    import cmds
    for _ in range(40):
        ctx = ctx_of(root, actor)
        m = open_mandate(ctx.board)
        if not m:
            return
        tv = view(ctx)
        did = False
        nodes = dict((n["id"], n) for n in plano_nos(m))
        for e in m.get("escaladas") or []:
            if e.get("tipo") != "dura_local":
                continue
            for nid in e.get("nos") or []:
                n = nodes.get(nid)
                if not n or not n.get("task"):
                    continue
                it = tv.get(n["task"])
                if it is None:
                    continue
                t = tv.m2(it) if it.get("m2") else None
                d = engine.latest_deleg(t) if t else None
                if e.get("aberta"):
                    if t is None:
                        import tree
                        if tree.zone_of(it["path"]) != "state":
                            continue
                        tree_start(root, actor, it["id"])
                        did = True
                        break
                    if d and d["state"] in ("PLANNED", "BRIEFED", "REJECTED"):
                        cmds.escalate(root, actor, t["id"], "mandato %s: %s (%s) — aguarda a decisão humana (%s)" % (
                            m["id"], e.get("condicao"), e.get("por_que"), e.get("id")))
                        did = True
                        break
                    continue
                if not d or d["state"] != "ESCALATED":
                    continue
                ch, dec = e.get("escolha"), e.get("decisao")
                if ch == "retomar" or (ch == "trocar-agente" and nid != e.get("no")):
                    cmds.retry(root, actor, t["id"], None, dec)
                elif ch == "trocar-agente":
                    cmds.reroute(root, actor, t["id"], e.get("agente"), "mandato %s: trocar-agente (%s)" % (
                        m["id"], e.get("id")), None, dec)
                elif ch == "descartar-ramo":
                    cmds.drop(root, actor, t["id"], "decisão do humano (%s): %s" % (e.get("id"), dec))
                else:
                    continue
                did = True
                break
            if did:
                break
        if not did:
            return


def mechanics(root, actor, mode):
    """mode: run (tudo) | wrap (fecha o que está em voo, sem retry/despacho) | hold (só verifica: escalada global)."""
    import cmds
    import tree
    reconcile_escalations(root, actor)
    for _ in range(60):
        ctx = ctx_of(root, actor)
        m = open_mandate(ctx.board)
        if not m:
            return
        tv = view(ctx)
        info, order = classify(ctx, tv, m, None)
        did = False
        for nid in order:
            x = info[nid]
            t, d, it = x["t"], x["d"], x["it"]
            if x["cls"] == "retornado":
                cmds.verify(root, actor, t["id"])
                did = True
                break
            if mode == "hold":
                continue
            if x["cls"] == "revisado":
                out = engine.review_outcome(t)
                if out == "PASS":
                    try:
                        cmds.accept(root, actor, t["id"])
                    except Refused as e:
                        cmds.reject(root, actor, t["id"], "aceite recusado pelo motor: %s" % "; ".join(e.problems)[:600])
                    did = True
                    break
                if out == "FAIL":
                    rv = [r for r in t.get("reviews") or [] if r.get("attempt") == t.get("attempts") and r.get("verdict") == "FAIL"]
                    cmds.reject(root, actor, t["id"], "review FAIL de %s: %s" % (
                        (rv[-1] if rv else {}).get("by"), ((rv[-1] if rv else {}).get("findings") or "")[:600]))
                    did = True
                    break
            if x["cls"] in ("aceito", "descartado") and it is not None and tree.zone_of(it["path"]) == "state" \
                    and not it.get("closed") and t is not None:
                if tree_close(root, actor, it["id"], "entregue pelo mandato %s (nó %s, %s)" % (m["id"], nid, x["status"])):
                    did = True
                    break
            if mode != "run":
                continue
            if x["cls"] == "planejado":
                cmds.ready(root, actor, t["id"])
                did = True
                break
            if x["cls"] == "trocar":
                alt = alt_agent(ctx, x["n"], t)
                cmds.reroute(root, actor, t["id"], alt, "mandato %s: mesma falha 2× com %s — troca para %s" % (
                    m["id"], d["agent"], alt))
                did = True
                break
        if not did:
            return


# ================================================================ proteção do aceite (escalada dura global)
def protected_write(root, board, rel):
    """Guard (pre-write e escrita via Bash): aceite/spec assinados pelo humano não mudam durante o mandato."""
    m = open_mandate(board) if board is not None else None
    if not m or not m.get("protegidos"):
        return None
    if rel in m["protegidos"]:
        return ("mandato %s: %s é %s (tentativa registrada → escalada dura global acceptance_changed; peça ao humano "
                "uma emenda: cs-auto amend)" % (m["id"], rel, PROTECT_MARK))
    return None


def tamper_attempts(root, mid):
    p = hcore.state_paths(root)["ledger"]
    if not os.path.isfile(p):
        return 0
    recs, _, _ = hcore.read_chain(p)
    mark = "mandato %s:" % mid
    return len([r for r in recs if r.get("kind") == "block" and mark in str(r.get("reason") or "")
                and PROTECT_MARK in str(r.get("reason") or "")])


def detect_global(root, m):
    """(alterado, tentativas, arquivos) quando aceite/spec/verificador foi alterado (hash) ou houve tentativa."""
    if not m.get("protegidos"):
        return None
    changed = []
    for rel, sha in sorted(m["protegidos"].items()):
        p = os.path.join(root, rel)
        cur = hcore.sha256_file(p) if os.path.isfile(p) else None
        if cur != sha:
            changed.append(rel)
    n = tamper_attempts(root, m["id"])
    att = n > int(m.get("tentativas_vistas") or 0)
    if not changed and not att:
        return None
    if [e for e in open_escalations(m, "dura_global") if e.get("condicao") == "acceptance_changed"]:
        return None
    return {"alterado": bool(changed), "arquivos": changed, "tentativas": n}


def escalate_global(root, actor, m, g):
    opc = list(OPCOES_ALTERADO if g["alterado"] else OPCOES_SEM_NO)
    why = ("aceite/spec alterado (hash ≠ assinatura): %s" % ", ".join(g["arquivos"])) if g["alterado"] else \
        "tentativa de alterar aceite/spec bloqueada pelo guard (%d registro(s) no ledger)" % g["tentativas"]
    pk = new_package(m, "ESC-%d" % (len(m.get("escaladas") or []) + 1), "dura_global", "acceptance_changed", [], opc, why,
                     evidencia=[{"tipo": "E1", "ref": "ledger:%s" % x} for x in g["arquivos"]] or
                     [{"tipo": "evento", "ref": "harness-ledger:%d" % g["tentativas"]}])
    mid = m["id"]

    def ex(to):
        return [S(mid, "escaladas", list(m.get("escaladas") or []) + [pk]), S(mid, "tentativas_vistas", g["tentativas"])]
    attempt(root, actor, mid, "escalate", {"condicao": "acceptance_changed", "_pacote": pk}, ex,
            data={"pacote": pk["id"], "tipo": pk["tipo"]})


# ================================================================ relatório
def build_report(root, ctx, tv, m, resultado, med=None, devolvidos=None, extra=None):
    info, order = classify(ctx, tv, m, None)
    V = []
    b = m.get("baseline") or {}
    if b.get("regressao"):
        V.append({"nome": "baseline: regressão", "executada": True, "output_sha256": b["regressao"].get("output_sha256")})
    elif m.get("regressao"):
        V.append({"nome": "baseline: regressão", "executada": False, "motivo": "mandato não aprovado"})
    else:
        V.append({"nome": "regressão", "executada": False, "motivo": "mandato sem --regressao"})
    for x in b.get("aceite") or []:
        V.append({"nome": "baseline: aceite %s" % x["id"], "executada": True, "output_sha256": x.get("output_sha256")})
    for nid in order:
        x = info[nid]
        bld = ((x["t"] or {}).get("gate_report") or {}).get("build") or {}
        nome = "verify do nó %s (%s)" % (nid, x["n"].get("task"))
        if bld.get("output_sha256"):
            V.append({"nome": nome, "executada": True, "output_sha256": bld["output_sha256"], "exit": bld.get("exit_code")})
        else:
            V.append({"nome": nome, "executada": False, "motivo": "nó %s não chegou ao verify (%s)" % (nid, x["cls"])})
    feats = {}
    for f, lst in (m.get("medicoes_features") or {}).items():
        feats[f] = lst
    if med is not None:
        feats[med.get("feature") or m.get("feature_ativa")] = med.get("aceite") or []
        if med.get("regressao"):
            V.append({"nome": "regressão final", "executada": True, "output_sha256": med["regressao"]["output_sha256"],
                      "exit": med["regressao"]["exit"]})
    crits = []
    for c in m.get("criterios") or []:
        got = [x for x in feats.get(c.get("feature")) or [] if x["id"] == c["id"]]
        if got:
            crits.append({"id": c["id"], "feature": c.get("feature"), "verde": got[-1]["verde"],
                          "output_sha256": got[-1]["output_sha256"]})
            V.append({"nome": "aceite final %s (%s)" % (c["id"], c.get("feature")), "executada": True,
                      "output_sha256": got[-1]["output_sha256"]})
        else:
            crits.append({"id": c["id"], "feature": c.get("feature"), "verde": False, "output_sha256": None,
                          "motivo": "não medido (feature não alcançada)"})
            V.append({"nome": "aceite final %s (%s)" % (c["id"], c.get("feature")), "executada": False,
                      "motivo": "feature %s não alcançada pelo mandato" % c.get("feature")})
    rev = (extra or {}).get("revisao") or review_of(m)
    if rev:
        V.append({"nome": "revisão final", "executada": True, "by": rev.get("by"), "verdict": rev.get("verdict")})
    else:
        V.append({"nome": "revisão final", "executada": False,
                  "motivo": "mandato encerrado antes da revisão final (%s)" % resultado})
    orf = orphan_criteria(m, med, info)
    u = usage(ctx, tv, m)
    rep = {"mandato": m["id"], "resultado": resultado, "objetivo": m.get("objetivo"), "alvo": m.get("alvo"),
           "criterios": crits, "verificacoes": V, "devolvidos": devolvidos or [], "criterios_orfaos": orf,
           "revisao_final": ({"by": rev.get("by"), "verdict": rev.get("verdict"), "findings": rev.get("findings")}
                             if rev else None),
           "orcamento": orcamento_view(m, u), "at": hcore.now_iso()}
    if resultado == "ABORTED":
        head = (b.get("head") or "").strip()
        rep["restaurar"] = ("git reset --hard %s  # ponto seguro gravado no approve (descarta o trabalho do mandato)" %
                            head) if head else "git stash  # sem ponto seguro gravado (mandato não aprovado)"
    if extra:
        rep.update({k: v for k, v in extra.items() if k != "revisao"})
    return rep


def orphan_criteria(m, med, info):
    if med is None:
        return []
    red = [x["id"] for x in med.get("aceite") or [] if not x["verde"]]
    out = []
    for ac in red:
        cov = [x for x in info.values() if ac in (x["n"].get("cobre") or []) and x["n"].get("feature") == med.get("feature")]
        if cov and all(x["cls"] == "descartado" for x in cov):
            out.append(ac)
    return out


# ================================================================ comandos: proposta e portões humanos
def contract_for(root, ctx, a):
    import tree
    tv = view(ctx)
    cfg = ctx.cfg
    if bool(a.feature) == bool(a.sprint):
        raise Syntax("propose exige exatamente um alvo: --feature FEA-nnn | --sprint SPR-nnn")
    if a.feature:
        alvo = {"tipo": "feature", "id": a.feature}
        feats = [a.feature]
        crits = parse_criterios(root, cfg, a.criterio, a.feature)
    else:
        alvo = {"tipo": "sprint", "id": a.sprint}
        sp = tv.get(a.sprint)
        feats = []
        if sp is not None and sp.get("kind") == "sprint":
            fs = [it for it in tv.items.values() if it.get("kind") == "feature" and tree.zone_of(it["path"]) != "archive"
                  and (it.get("sprint") == sp["id"] or (tv.container_of(it) or {}).get("id") == sp["id"])]
            feats = [f["id"] for f in sorted(fs, key=lambda x: x["id"])]
        crits = []
        for fid in feats:
            f = tv.get(fid)
            crits.append({"id": "AC-1", "texto": "aceite da feature %s: %s" % (fid, (f.get("title") or "").replace("|", "/")),
                          "comando": f.get("aceite"), "cmd": f.get("aceite") or "", "feature": fid})
        crits += parse_criterios(root, cfg, a.criterio, feats[0] if feats else None)
    return {"alvo": alvo, "features": feats, "feature_ativa": feats[0] if feats else None, "spec": a.spec,
            "objetivo": a.objetivo, "classe": a.classe or "feature", "rigor": a.rigor or "standard",
            "portoes": list(a.portao or []), "regressao": a.regressao or cfg.get("regression_command"),
            "nos_estimados": a.nos, "criterios": crits}


def cmd_propose(root, actor, a):
    ctx0 = ctx_of(root, actor)
    contrato = contract_for(root, ctx0, a)
    names = M()["transitions"]["propose"]["guards"]
    holder = {}

    def build(ctx):
        aa = {"_contrato": contrato, "nos": a.nos, "classe": contrato["classe"], "portoes": contrato["portoes"]}
        ent = {"id": None, "state": None}
        P = []
        for g in names:
            P += engine.GUARDS[g](ctx, KIND, ent, aa)
        if P:
            raise Refused(P, hint="corrija e proponha de novo: cs-auto propose ...")
        mid = engine.next_id(ctx.board, KIND, "MAN", 3)
        now = hcore.now_iso()
        obj = {"id": mid, "state": "PROPOSED", "created_at": now, "updated_at": now, "proposto_por": ctx.actor,
               "orcamento": derive_budget(a.nos, contrato["rigor"]), "assinatura": None, "aprovacoes": [],
               "relogio": {"minutos": 0, "visto_em": now}, "escaladas": [], "plano": None, "planos": [], "onda": 0,
               "integracoes": [], "replanos": 0, "licoes": [], "licoes_consultadas": False, "revisoes_finais": [],
               "orfas": [], "gasto": {"usd_medido": 0, "usd_autodeclarado": 0}, "sem_progresso": 0,
               "tentativas_vistas": 0, "protegidos": {}, "baseline": None, "aprovado": None, "liberados": [],
               "relatorio": None, "medicoes_features": {}, "medicao": None, "progresso": None, "replano": None}
        obj.update(contrato)
        holder["mid"] = mid
        return [engine.Event("mandato.propose", mid, [["create", KIND, None, obj]],
                             {"de": None, "para": "PROPOSED", "guardas": list(names),
                              "args": engine.public_args(aa)})]
    commit(root, actor, build)
    ctx = ctx_of(root, actor)
    m = ctx.find(KIND, holder["mid"])
    o = m["orcamento"]
    return ["%s PROPOSED — %s %s · objetivo: %s" % (m["id"], m["alvo"]["tipo"], m["alvo"]["id"], m.get("objetivo")),
            "orçamento derivado pelo motor: despachos=%s tentativas=%s replanos=%s minutos=%s" % (
                o["despachos"], o["tentativas"], o["replanos"], o["minutos"]),
            "aguarda o HUMANO: cs-auto approve --by <humano> [--orcamento ...] (ou amend/abort)"]


def _need(board, states=None):
    m = open_mandate(board) or current(board)
    if not m:
        raise Refused("sem mandato: cs-auto propose ...")
    if states and m["state"] not in states:
        raise Refused("mandato %s em %s; comando válido só em %s" % (m["id"], m["state"], "|".join(states)))
    return m


def signature(m, orc, protegidos, anterior):
    keys = ("alvo", "features", "spec", "objetivo", "classe", "rigor", "portoes", "regressao", "criterios")
    body = dict((k, m.get(k)) for k in keys)
    body.update({"orcamento": orc, "protegidos": protegidos, "anterior": anterior})
    return hcore.sha256_bytes(hcore.canonical(body).encode("utf-8"))


def plano_sha256(m, orc, protegidos):
    """sha256 do contrato aprovado, recomputável do mandato atual: alvo, features, spec, objetivo, classe, rigor,
    portões, regressão, critérios, orçamento aprovado e arquivos protegidos (aceite/spec assinados)."""
    body = dict((k, m.get(k)) for k in PLANO_KEYS)
    body.update({"orcamento": orc, "protegidos": protegidos or {}})
    return hcore.sha256_bytes(hcore.canonical(body).encode("utf-8"))


_CHAIN_CACHE = {}


def _chain_records(root):
    p = hcore.state_paths(root)["events"]
    try:
        st = os.stat(p)
    except OSError:
        return []
    key = (p, st.st_size, st.st_mtime_ns)
    hit = _CHAIN_CACHE.get("k")
    if hit is not None and hit[0] == key:
        return hit[1]
    recs, _, _ = hcore.read_chain(p)
    _CHAIN_CACHE["k"] = (key, recs)
    return recs


def last_approve(root, mid):
    """(evento mandato.approve mais recente do mandato na cadeia, eventos posteriores do mandato) ou (None, [])."""
    recs = _chain_records(root)
    for i in range(len(recs) - 1, -1, -1):
        r = recs[i]
        if r.get("type") == "mandato.approve" and r.get("entity") == mid:
            return r, [x for x in recs[i + 1:] if x.get("entity") == mid]
    return None, []


SELO_HINT = ("o mandato não avança: o humano confere no terminal dele (cs-auto conferir) e decide — parar "
             "(cs-auto stop --by <humano> --reason ...) ou reaprovar depois de emendar")


def selo_problems(root, m):
    """O que o motor confere SEM a senha (não verifica a HMAC — só o `cs-auto conferir` do humano verifica): o último
    `mandato.approve` deste mandato na cadeia tem selo no formato, do mesmo mandato, com o orçamento atual (mais os
    acréscimos de replano decididos pelo humano em `resolve`) e o hash do plano atual."""
    mid = m.get("id")
    ev, depois = last_approve(root, mid)
    if ev is None:
        return ["selo da aprovação: mandato %s sem evento mandato.approve na cadeia" % mid]
    selo = (ev.get("data") or {}).get("selo")
    P = ["selo da aprovação (%s, seq %s): %s" % (mid, ev.get("seq"), p) for p in senha.problemas_formato_selo(selo, mid)]
    if P:
        return P
    orc = copy.deepcopy(selo["orcamento"])
    for r in depois:
        extra = (r.get("data") or {}).get("orcamento_extra") if r.get("type") == "mandato.resolve_resume" else None
        for k, v in (extra or {}).items():
            if isinstance(v, int) and not isinstance(orc.get(k), dict):
                orc[k] = int(orc.get(k) or 0) + v
    if orc != (m.get("orcamento") or {}):
        P.append("selo da aprovação (%s, seq %s): o orçamento atual %s difere do aprovado %s" % (
            mid, ev.get("seq"), hcore.canonical(m.get("orcamento")), hcore.canonical(orc)))
    if plano_sha256(m, selo["orcamento"], m.get("protegidos")) != selo["plano_sha256"]:
        P.append("selo da aprovação (%s, seq %s): o plano atual (objetivo/critérios/regressão/orçamento/arquivos "
                 "protegidos) difere do que o humano aprovou" % (mid, ev.get("seq")))
    return P


def _human_key(root, contexto):
    """Ato humano: registro válido fora do alvo + senha digitada no terminal. Recusa → Refused (exit 1)."""
    try:
        return senha.pedir_chave(root, contexto)
    except senha.RegistroInvalido as e:
        raise Refused(str(e), hint="1ª vez: o humano roda, no terminal dele, `cs-auto senha definir`")
    except senha.SemTTY as e:
        raise Refused(str(e))
    except ValueError as e:
        raise Refused(str(e))


def cmd_senha(root, a):
    if a.acao != "definir":
        raise Syntax("uso: cs-auto senha definir")
    try:
        path = senha.definir(root)
    except (senha.RegistroInvalido, senha.SemTTY, ValueError) as e:
        raise Refused(str(e))
    return ["senha definida: registro %s (modo 0600; só sais e verificador PBKDF2-SHA256, nunca a senha)" % path,
            "daqui em diante `cs-auto approve` pede esta senha no terminal; `cs-auto conferir` recalcula os selos"]


def cmd_conferir(root, actor):
    recs = _chain_records(root)
    aprov = [r for r in recs if r.get("type") == "mandato.approve"]
    reg, K = _human_key(root, "conferir os selos HMAC de %d aprovação(ões) de mandato na cadeia" % len(aprov))
    ok, bad = [], []
    for r in aprov:
        selo = (r.get("data") or {}).get("selo")
        mid = r.get("entity") or ((selo or {}).get("mandato") if isinstance(selo, dict) else None)
        P = senha.problemas_formato_selo(selo, mid)
        if not P and not hmac.compare_digest(senha.tag_selo(K, selo), selo["tag"]):
            P = ["tag HMAC não confere com a senha (selo forjado ou registro da senha trocado)"]
        if P:
            bad.append("%s seq %s: SELO INVÁLIDO — %s" % (mid, r.get("seq"), "; ".join(P)))
        else:
            ok.append("%s seq %s: selo OK (aprovação nº %s de %s)" % (mid, r.get("seq"), selo.get("seq"),
                                                                     (r.get("data") or {}).get("by")))
    m = open_mandate(ctx_of(root, actor).board)
    if m is not None and m["state"] not in ("PROPOSED",) + TERMINAL:
        bad += selo_problems(root, m)
    if bad:
        raise Refused(bad + ok, hint="selo inválido: não deixe o piloto seguir; pare o mandato (cs-auto stop) e "
                                     "investigue quem mexeu na cadeia/registro")
    if not aprov:
        return ["nenhuma aprovação de mandato na cadeia"]
    return ok + ["todos os %d selos conferem com a senha" % len(aprov)]


def cmd_approve(root, actor, a, extras):
    if extras:
        raise Syntax("approve não aceita argumentos extras: a senha só é digitada no terminal")
    ctx = ctx_of(root, actor)
    m = _need(ctx.board)
    # a senha vem antes da transição; a guarda by_human continua no engine (recusa registrada como as demais)
    _, K = _human_key(root, "aprovar o mandato %s (%s)" % (m["id"], m.get("objetivo") or ""))
    orc = dict(m.get("orcamento") or {})
    orc.update(parse_orcamento(a.orcamento))
    protegidos = {}
    files = [m.get("spec")] if m.get("spec") else []
    for c in m.get("criterios") or []:
        files += crit_files(root, c)
    for f in files:
        p = os.path.join(root, f)
        if f and os.path.isfile(p):
            protegidos[hcore.norm_rel(f)] = hcore.sha256_file(p)
    aa = {"by": a.by, "_prova": [], "orcamento": a.orcamento}
    mid = m["id"]

    def build(ctx):
        cur = ctx.find(KIND, mid)
        sig = signature(cur, orc, protegidos, cur.get("assinatura"))
        selo = senha.novo_selo(K, mid, plano_sha256(cur, orc, protegidos), copy.deepcopy(orc),
                               len(cur.get("aprovacoes") or []) + 1, hcore.now_iso())
        holder = {}

        def ex(to):
            med = aa.get("_med") or medir(root, cur, todos=True)
            base = {"aceite": [{"id": x["id"], "feature": x.get("feature"), "verde": x["verde"], "exit": x["exit"],
                                "output_sha256": x["output_sha256"]} for x in med["aceite"]],
                    "regressao": ({k: med["regressao"][k] for k in ("exit", "output_sha256", "falhas")}
                                  if med.get("regressao") else None), "head": engine.git_head(root)}
            ap = list(cur.get("aprovacoes") or []) + [{"by": a.by, "at": hcore.now_iso(), "assinatura": sig}]
            holder["sig"] = sig
            return [S(mid, "assinatura", sig), S(mid, "orcamento", orc), S(mid, "protegidos", protegidos),
                    S(mid, "baseline", base), S(mid, "aprovado", {"by": a.by, "at": hcore.now_iso()}),
                    S(mid, "aprovacoes", ap), S(mid, "consultas_base", [c["id"] for c in ctx.board.get("consults") or []]),
                    S(mid, "relogio", {"minutos": float((cur.get("relogio") or {}).get("minutos") or 0),
                                       "visto_em": hcore.now_iso()})]
        # acceptance_red mede tudo (todos os critérios de todas as features)
        aa["_med"] = medir(root, cur, todos=True)
        ev = tr(ctx, mid, "approve", aa, ex, data={"assinatura": sig, "by": a.by, "selo": selo})
        return [ev]
    commit(root, actor, build)
    return ["%s CHARTERED (aprovado por %s; selo HMAC gravado no evento de aprovação) — o piloto segue: cs-auto tick" % (
        mid, a.by)]


def cmd_amend(root, actor, a, extras, decision=None, esc=None):
    ctx = ctx_of(root, actor)
    m = _need(ctx.board)
    mid = m["id"]
    orc = dict(m.get("orcamento") or {})
    orc.update(parse_orcamento(getattr(a, "orcamento", None)))
    reason = a.reason if decision is None else decision
    aa = {"by": a.by, "reason": reason, "_prova": extras}
    if decision is not None:
        aa["decision"] = decision
        aa["choice"] = "emendar"

    def ex(to):
        ops = [S(mid, "orcamento", orc), S(mid, "emenda", {"by": a.by, "reason": reason, "at": hcore.now_iso(),
                                                          "assinatura_anterior": m.get("assinatura")})]
        if esc is not None:
            es = []
            for e in m.get("escaladas") or []:
                e = dict(e)
                if e.get("id") == esc.get("id") and e.get("tipo") != "dura_local":
                    e.update({"aberta": False, "escolha": "emendar", "decisao": decision, "by": a.by})
                es.append(e)
            ops.append(S(mid, "escaladas", es))
        return ops
    attempt(root, actor, mid, "amend", aa, ex, data={"assinatura_anterior": m.get("assinatura"), "motivo": reason,
                                                     "decision": decision})
    return ["%s PROPOSED (emenda de %s: %s) — aguarda nova aprovação humana: cs-auto approve --by <humano>" % (
        mid, a.by, reason)]


def cmd_abort(root, actor, a, extras, decision=None):
    ctx = ctx_of(root, actor)
    m = _need(ctx.board)
    mid = m["id"]
    reason = a.reason if decision is None else decision
    aa = {"by": a.by, "reason": reason, "_prova": extras}
    if decision is not None:
        aa["decision"] = decision

    def build(ctx):
        cur = ctx.find(KIND, mid)
        tv = view(ctx)
        med = None
        if cur.get("state") in ("AWAITING_HUMAN",) and cur.get("feature_ativa"):
            med = medir(root, cur, cur.get("feature_ativa"))
        rep = build_report(root, ctx, tv, cur, "ABORTED", med, extra={"motivo": reason, "by": a.by})

        def ex(to):
            es = [dict(e, aberta=False) if e.get("aberta") else e for e in cur.get("escaladas") or []]
            return [S(mid, "relatorio", rep), S(mid, "escaladas", es)]
        return [tr(ctx, mid, "abort", aa, ex, data={"motivo": reason, "decision": decision})]
    commit(root, actor, build)
    return ["%s ABORTED (%s) — relatório: cs-auto report" % (mid, reason)]


def cmd_stop(root, actor, a, extras):
    ctx = ctx_of(root, actor)
    m = _need(ctx.board)
    aa = {"by": a.by, "reason": a.reason, "gatilho": "stop_humano", "_prova": extras}
    if not (a.reason or "").strip():
        raise Refused(G("wrap_trigger", "--reason obrigatório (motivo da parada humana)"))
    wrap_up(root, actor, m, "stop_humano", aa, data={"motivo": a.reason, "by": a.by})
    return ["%s WRAPPING_UP (parada humana: %s) — o piloto fecha o que está em voo e devolve o resto: cs-auto tick" % (
        m["id"], a.reason)]


def wrap_up(root, actor, m, gatilho, a=None, recusadas=None, data=None):
    aa = dict(a or {})
    aa["gatilho"] = gatilho
    d = {"gatilho": gatilho}
    d.update(data or {})
    mid = m["id"]

    def ex(to):
        return [S(mid, "gatilho_encerramento", gatilho)]
    attempt(root, actor, mid, "wrap_up", aa, ex, data=d, recusadas=recusadas)


def cmd_resolve(root, actor, a, extras):
    ctx = ctx_of(root, actor)
    m = _need(ctx.board)
    mid = m["id"]
    ch = a.choice
    esc = _esc_for(m, {"escalada": a.escalada})
    tname = CHOICE_TR.get(ch, "resolve_resume")
    if tname in ("amend", "wrap_up", "abort"):
        P = []
        if m["state"] != "AWAITING_HUMAN":
            raise Refused("mandato %s em %s: resolve só em AWAITING_HUMAN" % (mid, m["state"]))
        P += g_by_human(ctx, KIND, m, {"by": a.by, "_prova": extras})
        P += g_choice_in_package(ctx, KIND, m, {"choice": ch, "_esc": esc})
        P += g_decision_present(ctx, KIND, m, {"decision": a.decision})
        if P:
            raise Refused(P)
        if tname == "amend":
            a.reason = a.decision
            a.orcamento = None
            return cmd_amend(root, actor, a, extras, decision=a.decision, esc=esc)
        if tname == "abort":
            a.reason = a.decision
            return cmd_abort(root, actor, a, extras, decision=a.decision)
        ex_esc = []
        for e in m.get("escaladas") or []:
            e = dict(e)
            if e.get("aberta"):
                e.update({"aberta": False, "escolha": "encerrar", "decisao": a.decision, "by": a.by})
            ex_esc.append(e)

        def ex(to):
            return [S(mid, "escaladas", ex_esc), S(mid, "gatilho_encerramento", "encerrar")]
        attempt(root, actor, mid, "wrap_up", {"by": a.by, "gatilho": "encerrar", "decision": a.decision,
                                              "choice": ch, "_prova": extras}, ex,
                data={"gatilho": "encerrar", "decision": a.decision, "escalada": (esc or {}).get("id")})
        return ["%s WRAPPING_UP (encerrar: %s) — cs-auto tick fecha e devolve os abertos ao backlog" % (mid, a.decision)]
    aa = {"by": a.by, "choice": ch, "decision": a.decision, "agent": a.agent, "_esc": esc, "_prova": extras}
    if esc:
        aa["escalada"] = esc.get("id")

    def ex(to):
        es = []
        for e in m.get("escaladas") or []:
            e = dict(e)
            if esc and e.get("id") == esc.get("id"):
                e.update({"aberta": False, "escolha": ch, "decisao": a.decision, "by": a.by, "agente": a.agent,
                          "resolvida_em": hcore.now_iso()})
            es.append(e)
        ops = [S(mid, "escaladas", es)]
        if esc and esc.get("tipo") == "dura_local" and ch in ("retomar", "trocar-agente"):
            ops.append(S(mid, "liberados", sorted(set(m.get("liberados") or []) | set(esc.get("nos") or []))))
        if esc and esc.get("condicao") == "replans_exhausted" and ch == "retomar":
            orc = dict(m.get("orcamento") or {})
            orc["replanos"] = int(orc.get("replanos") or 0) + 1
            ops.append(S(mid, "orcamento", orc))
        if esc and ch == "trocar-agente" and esc.get("no"):
            nos = []
            for n in plano_nos(m):
                n = dict(n)
                if n["id"] == esc["no"]:
                    n["agent"] = a.agent
                nos.append(n)
            pl = dict(m.get("plano") or {})
            pl["nos"] = nos
            ops.append(S(mid, "plano", pl))
        return ops
    dres = {"decision": a.decision, "escolha": ch, "escalada": (esc or {}).get("id")}
    if esc and esc.get("condicao") == "replans_exhausted" and ch == "retomar":
        dres["orcamento_extra"] = {"replanos": 1}   # o selo do approve + estes acréscimos = orçamento autorizado
    attempt(root, actor, mid, tname, aa, ex, data=dres)
    # a decisão humana entra no brief/registro das tasks do ramo (árvore) e o motor aplica a saída em M2
    if esc and esc.get("tipo") == "dura_local":
        nodes = dict((n["id"], n) for n in plano_nos(m))
        for nid in esc.get("nos") or []:
            n = nodes.get(nid)
            if n and n.get("task"):
                tree_note(root, actor, n["task"], "decisao_humana", decisao=a.decision, escolha=ch, by=a.by,
                          escalada=esc.get("id"), mandato=mid)
    reconcile_escalations(root, actor)
    m2 = ctx_of(root, actor).find(KIND, mid)
    return ["%s %s (%s: %s) — o piloto segue: cs-auto tick" % (mid, m2["state"], ch, a.decision)]


# ================================================================ plano (rascunho do modelo; guardas no submit)
def load_draft(root, m):
    p = draft_path(root, m["id"])
    if os.path.isfile(p):
        try:
            d = j5.load(p)
            if isinstance(d, dict) and d.get("feature") == m.get("feature_ativa"):
                return d
        except (OSError, ValueError):
            pass
    return {"mandato": m["id"], "feature": m.get("feature_ativa"), "versao_base": (m.get("plano") or {}).get("versao"),
            "nos": [dict(n) for n in feature_nos(m)]}


def save_draft(root, m, d):
    p = draft_path(root, m["id"])
    os.makedirs(os.path.dirname(p), exist_ok=True)
    hcore.write_json5(p, d, "rascunho do plano do mandato %s (cs-auto plan add-node/edit-node; guardas no submit)" % m["id"])


def _csv(v):
    out = []
    for x in (v if isinstance(v, list) else [v]):
        for y in str(x or "").split(","):
            if y.strip():
                out.append(y.strip())
    return out


def cmd_plan(root, actor, a):
    ctx = ctx_of(root, actor)
    m = _need(ctx.board)
    if a.pcmd != "submit" and m["state"] not in ("PLANNING", "REPLANNING"):
        raise Refused("mandato %s em %s: plano só se edita em PLANNING/REPLANNING (o tick diz quando)" % (m["id"], m["state"]))
    if a.pcmd == "reset":
        p = draft_path(root, m["id"])
        if os.path.isfile(p):
            os.remove(p)
        return ["rascunho do plano descartado (%s)" % m["id"]]
    if a.pcmd in ("add-node", "edit-node"):
        d = load_draft(root, m)
        nodes = d["nos"]
        if a.pcmd == "add-node":
            if not NODE_ID_RE.match(a.id or ""):
                raise Syntax("--id inválido: %r" % a.id)
            if not a.path or not a.cobre or not a.agent or not (a.title or "").strip():
                raise Syntax("add-node exige --id --tipo --agent --title --path... --cobre AC-n")
            n = {"id": a.id, "tipo": (a.tipo or "US").upper(), "agent": a.agent, "title": a.title,
                 "paths": [hcore.norm_rel(p) for p in a.path], "deps": _csv(a.deps or []), "cobre": _csv(a.cobre),
                 "verify": a.verify_cmd, "teste": a.teste, "feature": m.get("feature_ativa")}
            nodes = [x for x in nodes if x["id"] != a.id] + [n]
        else:
            got = [x for x in nodes if x["id"] == a.id]
            if not got:
                raise Syntax("edit-node: nó %s não está no rascunho" % a.id)
            n = got[0]
            if a.tipo:
                n["tipo"] = a.tipo.upper()
            for k, v in (("agent", a.agent), ("title", a.title), ("verify", a.verify_cmd), ("teste", a.teste)):
                if v is not None:
                    n[k] = v
            if a.path:
                n["paths"] = [hcore.norm_rel(p) for p in a.path]
            if a.deps is not None:
                n["deps"] = _csv(a.deps)
            if a.cobre is not None:
                n["cobre"] = _csv(a.cobre)
        for x in nodes:
            if x.get("tipo") not in ("US", "BUG", "FIX"):
                raise Syntax("--tipo deve ser US|BUG|FIX (nó %s)" % x["id"])
        d["nos"] = nodes
        save_draft(root, m, d)
        return ["rascunho %s: %d nó(s) (%s) — valide com cs-auto plan submit" % (
            m["id"], len(nodes), ", ".join(x["id"] for x in nodes))]
    if a.pcmd == "submit":
        return plan_submit(root, actor, m, a)
    raise Syntax("plan add-node|edit-node|reset|submit")


def plan_submit(root, actor, m, a):
    if m["state"] not in ("PLANNING", "REPLANNING"):
        raise Refused("mandato %s em %s: submit só em PLANNING/REPLANNING" % (m["id"], m["state"]))
    replan = m["state"] == "REPLANNING" or bool(feature_nos(m))
    tname = "replan_accept" if m["state"] == "REPLANNING" else "plan_accept"
    d = load_draft(root, m)
    mid = m["id"]
    fa = m.get("feature_ativa")

    def build(tv):
        ctx = tv.ctx
        cur = ctx.find(KIND, mid)
        info, _ = classify(ctx, tv, cur, fa)
        draft = [dict(n) for n in d["nos"]]
        for n in draft:
            n["feature"] = fa
            old = [x for x in feature_nos(cur) if x["id"] == n["id"]]
            if old and old[0].get("task"):
                n["task"] = old[0]["task"]
            elif not old:
                n.pop("task", None)
        outros = [n for n in plano_nos(cur) if n.get("feature") != fa]
        aceitos = [x["n"] for x in info.values() if x["cls"] == "aceito"]
        last = cur.get("medicao") or {}
        if last.get("feature") == fa:
            vermelhos = [x["id"] for x in last.get("aceite") or [] if not x["verde"]]
        else:
            vermelhos = [c["id"] for c in criterios_de(cur)]
        eleg = [n["id"] for n in draft if not n.get("task") or (info.get(n["id"], {}).get("cls") in RUNNABLE + PIPE +
                                                                ("esperando",))]
        ondas = compute_waves(ctx, draft)
        u = usage(ctx, tv, cur)
        aa = {"_plano": draft, "_outros": outros, "_criterios": criterios_de(cur), "_aceitos": aceitos,
              "_replano": replan, "_vermelhos": vermelhos, "_elegiveis": eleg, "_ondas": ondas,
              "_desp_usado": u["despachos"], "motivo": getattr(a, "motivo", None), "evidencia": getattr(a, "evidencia", None)}
        if tname == "plan_accept" and not replan:
            aa.pop("motivo", None)
            aa.pop("evidencia", None)

        def ex(to):
            nodes = create_node_tasks(tv, cur, draft)
            full = outros + nodes
            versao = int((cur.get("plano") or {}).get("versao") or 0) + 1
            prev = (cur.get("planos") or [])[-1] if cur.get("planos") else None
            old_ids = set(n["id"] for n in feature_nos(cur))
            diff = {"novos": [n["id"] for n in nodes if n["id"] not in old_ids],
                    "removidos": sorted(old_ids - set(n["id"] for n in nodes))}
            rec = {"versao": versao, "feature": fa, "nos": nodes, "ondas": ondas, "motivo": aa.get("motivo"),
                   "evidencia": aa.get("evidencia"), "diff": diff, "at": hcore.now_iso(),
                   "anterior_sha": hcore.sha256_bytes(hcore.canonical(prev).encode("utf-8")) if prev else None}
            esc = frozen_escalation_packages(ctx, cur, nodes, [])
            # onda corrente = 1ª onda com nó EXECUTÁVEL (novo com deps aceitas, ou nó existente executável; nunca
            # congelado) — onda só com nós aceitos/travados não vira corrente
            frozen = set(congelados(cur)) | set(x for e in esc for x in e["nos"])
            done = set(n["id"] for n in aceitos)
            run_ids = set(nid for nid, x in info.items() if x["runnable"])
            for n in nodes:
                if n["id"] not in info and all(d in done for d in n.get("deps") or []):
                    run_ids.add(n["id"])
            run_ids -= frozen
            onda = 0
            for i, w in enumerate(ondas):
                if [x for x in w if x in run_ids]:
                    onda = i
                    break
            ops = [S(mid, "plano", {"versao": versao, "nos": full, "ondas": ondas, "feature": fa}),
                   S(mid, "planos", list(cur.get("planos") or []) + [rec]), S(mid, "onda", onda),
                   S(mid, "escaladas", list(cur.get("escaladas") or []) + esc)]
            if tname == "replan_accept":
                ops += [S(mid, "replanos", int(cur.get("replanos") or 0) + 1), S(mid, "replano", None)]
            if not cur.get("progresso") or (cur.get("progresso") or {}).get("feature") != fa:
                base = [x for x in ((cur.get("baseline") or {}).get("aceite") or []) if x.get("feature") == fa]
                ops.append(S(mid, "progresso", {"feature": fa, "verdes": len([x for x in base if x.get("verde")]),
                                                "aceitos": 0}))
            return ops
        ev = tr(ctx, mid, tname, aa, ex, data={"versao": int((cur.get("plano") or {}).get("versao") or 0) + 1,
                                               "motivo": aa.get("motivo"), "evidencia": aa.get("evidencia")})
        evs = [ev]
        if tv.ops or tv.board_ops:
            evs.append(tv.event("mandato", mid, {"mandato": mid, "plano": "tasks dos nós"}))
        return evs
    commit_tree(root, actor, build)
    p = draft_path(root, mid)
    if os.path.isfile(p):
        os.remove(p)
    reconcile_escalations(root, actor)
    m2 = ctx_of(root, actor).find(KIND, mid)
    return ["%s %s — plano v%s aceito (%d nó(s), ondas %s); o piloto segue: cs-auto tick" % (
        mid, m2["state"], m2["plano"]["versao"], len(feature_nos(m2)), json.dumps(m2["plano"]["ondas"]))]


# ================================================================ tick (o piloto)
def lessons_for(root, m):
    try:
        import mem
        q = " ".join(x for x in (m.get("objetivo"), m.get("feature_ativa")) if x)
        res = mem.search(root, q, k=5) or []
        out = []
        for r in res[:5]:
            if isinstance(r, dict):
                out.append({"id": r.get("id"), "texto": str(r.get("text") or r.get("texto") or r.get("rule") or "")[:240]})
        return out
    except Exception:
        return []


def ensure_feature(root, actor, m):
    """Feature ativa em state/ (uma por vez): fecha a anterior do mandato (DoD) e inicia a da vez."""
    import tree
    ctx = ctx_of(root, actor)
    tv = view(ctx)
    fa = m.get("feature_ativa")
    it = tv.get(fa or "")
    if it is None or tree.zone_of(it["path"]) != "backlog":
        return
    for f in m.get("features") or []:
        if f == fa:
            break
        fi = tv.get(f)
        if fi is not None and tree.zone_of(fi["path"]) == "state":
            tree_close(root, actor, f, "feature entregue pelo mandato %s (aceite verde + revisão final)" % m["id"])
    tree_start(root, actor, fa)


def progress_str(m, info, med=None):
    last = med or m.get("medicao") or {}
    if last.get("feature") == m.get("feature_ativa") and last.get("aceite"):
        v = len([x for x in last["aceite"] if x["verde"]])
        t = len(last["aceite"])
    else:
        base = [x for x in ((m.get("baseline") or {}).get("aceite") or []) if x.get("feature") == m.get("feature_ativa")]
        v, t = len([x for x in base if x.get("verde")]), len(criterios_de(m)) or len(base)
    acc = len([x for x in info.values() if x["cls"] == "aceito"])
    ondas = (m.get("plano") or {}).get("ondas") or []
    return "aceite %d/%d · nós %d/%d aceitos · onda %d/%d" % (v, t, acc, len(info), min(int(m.get("onda") or 0) + 1,
                                                                                          len(ondas)), len(ondas))


def tick_out(root, acao, por_que, **kw):
    import tree
    ctx = ctx_of(root)
    m = current(ctx.board)
    tv = view(ctx)
    if m is None:
        return {"mandato": None, "estado": None, "acao": "FIM", "por_que": "sem mandato (cs-auto propose ...)"}
    info, _ = classify(ctx, tv, m, m.get("feature_ativa"))
    fi = tv.get(m.get("feature_ativa") or "")
    d = {"mandato": m["id"], "estado": m["state"], "frente": tree.chain(tv, fi) if fi else (m.get("alvo") or {}).get("id"),
         "feature": m.get("feature_ativa"), "objetivo": m.get("objetivo"), "acao": acao, "alvo": None, "no": None,
         "agente": None, "model": None, "paths": None, "comando": None,
         "progresso": progress_str(m, info), "orcamento": orcamento_view(m, usage(ctx, tv, m)), "por_que": por_que,
         "evidencia": [], "criterios": None, "licoes": None, "escalada": None, "opcoes": None}
    d.update(kw)
    return d


def node_action(root, acao, x, por_que, comando, **kw):
    d = x.get("d") or {}
    model = (d.get("route_override") or {}).get("model") or (d.get("route") or {}).get("model")
    return tick_out(root, acao, por_que, alvo=x["n"].get("task"), no=x["n"]["id"], agente=kw.pop("agente", None) or
                    d.get("agent") or x["n"].get("agent"), model=model, paths=list(x["n"].get("paths") or []),
                    comando=comando, **kw)


def fail_evidence(root, x, vev=None):
    t = x.get("t") or {}
    vev = vev if vev is not None else verify_events(root)
    gr = (t.get("gate_report") or {}).get("build") or {}
    hist = []
    for d in t.get("delegations") or []:
        hist += vev.get(d["id"]) or []
    hist.sort(key=lambda r: r["seq"])
    last = hist[-1] if hist else {}
    sha = gr.get("output_sha256") or last.get("output_sha256") or ""
    ref = "verify:%s#%s:%s" % (x["n"].get("task"), t.get("attempts"), sha[:12])
    return [{"tipo": "E1", "ref": ref, "comando": gr.get("cmd") or t.get("verification_command"),
             "exit": gr.get("exit_code"), "output_sha256": sha, "tail": (gr.get("tail") or last.get("tail") or "")[-400:],
             "problemas": (last.get("problems") or [t.get("reject_reason")])[:5]}]


def orphans(m, info):
    out = []
    for o in m.get("orfas") or []:
        x = info.get(o.get("no"))
        if x and x["d"] and x["d"]["id"] == o.get("deleg") and int(x["t"].get("attempts") or 0) == int(o.get("tentativa") or 0) \
                and x["ds"] == "DISPATCHED":
            out.append(x)
    return out


def inflight_conflict(ctx, info, x):
    for y in info.values():
        if y is x or y["ds"] != "DISPATCHED":
            continue
        if node_conflict(ctx, x["n"], y["n"]) or (y["d"] or {}).get("agent") == (x["d"] or {}).get("agent"):
            return True
    return False


def model_actions(root, actor, m, info, order, allow_dispatch=True, allow_reflect=True):
    """Ação de julgamento pedida ao modelo (ou None). Inicia a task do nó (mecânico) antes do DISPATCH."""
    for x in orphans(m, info):
        return node_action(root, "ANSWER_ORPHAN", x, "delegação de %s ficou órfã (janela encerrada com o subagente em voo); "
                           "o motor decide pelo disco" % x["n"].get("task"), "cs-auto orphan %s" % x["n"].get("task"))
    if allow_reflect:
        for nid in order:
            x = info[nid]
            if x["cls"] == "rejeitado":
                ev = fail_evidence(root, x)
                return node_action(root, "REFLECT", x, "verify do nó %s reprovou: reflita ancorado no sinal externo antes do "
                                   "retry" % nid, "cs-auto reflect %s --texto '<o que falhou, por quê, o que muda>' "
                                   "--evidencia %s" % (x["n"].get("task"), ev[0]["ref"]), evidencia=ev)
    ctx = ctx_of(root, actor)
    tv = view(ctx)
    for nid in order:
        x = info[nid]
        if x["cls"] == "verificado" or (x["cls"] == "revisado" and engine.review_outcome(x["t"]) == "NEEDS_SPECIALIST"):
            done = set(r.get("by") for r in (x["t"].get("reviews") or []) if r.get("attempt") == x["t"].get("attempts"))
            gate = pick_gate(ctx, m, tv, exclude=done if x["cls"] == "revisado" else ())
            return node_action(root, "REVIEW", x, "verify do motor passou (exit 0); falta a review de um gate ≠ autor",
                               "cs-state review %s --by %s --verdict PASS|FAIL --findings '<arquivo:linha ...>'" % (
                                   x["n"].get("task"), gate), agente=gate)
    if allow_dispatch:
        ondas = (m.get("plano") or {}).get("ondas") or []
        cur = int(m.get("onda") or 0)
        wave = ondas[cur] if cur < len(ondas) else []
        for nid in wave:
            x = info.get(nid)
            if not x or not x["runnable"] or x["cls"] not in ("novo", "pronto"):
                continue
            if inflight_conflict(ctx, info, x):
                continue
            if x["cls"] == "novo":
                tree_start(root, actor, x["n"]["task"])
                ctx = ctx_of(root, actor)
                tv = view(ctx)
                info2, _ = classify(ctx, tv, m, m.get("feature_ativa"))
                x = info2[nid]
                if x["cls"] != "pronto":
                    return None
            d = x["d"]
            model = (d.get("route_override") or {}).get("model") or (d.get("route") or {}).get("model") or "sonnet"
            return node_action(root, "DISPATCH", x, "onda %d: nó %s pronto (deps aceitas, sem colisão em voo)" % (cur + 1, nid),
                               "Agent(subagent_type=%r, model=%r, description='%s: %s') — sem hook: cs-state dispatch %s "
                               "--manual --model %s" % (d["agent"], model, d["id"], x["n"].get("title") or nid,
                                                         x["n"].get("task"), model))
    fl = [info[nid] for nid in order if info[nid]["cls"] == "voo"]
    if fl:
        x = fl[0]
        return node_action(root, "IDLE_WAIT", x, "subagente(s) em voo: %s" % ", ".join(y["n"].get("task") for y in fl),
                           "aguarde o retorno (o subagente faz cs-state submit|abstain); depois cs-auto tick")
    return None


def do_tick(root, actor):
    out = None
    for _ in range(30):
        ctx = ctx_of(root, actor)
        m = open_mandate(ctx.board) or current(ctx.board)
        if m is None:
            return tick_out(root, "FIM", "sem mandato")
        st = m["state"]
        if st in TERMINAL:
            return tick_out(root, "FIM", "mandato %s terminal (%s): relatório em cs-auto report" % (m["id"], st),
                            comando="cs-auto report")
        if st == "PROPOSED":
            return tick_out(root, "ASK_HUMAN", "proposta aguarda o portão humano (aprovar, emendar ou abortar)",
                            comando="cs-auto approve --by <humano> [--orcamento despachos=,tentativas=,replanos=,minutos=]",
                            criterios=criterios_de(m) or m.get("criterios"))
        P = selo_problems(root, m)
        if P:   # antes de qualquer avanço: sem selo conferido o piloto não anda e não grava nada
            return tick_out(root, "ASK_HUMAN", "; ".join(P) + " — " + SELO_HINT,
                            comando="cs-auto conferir   (HUMANO, no terminal dele, com a senha)")
        if st == "PAUSED":
            return tick_out(root, "RESUME", "mandato pausado (estado anterior: %s)" % m.get("anterior"), comando="cs-auto resume")
        if st == "AWAITING_HUMAN":
            mechanics(root, actor, "hold")
            m = current(ctx_of(root, actor).board)
            es = open_escalations(m)
            e = es[-1] if es else None
            return tick_out(root, "ASK_HUMAN", "escalada %s (%s/%s): só o humano decide" % (
                (e or {}).get("id"), (e or {}).get("tipo"), (e or {}).get("condicao")),
                comando="cs-auto resolve --choice <%s> --by <humano> --decision '<decisão>'" % "|".join(
                    (e or {}).get("opcoes") or OPCOES), escalada=package_view(m, e) if e else None,
                opcoes=(e or {}).get("opcoes"))
        if st == "CHARTERED":
            ensure_feature(root, actor, m)
            mid = m["id"]
            les = lessons_for(root, m)
            attempt(root, actor, mid, "plan", {}, lambda to: [S(mid, "licoes", les), S(mid, "licoes_consultadas", True)])
            continue
        if st == "PLANNING":
            ensure_feature(root, actor, m)
            return plan_action(root, m, "PLAN")
        if st == "REPLANNING":
            return plan_action(root, m, "REPLAN")
        if st == "WRAPPING_UP":
            return run_wrapping(root, actor)
        if st == "INTEGRATING":
            out = run_integrating(root, actor)
            if out is None:
                continue
            return out
        if st == "RUNNING":
            out = run_running(root, actor)
            if out is None:
                continue
            return out
        return tick_out(root, "FIM", "estado desconhecido %s" % st)
    return out or tick_out(root, "IDLE_WAIT", "o piloto não convergiu neste tick; rode cs-auto tick de novo",
                           comando="cs-auto tick")


def plan_action(root, m, acao):
    crits = []
    last = m.get("medicao") or {}
    verde = dict((x["id"], x["verde"]) for x in last.get("aceite") or []) if last.get("feature") == m.get("feature_ativa") else {}
    for c in criterios_de(m):
        crits.append({"id": c["id"], "texto": c.get("texto"), "comando": c.get("cmd"), "verde": verde.get(c["id"], False)})
    if acao == "PLAN":
        return tick_out(root, "PLAN", "monte o DAG da feature %s (nós com agente, paths do território e --cobre); o motor "
                        "valida no submit" % m.get("feature_ativa"),
                        comando="cs-auto plan add-node --id 01 --tipo US --agent <agente> --title '<título>' --path <arquivo> "
                                "--cobre AC-1 [--deps ..] ; ... ; cs-auto plan submit",
                        criterios=crits, licoes=list(m.get("licoes") or []))
    rp = m.get("replano") or {}
    ev = list(rp.get("evidencia") or [])
    return tick_out(root, "REPLAN", "replano (%s): %s" % (rp.get("gatilho"), rp.get("por_que") or ""),
                    comando="cs-auto plan add-node ... ; cs-auto plan submit --motivo '<por quê>' --evidencia %s" % (
                        ev[0]["ref"] if ev else "<ref>"), evidencia=ev, criterios=crits, testes=rp.get("testes"),
                    licoes=list(m.get("licoes") or []))


def write_tick_event(root, actor, m, extra_ops=None, data=None):
    mid = m["id"]
    attempt(root, actor, mid, "tick", {}, (lambda to: list(extra_ops or [])), data=data)


def run_running(root, actor):
    ctx = ctx_of(root, actor)
    m = open_mandate(ctx.board)
    write_tick_event(root, actor, m)
    m = current(ctx_of(root, actor).board)
    g = detect_global(root, m)
    if g:
        escalate_global(root, actor, m, g)
        return None
    tv = view(ctx_of(root, actor))
    u = usage(tv.ctx, tv, m)
    ratio, dim = budget_ratio(m, u)
    if ratio >= float(mcfg("budget_soft_ratio", 0.8)):
        wrap_up(root, actor, m, "budget_hard" if ratio >= 1.0 else "budget_soft",
                data={"dimensao": dim, "uso": round(ratio, 3)})
        return None
    mechanics(root, actor, "run")
    ctx = ctx_of(root, actor)
    m = current(ctx.board)
    if m["state"] != "RUNNING":
        return None
    tv = view(ctx)
    info, order = classify(ctx, tv, m, m.get("feature_ativa"))
    act = model_actions(root, actor, m, info, order)
    if act is not None:
        return act
    ctx = ctx_of(root, actor)
    m = current(ctx.board)
    tv = view(ctx)
    info, order = classify(ctx, tv, m, m.get("feature_ativa"))
    ondas = (m.get("plano") or {}).get("ondas") or []
    cur = int(m.get("onda") or 0)
    wave = ondas[cur] if cur < len(ondas) else []
    busy = [nid for nid in wave if nid in info and (info[nid]["runnable"] or info[nid]["cls"] in PIPE + ("esperando",))]
    if busy:
        return tick_out(root, "IDLE_WAIT", "onda %d ainda em andamento (%s)" % (cur + 1, ", ".join(busy)),
                        comando="cs-auto tick")
    attempt(root, actor, m["id"], "wave_closed", {}, None, data={"onda": cur + 1})
    return None


def integ_record(m, med, info, tv=None):
    v = len([x for x in med["aceite"] if x["verde"]])
    acc = len([x for x in info.values() if x["cls"] == "aceito"])
    prev = m.get("progresso") or {}
    if prev.get("feature") != m.get("feature_ativa"):
        prev = {}
    prog = v > int(prev.get("verdes") or 0) or acc > int(prev.get("aceitos") or 0)
    sem = 0 if prog else int(m.get("sem_progresso") or 0) + 1
    rec = {"n": len(m.get("integracoes") or []) + 1, "feature": m.get("feature_ativa"), "verdes": v,
           "total": len(med["aceite"]), "aceitos": acc, "regressao_exit": (med.get("regressao") or {}).get("exit"),
           "progresso": prog, "at": hcore.now_iso()}
    return rec, sem


def integ_ops(m, med, rec, sem):
    mid = m["id"]
    mf = dict(m.get("medicoes_features") or {})
    mf[med.get("feature") or m.get("feature_ativa")] = med["aceite"]
    slim = {"feature": med.get("feature"), "aceite": med["aceite"], "at": med["at"],
            "regressao": ({k: med["regressao"][k] for k in ("exit", "output_sha256", "falhas", "cmd")}
                          if med.get("regressao") else None)}
    return [S(mid, "integracoes", list(m.get("integracoes") or []) + [rec]), S(mid, "sem_progresso", sem),
            S(mid, "progresso", {"feature": m.get("feature_ativa"), "verdes": rec["verdes"], "aceitos": rec["aceitos"]}),
            S(mid, "medicao", slim), S(mid, "medicoes_features", mf)]


def replan_trigger(root, m, med, info):
    ev = []
    reg = med.get("regressao") or {}
    testes = []
    gat = None
    if not reg_ok(m, reg):
        gat = "regressao"
        testes = list(reg.get("falhas") or [])
        for t in testes or ["?"]:
            ev.append({"tipo": "E1", "ref": "regressao:%s@%s" % (t, (reg.get("output_sha256") or "")[:12]), "teste": t,
                       "comando": reg.get("cmd"), "exit": reg.get("exit"), "output_sha256": reg.get("output_sha256")})
    rv = review_of(m)
    if rv and rv.get("verdict") == "FAIL" and not gat:
        gat = "revisao_final_fail"
        ev.append({"tipo": "evento", "ref": "revisao_final:%s" % rv.get("by"), "findings": rv.get("findings")})
    stuck = [nid for nid, x in info.items() if x["cls"] in ("travado", "bloqueado")]
    red = [x for x in med["aceite"] if not x["verde"]]
    for x in red:
        ev.append({"tipo": "E1", "ref": "aceite:%s@%s" % (x["id"], (x.get("output_sha256") or "")[:12]),
                   "criterio": x["id"], "comando": x.get("cmd"), "exit": x.get("exit"),
                   "output_sha256": x.get("output_sha256")})
    for nid in stuck:
        x = info[nid]
        ev.append({"tipo": "evento", "ref": "no:%s:%s" % (nid, x["ds"] or x["cls"]), "task": x["n"].get("task"),
                   "estado": x["ds"]})
    if not gat:
        if stuck:
            gat = "no_travado"
        elif red:
            gat = "dag_esgotado"
    why = {"regressao": "regressão vermelha vs baseline (%s)" % ", ".join(testes),
           "revisao_final_fail": "revisão final FAIL", "no_travado": "nó(s) %s travado(s) (ABSTAINED/BLOCKED)" % ", ".join(stuck),
           "dag_esgotado": "DAG esgotado com aceite %d/%d" % (len(med["aceite"]) - len(red), len(med["aceite"]))}.get(gat)
    return ({"gatilho": gat, "evidencia": ev, "testes": testes, "por_que": why} if gat else None)


def run_integrating(root, actor):
    ctx = ctx_of(root, actor)
    m = open_mandate(ctx.board)
    mid = m["id"]
    g = detect_global(root, m)
    if g:
        escalate_global(root, actor, m, g)
        return None
    fa = m.get("feature_ativa")
    med = medir(root, m, fa)
    tv = view(ctx)
    info, order = classify(ctx, tv, m, fa)
    all_green = bool(med["aceite"]) and all(x["verde"] for x in med["aceite"])
    pend = pending(info)
    if all_green and reg_ok(m, med.get("regressao")) and not review_of(m) and not pend:
        gate = pick_gate(ctx, m, tv)
        return tick_out(root, "FINAL_REVIEW", "aceite %d/%d verde e regressão verde: revisão final da frente por um gate ≠ "
                        "autores" % (len(med["aceite"]), len(med["aceite"])), agente=gate,
                        comando="cs-auto final-review --by %s --verdict PASS|FAIL --findings '<o que conferiu>'" % gate,
                        criterios=[{"id": x["id"], "verde": x["verde"], "output_sha256": x["output_sha256"]}
                                   for x in med["aceite"]])
    rec_i, sem = integ_record(m, med, info)
    base = {"_med": med, "_pendentes": pend}
    recs = []
    queued = feature_queue(m)
    tries = (["next_feature"] if queued else ["integrate_done"]) + ["integrate_ok"]
    for t in tries:
        a = dict(base)
        try:
            if t == "integrate_ok":
                ondas = (m.get("plano") or {}).get("ondas") or []
                nxt = int(m.get("onda") or 0)
                for i, w in enumerate(ondas):
                    if [x for x in w if x in info and (info[x]["runnable"] or info[x]["cls"] in PIPE)]:
                        nxt = i
                        break

                def ex(to, nxt=nxt):
                    return integ_ops(m, med, rec_i, sem) + [S(mid, "onda", nxt)]
            elif t == "integrate_done":
                rep = build_report(root, ctx, tv, m, "DONE", med)

                def ex(to, rep=rep):
                    return integ_ops(m, med, rec_i, sem) + [S(mid, "relatorio", rep)]
            else:
                def ex(to):
                    return integ_ops(m, med, rec_i, sem) + next_feature_ops(m)
            attempt(root, actor, mid, t, a, ex, recusadas=recs, data={"integracao": rec_i["n"]})
            if t == "integrate_done":
                close_feature(root, actor, m)
            return None
        except Refused as e:
            recs += refusals(t, e)
    locais = open_escalations(m, "dura_local")
    if locais and not pend:
        e = locais[0]

        def ex(to):
            return integ_ops(m, med, rec_i, sem)
        attempt(root, actor, mid, "escalate", {"condicao": e["condicao"], "_pacote": e}, ex, recusadas=recs,
                data={"pacote": e["id"], "tipo": e["tipo"], "integracao": rec_i["n"]})
        return None
    orf = orphan_criteria(m, med, info)
    if orf and not pend:
        _wrap_integ(root, actor, m, med, rec_i, sem, "criterios_orfaos", recs, {"criterios_orfaos": orf})
        return None
    if sem >= 2:
        _wrap_integ(root, actor, m, med, rec_i, sem, "no_progress", recs, {"sem_progresso": sem})
        return None
    trig = replan_trigger(root, m, med, info)
    try:
        def ex(to):
            return integ_ops(m, med, rec_i, sem) + [S(mid, "replano", trig)]
        attempt(root, actor, mid, "integrate_replan", dict(base, _gatilho=(trig or {}).get("gatilho")), ex,
                recusadas=recs, data={"gatilho": (trig or {}).get("gatilho"), "integracao": rec_i["n"]})
        return None
    except Refused as e:
        recs += refusals("integrate_replan", e)
    cond = "replans_exhausted"
    pk = new_package(m, "ESC-%d" % (len(m.get("escaladas") or []) + 1), "suave", cond, [], list(OPCOES_SEM_NO),
                     "replanos esgotados (%s/%s) com %s" % (m.get("replanos"), (m.get("orcamento") or {}).get("replanos"),
                                                            (trig or {}).get("por_que") or "aceite incompleto"),
                     evidencia=(trig or {}).get("evidencia"))

    def ex(to):
        return integ_ops(m, med, rec_i, sem) + [S(mid, "escaladas", list(m.get("escaladas") or []) + [pk]),
                                                S(mid, "replano", trig)]
    attempt(root, actor, mid, "escalate", {"condicao": cond, "_pacote": pk}, ex, recusadas=recs,
            data={"pacote": pk["id"], "tipo": "suave", "integracao": rec_i["n"]})
    return None


def _wrap_integ(root, actor, m, med, rec_i, sem, gatilho, recs, data):
    mid = m["id"]

    def ex(to):
        return integ_ops(m, med, rec_i, sem) + [S(mid, "gatilho_encerramento", gatilho)]
    d = {"gatilho": gatilho, "integracao": rec_i["n"]}
    d.update(data or {})
    attempt(root, actor, mid, "wrap_up", {"gatilho": gatilho}, ex, recusadas=recs, data=d)


def next_feature_ops(m):
    mid = m["id"]
    q = feature_queue(m)
    return [S(mid, "feature_ativa", q[0]), S(mid, "onda", 0), S(mid, "sem_progresso", 0), S(mid, "replano", None),
            S(mid, "progresso", None)]


def close_feature(root, actor, m):
    import tree
    ctx = ctx_of(root, actor)
    tv = view(ctx)
    it = tv.get(m.get("feature_ativa") or "")
    if it is not None and tree.zone_of(it["path"]) == "state":
        tree_close(root, actor, it["id"], "feature entregue pelo mandato %s (aceite verde + revisão final)" % m["id"])


def run_wrapping(root, actor, quiet=False):
    mechanics(root, actor, "wrap")
    ctx = ctx_of(root, actor)
    m = open_mandate(ctx.board)
    if m is None or m["state"] != "WRAPPING_UP":
        return None if quiet else tick_out(root, "FIM", "mandato encerrado")
    tv = view(ctx)
    info, order = classify(ctx, tv, m, None)
    act = model_actions(root, actor, m, info, order, allow_dispatch=False, allow_reflect=False)
    if act is not None:
        return None if quiet else act
    hand_back(root, actor, m)
    return None if quiet else tick_out(root, "FIM", "mandato %s HANDED_BACK (%s): entrega parcial honesta; abertos "
                                       "devolvidos ao backlog" % (m["id"], m.get("gatilho_encerramento")),
                                       comando="cs-auto report")


def hand_back(root, actor, m):
    import tree
    mid = m["id"]
    fa = m.get("feature_ativa")
    med = medir(root, m, fa) if fa else None
    motivo = "devolvido pelo mandato %s (encerramento: %s)" % (mid, m.get("gatilho_encerramento") or "?")

    def build(tv):
        ctx = tv.ctx
        cur = ctx.find(KIND, mid)
        info, order = classify(ctx, tv, cur, None)
        abertos = [nid for nid in order if info[nid]["cls"] not in ("aceito", "descartado", "devolvido")]
        rep0 = build_report(root, ctx, tv, cur, "HANDED_BACK", med, devolvidos=[{"no": nid} for nid in abertos])
        box = {}

        def ex(to):
            devs = []
            for nid in abertos:
                x = info[nid]
                it = x["it"]
                why = "%s — nó %s (%s)" % (motivo, nid, x["cls"])
                if it is not None and x["t"] is None and tree.zone_of(it["path"]) == "state":
                    novo = tree._to_backlog_task(tv, tv.items[it["id"]], why)
                    devs.append({"no": nid, "task": it["id"], "novo_id": novo, "motivo": why})
                else:
                    nn = tree.add_task_item(tv, node_spec(cur, x["n"]), x["n"].get("title") or nid, "backlog", None,
                                            extra={"mandato": mid, "no": nid, "devolvido_de": x["n"].get("task"),
                                                   "motivo": why})
                    nn = tv.items[nn["id"]]
                    tv.note(nn, "devolvido", why)
                    tv.put(nn)
                    devs.append({"no": nid, "task": x["n"].get("task"), "novo_id": nn["id"], "motivo": why})
            rep = dict(rep0, devolvidos=devs)
            box["rep"] = rep
            return [S(mid, "relatorio", rep), S(mid, "devolvidos", devs)]
        ev = tr(ctx, mid, "hand_back", {"_relatorio": rep0}, ex, data={"gatilho": cur.get("gatilho_encerramento")})
        evs = [ev]
        if tv.ops or tv.board_ops:
            evs.append(tv.event("devolver", mid, {"mandato": mid}))
        return evs
    commit_tree(root, actor, build)


# ================================================================ comandos do modelo/motor
def find_node_by_task(m, task):
    for n in plano_nos(m):
        if n.get("task") == task or n["id"] == task:
            return n
    return None


def cmd_reflect(root, actor, a):
    import cmds
    ctx = ctx_of(root, actor)
    m = _need(ctx.board, ("RUNNING",))
    tv = view(ctx)
    n = find_node_by_task(m, a.task)
    if n is None:
        raise Refused("%s não é task de nó do mandato %s" % (a.task, m["id"]))
    info, _ = classify(ctx, tv, m, None)
    x = info.get(n["id"])
    if not x or x["cls"] != "rejeitado":
        raise Refused("nó %s não espera reflexão (estado %s)" % (n["id"], (x or {}).get("cls")))
    if not (a.texto or "").strip():
        raise Refused("reflexão: --texto obrigatório (o que falhou, por quê, o que muda)")
    ev = fail_evidence(root, x)
    refs = [e["ref"] for e in ev]
    if not (a.evidencia or "").strip():
        raise Refused("reflexão sem --evidencia: cite o sinal externo (%s)" % ", ".join(refs))
    if a.evidencia not in refs and not file_line_ok(root, a.evidencia):
        raise Refused("evidência %r não é do sinal externo: use evidencia[].ref do tick (%s) ou arquivo:linha existente" % (
            a.evidencia, ", ".join(refs)))
    tree_note(root, actor, n["task"], "reflexao", texto=a.texto, evidencia=a.evidencia, tentativa=x["t"].get("attempts"),
              mandato=m["id"])
    cmds.retry(root, actor, x["t"]["id"], "reflexão ancorada em %s: %s | %s" % (
        a.evidencia, a.texto, x["t"].get("reject_reason") or ""))
    return ["reflexão registrada em %s (sinal %s); retry BRIEFED — cs-auto tick" % (n["task"], a.evidencia)]


def changed_in_scope(root, t, d):
    dirty = engine.git_dirty(root) or {}
    base = d.get("baseline") or {}
    ap = t.get("allowed_paths") or []
    out = set()
    for p, sha in dirty.items():
        if hcore.matches_any(p, ap) and base.get(p, "__absent__") != sha:
            out.add(p)
    for p in base:
        if p != "__nogit__" and p not in dirty and hcore.matches_any(p, ap):
            out.add(p)
    return sorted(out)


def cmd_orphan(root, actor, a):
    import cmds
    ctx = ctx_of(root, actor)
    m = _need(ctx.board, ("RUNNING", "WRAPPING_UP"))
    tv = view(ctx)
    n = find_node_by_task(m, a.task)
    if n is None:
        raise Refused("%s não é task de nó do mandato %s" % (a.task, m["id"]))
    info, _ = classify(ctx, tv, m, None)
    x = info.get(n["id"])
    if not x or x not in orphans(m, info):
        raise Refused("%s não está órfã (estado %s)" % (a.task, (x or {}).get("ds")))
    t, d = x["t"], x["d"]
    ch = changed_in_scope(root, t, d)
    if ch:
        cmds.submit(root, "motor", t["id"], {"files_changed": ch, "checks_run": ["motor: órfã com diff — verify do motor"],
                                             "risks": ["entrega recuperada de janela encerrada (sem submit do subagente)"],
                                             "handoff_notes": "órfã: o motor submeteu o diff encontrado em allowed_paths"})
        return ["órfã %s COM diff (%s): submetida pelo motor → verify (sem redespacho) — cs-auto tick" % (
            a.task, ", ".join(ch))]
    cmds.return_(root, actor, t["id"], "órfã: janela encerrada sem entrega (requeue pelo motor)")
    cmds.retry(root, actor, t["id"], "requeue de órfã sem diff (nenhuma alteração em allowed_paths)")
    return ["órfã %s SEM diff: devolvida à fila (novo despacho, conta tentativa) — cs-auto tick" % a.task]


def cmd_final_review(root, actor, a):
    ctx = ctx_of(root, actor)
    m = _need(ctx.board)
    mid = m["id"]
    if m["state"] != "INTEGRATING":
        raise Refused("mandato %s em %s: final-review só em INTEGRATING com aceite 100%% verde" % (mid, m["state"]))
    fa = m.get("feature_ativa")
    med = medir(root, m, fa)
    if not reg_ok(m, med.get("regressao")):
        raise Refused("regressão vermelha: %s — revisão final só com regressão verde" % (med["regressao"] or {}).get("cmd"))
    rev = {"by": a.by, "verdict": (a.verdict or "").upper(), "findings": a.findings or "", "feature": fa,
           "versao": (m.get("plano") or {}).get("versao"), "at": hcore.now_iso()}
    tv = view(ctx)
    info, _ = classify(ctx, tv, m, fa)
    rec_i, sem = integ_record(m, med, info)
    aa = {"revisao": rev, "_med": med, "by": a.by}
    if rev["verdict"] == "PASS":
        t = "next_feature" if feature_queue(m) else "integrate_done"
        if g_final_review_pass(ctx, KIND, m, {"revisao": rev}) or g_acceptance_all_green(ctx, KIND, m, {"_med": med}):
            # recusa observável pela máquina: a transição de saída é avaliada com a revisão proposta (e recusa)
            attempt(root, actor, mid, t, aa, None, data={"revisao": {"by": a.by, "verdict": "PASS"}})
            raise Refused("revisão final recusada")
        # revisão válida: registrada na cadeia (dado, não transição); o tick fecha a frente (integrate_done/next_feature)
        commit(root, actor, lambda c: [engine.Event("m5.revisao_final", mid, [
            S(mid, "revisoes_finais", list(m.get("revisoes_finais") or []) + [rev])], {"revisao": rev})])
        return ["revisão final PASS de %s registrada — o piloto fecha a frente (%s): cs-auto tick" % (a.by, t)]
    if rev["verdict"] != "FAIL":
        raise Refused(G("final_review_pass", "--verdict deve ser PASS|FAIL"))
    P = [p for p in g_final_review_pass(ctx, KIND, m, dict(aa, revisao=dict(rev, verdict="PASS")))]
    if P:
        raise Refused(P)
    trig = {"gatilho": "revisao_final_fail", "por_que": "revisão final FAIL de %s" % a.by, "testes": [],
            "evidencia": [{"tipo": "evento", "ref": "revisao_final:%s" % a.by, "findings": a.findings}]}

    def ex(to):
        return integ_ops(m, med, rec_i, sem) + [S(mid, "revisoes_finais", list(m.get("revisoes_finais") or []) + [rev]),
                                                S(mid, "replano", trig)]
    attempt(root, actor, mid, "integrate_replan", dict(aa, _gatilho="revisao_final_fail"), ex,
            data={"gatilho": "revisao_final_fail"})
    return ["%s REPLANNING — revisão final FAIL de %s: %s" % (mid, a.by, a.findings)]


def cmd_escalate(root, actor, a):
    ctx = ctx_of(root, actor)
    m = _need(ctx.board)
    mid = m["id"]
    nos = [a.no] if a.no else []
    opc = list(OPCOES if a.no else OPCOES_SEM_NO)
    tipo = "suave" if a.condicao in ("material_ambiguity", "replans_exhausted") else (
        "dura_global" if a.condicao == "acceptance_changed" else "dura_local")
    if a.no and a.no not in [n["id"] for n in plano_nos(m)]:
        raise Refused("nó %s não está no plano" % a.no)
    if a.evidencia and not (file_line_ok(root, a.evidencia) or a.evidencia in evidence_refs(m)):
        raise Refused("evidência %r inexistente (arquivo:linha ou evidencia[].ref do tick)" % a.evidencia)
    pk = new_package(m, "ESC-%d" % (len(m.get("escaladas") or []) + 1), tipo, a.condicao, nos, opc,
                     "escalada sinalizada pelo modelo: %s" % a.condicao, no=a.no,
                     evidencia=[{"tipo": "E1", "ref": a.evidencia}] if a.evidencia else [])

    def ex(to):
        return [S(mid, "escaladas", list(m.get("escaladas") or []) + [pk])]
    attempt(root, actor, mid, "escalate", {"condicao": a.condicao, "_pacote": pk, "evidencia": a.evidencia}, ex,
            data={"pacote": pk["id"], "tipo": tipo})
    return ["%s AWAITING_HUMAN — escalada %s (%s, %s): só o humano decide (cs-auto resolve ...)" % (
        mid, pk["id"], tipo, a.condicao)]


def pause(root, actor, motivo=None):
    ctx = ctx_of(root, actor)
    m = _need(ctx.board)
    mid = m["id"]
    tv = view(ctx)
    info, _ = classify(ctx, tv, m, None)
    orf = [{"no": nid, "task": x["n"].get("task"), "m2": x["t"]["id"], "deleg": x["d"]["id"],
            "tentativa": int(x["t"].get("attempts") or 0)} for nid, x in info.items() if x["ds"] == "DISPATCHED"]

    def ex(to):
        return [S(mid, "orfas", orf), S(mid, "pausa", {"motivo": motivo, "at": hcore.now_iso(),
                                                      "eventos": ctx.board.get("event_count")})]
    attempt(root, actor, mid, "pause", {"motivo": motivo}, ex, data={"motivo": motivo, "orfas": [o["task"] for o in orf]})
    return m


def resume(root, actor):
    ctx = ctx_of(root, actor)
    m = _need(ctx.board)
    mid = m["id"]
    recs, _, _ = hcore.read_chain(hcore.state_paths(root)["events"])
    since = int((m.get("pausa") or {}).get("eventos") or 0)
    delta = ["%s %s" % (r.get("type"), r.get("entity") or "") for r in recs[since:]
             if not str(r.get("type") or "").startswith("mandato.")][-12:]
    attempt(root, actor, mid, "resume", {}, None, data={"delta": delta})
    return delta


def cmd_spend(root, actor, a):
    ctx = ctx_of(root, actor)
    m = _need(ctx.board)
    if m["state"] != "RUNNING":
        raise Refused("spend: custo autodeclarado só é anotado em RUNNING (nunca controla orçamento)")
    g = dict(m.get("gasto") or {})
    g["usd_autodeclarado"] = float(g.get("usd_autodeclarado") or 0) + float(a.usd or 0)
    write_tick_event(root, actor, m, [S(m["id"], "gasto", g)], data={"usd_autodeclarado": a.usd})
    return ["gasto AUTODECLARADO anotado (usd=%s): não muda o custo medido nem dispara parada" % g["usd_autodeclarado"]]


# ================================================================ status / relatório / pacotes
def package_view(m, e):
    if not e:
        return None
    return {"id": e.get("id"), "tipo": e.get("tipo"), "condicao": e.get("condicao"), "no": e.get("no"),
            "nos": e.get("nos"), "opcoes": e.get("opcoes"), "pacote": "%s/%s" % (pasta_rel(m), e.get("arquivo")),
            "aberta": e.get("aberta"), "por_que": e.get("por_que"), "evidencia": e.get("evidencia"),
            "escolha": e.get("escolha"), "decisao": e.get("decisao")}


def candidate_lessons(tv, m, info):
    out = []
    for nid, x in info.items():
        if x["cls"] != "aceito" or not x["it"] or int((x["t"] or {}).get("attempts") or 0) < 2:
            continue
        for h in x["it"].get("historico") or []:
            if h.get("acao") == "reflexao":
                out.append({"task": x["n"].get("task"), "no": nid, "texto": h.get("texto"), "sinal": h.get("evidencia")})
    return out


def status_json(root):
    ctx = ctx_of(root)
    m = current(ctx.board)
    if not m:
        return {"mandato": None}
    tv = view(ctx)
    info, order = classify(ctx, tv, m, None)
    u = usage(ctx, tv, m)
    last = m.get("medicao") or {}
    if last.get("feature") == m.get("feature_ativa") and last.get("aceite"):
        ac = {"verdes": len([x for x in last["aceite"] if x["verde"]]), "total": len(last["aceite"])}
    else:
        base = [x for x in ((m.get("baseline") or {}).get("aceite") or []) if x.get("feature") == m.get("feature_ativa")]
        ac = {"verdes": len([x for x in base if x.get("verde")]), "total": len(criterios_de(m))}
    b = m.get("baseline") or {}
    nos = []
    fz = set(congelados(m))
    for nid in order:
        x = info[nid]
        n = x["n"]
        nos.append({"id": nid, "task": n.get("task"), "agente": (x["d"] or {}).get("agent") or n.get("agent"),
                    "paths": n.get("paths"), "deps": n.get("deps") or [], "cobre": n.get("cobre") or [],
                    "estado": x["status"], "delegacao": x["ds"], "classe": x["cls"], "congelado": nid in fz,
                    "feature": n.get("feature"), "tipo": n.get("tipo")})
    pl = m.get("plano") or {}
    return {"mandato": m["id"], "estado": m["state"], "alvo": m.get("alvo"), "feature_ativa": m.get("feature_ativa"),
            "objetivo": m.get("objetivo"), "pasta": pasta_rel(m), "classe": m.get("classe"), "rigor": m.get("rigor"),
            "orcamento": orcamento_view(m, u), "aceite": ac,
            "baseline": {"aceite": [{"id": x["id"], "verde": x.get("verde"), "output_sha256": x.get("output_sha256"),
                                     "feature": x.get("feature")} for x in b.get("aceite") or []],
                         "regressao": ({"exit": b["regressao"].get("exit"), "output_sha256": b["regressao"].get("output_sha256")}
                                       if b.get("regressao") else None), "head": b.get("head")},
            "plano": {"versao": pl.get("versao"), "ondas": pl.get("ondas") or [], "nos": nos, "onda_atual": m.get("onda")},
            "congelados": sorted(fz), "escaladas": [package_view(m, e) for e in m.get("escaladas") or []],
            "licoes_candidatas": candidate_lessons(tv, m, info), "anterior": m.get("anterior"),
            "assinatura": m.get("assinatura"), "gatilho_encerramento": m.get("gatilho_encerramento")}


def peek(root):
    """Próxima ação SEM efeito colateral (hook Stop / status --brief): (acao, alvo) ou None quando não há o que conduzir."""
    ctx = ctx_of(root)
    m = open_mandate(ctx.board)
    if not m:
        return None
    st = m["state"]
    if st in WAITING:
        return None
    if st in ("CHARTERED", "PLANNING"):
        return ("PLAN", m.get("feature_ativa"))
    if st == "REPLANNING":
        return ("REPLAN", m.get("feature_ativa"))
    if st == "INTEGRATING":
        return ("INTEGRAR", m.get("feature_ativa"))
    tv = view(ctx)
    info, order = classify(ctx, tv, m, None if st == "WRAPPING_UP" else m.get("feature_ativa"))
    for x in orphans(m, info):
        return ("ANSWER_ORPHAN", x["n"].get("task"))
    for nid in order:
        x = info[nid]
        if x["cls"] == "retornado" or x["cls"] == "revisado":
            return ("TICK", x["n"].get("task"))
        if x["cls"] == "rejeitado" and st == "RUNNING":
            return ("REFLECT", x["n"].get("task"))
        if x["cls"] == "verificado":
            return ("REVIEW", x["n"].get("task"))
    if st == "RUNNING":
        ondas = (m.get("plano") or {}).get("ondas") or []
        cur = int(m.get("onda") or 0)
        for nid in (ondas[cur] if cur < len(ondas) else []):
            x = info.get(nid)
            if x and x["runnable"] and x["cls"] in ("novo", "pronto"):
                return ("DISPATCH", x["n"].get("task"))
    for nid in order:
        if info[nid]["cls"] == "voo":
            return ("IDLE_WAIT", info[nid]["n"].get("task"))
    return ("TICK", None)


def status_brief(root):
    st = status_json(root)
    if not st.get("mandato"):
        return ["sem mandato (cs-auto propose --feature FEA-nnn ...)"]
    nx = peek(root)
    o = st["orcamento"]
    L = ["mandato %s [%s] — objetivo: %s" % (st["mandato"], st["estado"], st.get("objetivo")),
         "frente: %s · feature ativa: %s" % ((st.get("alvo") or {}).get("id"), st.get("feature_ativa")),
         "aceite: %d/%d verdes · plano v%s ondas %s" % (st["aceite"]["verdes"], st["aceite"]["total"],
                                                         st["plano"].get("versao"), json.dumps(st["plano"].get("ondas"))),
         "orçamento: despachos %s/%s · tentativas %s/%s · replanos %s/%s · minutos %s/%s" % (
             o["despachos"]["usado"], o["despachos"]["limite"], o["tentativas"]["usado"], o["tentativas"]["limite"],
             o["replanos"]["usado"], o["replanos"]["limite"], o["minutos"]["usado"], o["minutos"]["limite"])]
    es = [e for e in st["escaladas"] if e.get("aberta")]
    for e in es[:3]:
        L.append("escalada aberta %s (%s/%s) nós %s — opções %s" % (e["id"], e["tipo"], e["condicao"], e.get("nos"),
                                                                   ", ".join(e.get("opcoes") or [])))
    if st["estado"] in ("PROPOSED", "AWAITING_HUMAN"):
        L.append("1º passo (HUMANO): cs-auto %s --by <humano> ..." % ("approve" if st["estado"] == "PROPOSED" else "resolve --choice <opção>"))
    elif st["estado"] == "PAUSED":
        L.append("1º passo: cs-auto resume")
    elif st["estado"] in TERMINAL:
        L.append("1º passo: cs-auto report (mandato terminal)")
    else:
        L.append("1º passo: cs-auto tick%s" % ((" (próxima ação: %s %s)" % nx) if nx else ""))
    return L[:20]


def tick_text(d):
    L = ["%s [%s] objetivo: %s" % (d.get("mandato"), d.get("estado"), d.get("objetivo")),
         "frente: %s" % d.get("frente"), "ação: %s%s" % (d.get("acao"), (" %s" % d["alvo"]) if d.get("alvo") else ""),
         "por quê: %s" % d.get("por_que")]
    if d.get("agente"):
        L.append("agente: %s%s" % (d["agente"], (" (model %s)" % d["model"]) if d.get("model") else ""))
    if d.get("comando"):
        L.append("comando: %s" % d["comando"])
    if d.get("progresso"):
        L.append("progresso: %s" % d["progresso"])
    for e in (d.get("evidencia") or [])[:3]:
        L.append("evidência: %s" % e.get("ref"))
    if d.get("opcoes"):
        L.append("opções (humano): %s" % ", ".join(d["opcoes"]))
    return "\n".join(L[:30])


def cmd_report(root):
    ctx = ctx_of(root)
    m = current(ctx.board)
    if not m:
        raise Refused("sem mandato")
    if m.get("relatorio") and m["state"] in TERMINAL:
        return m["relatorio"]
    tv = view(ctx)
    return build_report(root, ctx, tv, m, m["state"], m.get("medicao"))


# ================================================================ materialização e validação dos arquivos do mandato
def files_of(m):
    out = {"mandato.json5": m}
    for p in m.get("planos") or []:
        out["plano.v%d.json5" % int(p.get("versao") or 0)] = p
    for e in m.get("escaladas") or []:
        if e.get("arquivo"):
            out[e["arquivo"]] = {"mandato": m["id"], "pacote": e}
    if m.get("relatorio"):
        out["relatorio.json5"] = m["relatorio"]
    return out


def materialize(root, board):
    for m in all_mandates(board):
        rel = pasta_rel(m)
        d = os.path.join(root, rel)
        for z in ("state", "archive"):
            other = os.path.join(root, hcore.STATE_DIR, z, "mandatos", m["id"])
            if os.path.realpath(other) != os.path.realpath(d) and os.path.isdir(other):
                shutil.rmtree(other, ignore_errors=True)
        os.makedirs(d, exist_ok=True)
        for name, obj in files_of(m).items():
            data = j5.dumps(obj, header=HEADER).encode("utf-8")
            p = os.path.join(d, name)
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    if f.read() == data:
                        continue
            hcore.atomic_write_bytes(p, data)


def validate_files(root, board):
    E = []
    for m in all_mandates(board):
        rel = pasta_rel(m)
        for name, obj in files_of(m).items():
            p = os.path.join(root, rel, name)
            if not os.path.isfile(p):
                E.append("mandato %s: %s/%s ausente (removido à mão?)" % (m["id"], rel, name))
                continue
            try:
                got = hcore.canonical(j5.load(p))
            except (OSError, ValueError):
                got = None
            if got != hcore.canonical(obj):
                E.append("edição à mão em %s/%s (mandato %s): o arquivo difere do que o motor gravou — desfaça "
                         "(o mandato só muda por cs-auto)" % (rel, name, m["id"]))
    return E


# ================================================================ integração com guard / árvore / M2
def frozen_released(board, task):
    """Task M2 de nó congelado liberado por decisão humana (retomar/trocar-agente) pode escrever em frozen_paths."""
    tid = (task or {}).get("tree_id")
    it = (board.get("tree") or {}).get(tid or "") or {}
    mid, no = it.get("mandato"), it.get("no")
    if not mid:
        return False
    m = hcore.find(board, KIND, mid)
    return bool(m and no in (m.get("liberados") or []))


def task_mandate(board, task):
    tid = (task or {}).get("tree_id")
    it = (board.get("tree") or {}).get(tid or "") or {}
    mid = it.get("mandato")
    return (hcore.find(board, KIND, mid) if mid else None), it.get("no")


def dispatch_problems(ctx, deleg):
    """Guarda budget_available (M2): task de nó do mandato só despacha em RUNNING, fora de ramo congelado e abaixo do
    corte de 80% do orçamento (o despacho que atinge o corte já está em voo e fecha)."""
    task = hcore.task_of_deleg(ctx.board, deleg["id"])
    m, no = task_mandate(ctx.board, task)
    if not m:
        return []
    if m.get("state") != "RUNNING":
        return ["mandato %s em %s: nenhum despacho novo de nó (%s)" % (m["id"], m.get("state"), no)]
    if no in congelados(m):
        return ["nó %s do mandato %s congelado (escalada aberta): aguarda a decisão humana" % (no, m["id"])]
    tv = view(ctx)
    ratio, dim = budget_ratio(m, usage(ctx, tv, m))
    if ratio >= float(mcfg("budget_soft_ratio", 0.8)):
        return ["mandato %s: orçamento de %s em %d%% (corte de 80%%): nenhum despacho novo" % (m["id"], dim, int(ratio * 100))]
    return []


def dag_collision(tv, it):
    """Avulsa (task fora do mandato) cujo allowed_path colide com nó aberto do DAG ativo: recusada no start."""
    board = tv.ctx.board
    m = open_mandate(board)
    if not m or it.get("mandato") or not m.get("plano"):
        return None
    info, order = classify(tv.ctx, tv, m, None)
    ap = it.get("allowed_paths") or []
    for nid in order:
        x = info[nid]
        if x["cls"] in ("aceito", "descartado", "devolvido"):
            continue
        hit = [p for p in ap if hcore.scopes_overlap([p], x["n"].get("paths") or [])]
        if hit:
            return "%s colide com o DAG ativo do mandato %s (nó %s, %s): espere o mandato ou peça ao humano" % (
                ", ".join(hit), m["id"], nid, ", ".join(x["n"].get("paths") or []))
    return None


def mandate_shared_file(board, task, f):
    """diff_check: arquivo declarado e já entregue (mesmo conteúdo) por outro nó ACEITO do mesmo mandato — o motor
    separou os dois em sub-ondas justamente pelo arquivo comum; a reescrita idêntica não é mentira de files_changed."""
    m, no = task_mandate(board, task)
    if not m:
        return False
    for n in plano_nos(m):
        if n["id"] == no or f not in (n.get("paths") or []):
            continue
        it = (board.get("tree") or {}).get(n.get("task") or "") or {}
        t = hcore.find(board, "task", it.get("m2") or "") if it.get("m2") else None
        if t and t.get("status") == "ACCEPTED" and f in ((t.get("submission") or {}).get("files_changed") or []):
            return True
    return False


HUMAN_SUB_RE = re.compile(r"(?:^|[\s;&|()])(?:\S*/)?(cs-auto|auto\.py)\b")


def human_act_in_command(command):
    """`cs-auto approve|amend|resolve|abort|stop` (inclusive .swarm/bin/cs-auto e python3 …/auto.py) num comando Bash."""
    if not isinstance(command, str) or "auto" not in command:
        return None
    for seg in re.split(r"[;&|\n]+", command):
        try:
            toks = shlex.split(seg)
        except ValueError:
            toks = seg.split()
        for i, t in enumerate(toks):
            if os.path.basename(t) not in ("cs-auto", "auto.py"):
                continue
            j = i + 1
            while j < len(toks):
                if toks[j] in ("--root", "--actor"):
                    j += 2
                    continue
                if toks[j].startswith("--root=") or toks[j].startswith("--actor="):
                    j += 1
                    continue
                break
            if j < len(toks) and toks[j] in HUMAN_CMDS:
                return toks[j]
    return None


def stop_decision(root, payload):
    """Hook Stop no mandato: (bloqueia?, motivo). None = sem mandato aberto (o hook segue o legado)."""
    try:
        board = hcore.load_board(root)
    except StateError:
        return None
    m = open_mandate(board)
    if not m:
        return None
    nx = peek(root)
    if nx is None:
        return (False, None)
    p = stop_path(root)
    recs, _, _ = hcore.read_chain(hcore.state_paths(root)["events"])
    mark = len([r for r in recs if (str(r.get("type") or "").startswith("mandato.") and r.get("type") != "mandato.tick")
                or str(r.get("type") or "").startswith("delegation.")])
    st = {}
    if os.path.isfile(p):
        try:
            st = j5.load(p) or {}
        except (OSError, ValueError):
            st = {}
    blocks = int(st.get("blocks") or 0) if st.get("mandato") == m["id"] and st.get("marca") == mark else 0
    if blocks >= STOP_MAX_BLOCKS:
        pause(root, "hook", "anti-loop: %d bloqueios do Stop sem transição de M5/M2 (diagnóstico: próxima ação %s %s)" % (
            blocks, nx[0], nx[1] or ""))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        hcore.write_json5(p, {"mandato": m["id"], "marca": -1, "blocks": 0}, "contador anti-loop do hook Stop (cs-auto)")
        return (False, None)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    hcore.write_json5(p, {"mandato": m["id"], "marca": mark, "blocks": blocks + 1}, "contador anti-loop do hook Stop (cs-auto)")
    return (True, "mandato %s [%s] segue: próxima ação %s %s — rode `cs-auto tick` (objetivo: %s)" % (
        m["id"], m["state"], nx[0], nx[1] or "", m.get("objetivo")))


def session_start(root):
    try:
        board = hcore.load_board(root)
    except StateError:
        return None
    m = open_mandate(board)
    if not m:
        return None
    if m["state"] == "PAUSED":
        try:
            resume(root, "hook")
        except Refused:
            pass
    L = status_brief(root)
    return "<<DADO mandato (cs-auto status --brief)>>\n%s\n<</DADO>>\nO loop é do motor: rode `cs-auto tick` e execute só a " \
           "ação pedida." % "\n".join(L)


def pre_compact(root):
    try:
        board = hcore.load_board(root)
    except StateError:
        return None
    m = open_mandate(board)
    if not m:
        return None
    if m["state"] in W:
        pause(root, "hook", "pre-compact: checkpoint antes da compactação")
    if hcore.tree_mode(root):
        import session
        session.tree_save(root)
    return m["id"]


# ================================================================ CLI
def build_parser():
    ap = argparse.ArgumentParser(prog="cs-auto", description="piloto do modo autônomo (mandato M5)")
    ap.add_argument("--root")
    ap.add_argument("--actor", default=os.environ.get("CS_ACTOR", "lead"))
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("propose")
    p.add_argument("--feature")
    p.add_argument("--sprint")
    p.add_argument("--spec")
    p.add_argument("--objetivo")
    p.add_argument("--nos", type=int)
    p.add_argument("--criterio", action="append", default=[])
    p.add_argument("--regressao")
    p.add_argument("--classe")
    p.add_argument("--portao", action="append", default=[])
    p.add_argument("--rigor", choices=["lean", "standard", "paranoid"])
    p = sub.add_parser("senha")
    p.add_argument("acao", choices=["definir"])
    sub.add_parser("conferir")
    for name in ("approve", "amend", "abort", "stop"):
        p = sub.add_parser(name)
        p.add_argument("--by")
        if name in ("approve", "amend"):
            p.add_argument("--orcamento")
        if name != "approve":
            p.add_argument("--reason")
    p = sub.add_parser("resolve")
    p.add_argument("--choice", required=True)
    p.add_argument("--by")
    p.add_argument("--decision")
    p.add_argument("--agent")
    p.add_argument("--escalada")
    p = sub.add_parser("tick")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("status")
    p.add_argument("--json", action="store_true")
    p.add_argument("--brief", action="store_true")
    p = sub.add_parser("plan")
    ps = p.add_subparsers(dest="pcmd")
    for name in ("add-node", "edit-node"):
        q = ps.add_parser(name)
        q.add_argument("--id", required=True)
        q.add_argument("--tipo", type=str.upper, choices=["US", "BUG", "FIX"])
        q.add_argument("--agent")
        q.add_argument("--title")
        q.add_argument("--path", action="append", default=[])
        q.add_argument("--deps")
        q.add_argument("--cobre")
        q.add_argument("--verify-cmd")
        q.add_argument("--teste")
    ps.add_parser("reset")
    q = ps.add_parser("submit")
    q.add_argument("--motivo")
    q.add_argument("--evidencia")
    p = sub.add_parser("reflect")
    p.add_argument("task")
    p.add_argument("--texto")
    p.add_argument("--evidencia")
    p = sub.add_parser("orphan")
    p.add_argument("task")
    p = sub.add_parser("final-review")
    p.add_argument("--by", required=True)
    p.add_argument("--verdict", required=True)
    p.add_argument("--findings", default="")
    p = sub.add_parser("escalate")
    p.add_argument("--condicao", required=True)
    p.add_argument("--evidencia")
    p.add_argument("--no")
    p = sub.add_parser("pause")
    p.add_argument("--motivo")
    sub.add_parser("resume")
    p = sub.add_parser("spend")
    p.add_argument("--usd", type=float, required=True)
    p = sub.add_parser("report")
    p.add_argument("--json", action="store_true")
    return ap


def run(a, extras):
    root = hcore.resolve_root(a.root)
    if a.cmd == "senha":
        return cmd_senha(root, a)
    import tree
    tree.need_tree(root)
    actor = a.actor
    c = a.cmd
    if c == "conferir":
        return cmd_conferir(root, actor)
    if c == "propose":
        return cmd_propose(root, actor, a)
    if c == "approve":
        return cmd_approve(root, actor, a, extras)
    if c == "amend":
        return cmd_amend(root, actor, a, extras)
    if c == "abort":
        return cmd_abort(root, actor, a, extras)
    if c == "stop":
        return cmd_stop(root, actor, a, extras)
    if c == "resolve":
        return cmd_resolve(root, actor, a, extras)
    if c == "tick":
        d = do_tick(root, actor)
        return [json.dumps(d, ensure_ascii=False)] if a.json else [tick_text(d)]
    if c == "status":
        if a.brief:
            return status_brief(root)
        st = status_json(root)
        if a.json:
            return [json.dumps(st, ensure_ascii=False)]
        if not st.get("mandato"):
            return ["sem mandato"]
        return status_brief(root)
    if c == "plan":
        return cmd_plan(root, actor, a)
    if c == "reflect":
        return cmd_reflect(root, actor, a)
    if c == "orphan":
        return cmd_orphan(root, actor, a)
    if c == "final-review":
        return cmd_final_review(root, actor, a)
    if c == "escalate":
        return cmd_escalate(root, actor, a)
    if c == "pause":
        m = pause(root, actor, a.motivo)
        return ["%s PAUSED (%s)" % (m["id"], a.motivo or "pausa")]
    if c == "resume":
        delta = resume(root, actor)
        m = current(ctx_of(root, actor).board)
        return ["%s %s (retomado)%s" % (m["id"], m["state"], ("; delta desde a pausa: " + "; ".join(delta)) if delta else "")]
    if c == "spend":
        return cmd_spend(root, actor, a)
    if c == "report":
        rep = cmd_report(root)
        return [json.dumps(rep, ensure_ascii=False)] if a.json else [j5.dumps(rep)]
    return None


def main(argv=None):
    ap = build_parser()
    a, extras = ap.parse_known_args(argv)
    if not a.cmd:
        ap.print_help(sys.stderr)
        return 2
    if extras and a.cmd in ("approve", "senha", "conferir"):
        # sem eco dos extras: podem conter a senha; ela nunca vai por argumento (só digitada no terminal)
        ap.error("%s não aceita argumentos extras (%d recusados): a senha só é digitada no terminal" % (
            a.cmd, len(extras)))
    if extras and a.cmd not in PROOF_CMDS:
        ap.error("argumentos não reconhecidos: %s" % " ".join(extras))
    try:
        out = run(a, extras)
    except Syntax as e:
        sys.stderr.write("cs-auto: %s\n" % e)
        return 2
    except Refused as e:
        sys.stderr.write(e.render() + "\n")
        return 1
    except StateError as e:
        sys.stderr.write("cs-auto: ESTADO: %s\n" % e)
        return 2
    if out is None:
        ap.print_help(sys.stderr)
        return 2
    print("\n".join(x for x in out if x))
    return 0


if __name__ == "__main__":
    import auto as _self  # um só módulo `auto` (engine importa `auto` para as guardas M5)
    sys.exit(_self.main())
