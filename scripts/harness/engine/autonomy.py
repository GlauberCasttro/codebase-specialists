"""autonomy — modo autônomo (ARCHITECTURE §8-sexies): mandato assinado, hook Stop, escalada, relatório.

state/autonomy.json5 guarda o mandato + assinatura sha256 (também gravada como evento autonomy.start
em events.jsonl, então editar o arquivo à mão é detectado pelo validador).
"""
import os
import time

import hcore
import j5

TRAINABLE = None


def path(root):
    return hcore.state_paths(root)["autonomy"]


def load(root):
    p = path(root)
    if not os.path.isfile(p):
        return None
    return j5.load(p)


def save(root, m):
    hcore.write_json5(path(root), m, "autonomy.json5 — mandato do modo autônomo; escrito só por cs-state autonomy")


def signature(m):
    core = {k: m.get(k) for k in ("target", "spec", "spec_sha256", "acceptance", "acceptance_files_sha", "class",
                                   "budget", "started_at", "approved_by")}
    return hcore.sha256_bytes(hcore.canonical(core).encode("utf-8"))


def active(root):
    m = load(root)
    return m if m and m.get("state") == "ACTIVE" else None


def parse_budget(s):
    out = {}
    if (s or "").strip().isdigit():
        return {"tasks": int(s)}
    for part in (s or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = float(v) if k.strip() == "usd" else int(v)
    return out


def start(root, actor, target, budget, spec=None, accept_cmds=None, accept_files=None, klass=None, approved_by="user"):
    import engine
    board = hcore.load_board(root)
    ctx = engine.Ctx(root, board, actor)
    if active(root):
        raise hcore.Refused("já existe mandato ACTIVE: cs-state autonomy stop antes")
    ent = ctx.find("feature", target) or ctx.find("story", target)
    if ent is None:
        raise hcore.Refused("--feature/--story %s inexistente (mandato é por Feature ou Story)" % target)
    if target.startswith("FEAT"):
        spec = spec or ent.get("spec")
        accept_cmds = accept_cmds or ent.get("acceptance") or []
        accept_files = accept_files or ent.get("acceptance_files") or []
        if ent["state"] not in ("READY", "IN_PROGRESS"):
            raise hcore.Refused("feature %s em %s: DoR primeiro (cs-state feature ready --id %s)" % (target, ent["state"], target))
    else:
        accept_cmds = accept_cmds or [engine.resolve_test(ctx.cfg, t) for t in engine.story_tests(ent)]
    P = []
    if not spec or not os.path.isfile(os.path.join(root, spec)):
        P.append("spec inexistente: %r" % spec)
    if not accept_cmds:
        P.append("sem critérios de aceite executáveis")
    for f in accept_files or []:
        if not os.path.isfile(os.path.join(root, f)):
            P.append("teste de aceite inexistente: %s" % f)
    klass = klass or "feature"
    if klass == "risco":
        P.append("classe risco não roda em modo autônomo (exige confirmação do usuário a cada passo)")
    for k in ("tasks", "attempts", "minutes"):
        if k not in budget:
            P.append("--budget sem %s (ex.: tasks=6,attempts=2,minutes=90[,usd=5])" % k)
    if P:
        raise hcore.Refused(P)
    runs = [engine.run_cmd(root, c, int(ctx.cfg.get("verify_timeout_s", 900))) for c in accept_cmds]
    green = [r["cmd"] for r in runs if r["exit_code"] == 0]
    missing = [r["cmd"] for r in runs if r["exit_code"] == 127]
    if missing:
        raise hcore.Refused("teste de aceite não executável: %s" % ", ".join(missing))
    if green:
        raise hcore.Refused("teste de aceite já passa hoje (%s): não há o que entregar ou o teste não prova a feature" % ", ".join(green))
    m = {"state": "ACTIVE", "mode": "autonomo", "target": target, "spec": spec,
         "spec_sha256": hcore.sha256_file(os.path.join(root, spec)), "acceptance": list(accept_cmds),
         "acceptance_files_sha": {f: hcore.sha256_file(os.path.join(root, f)) for f in accept_files or []},
         "class": klass, "budget": budget, "started_at": hcore.now_iso(), "started_ts": time.time(),
         "approved_by": approved_by, "baseline": [{"cmd": r["cmd"], "exit_code": r["exit_code"],
                                                  "output_sha256": r["output_sha256"]} for r in runs],
         "counters": {"stop_blocks": 0, "noprogress": 0, "last_event_count": board["event_count"]},
         "spent": {"usd": 0.0}, "escalation": None}
    m["signature"] = signature(m)

    def build(c2):
        return [engine.Event("autonomy.start", target, [], {"args": {"signature": m["signature"], "budget": budget,
                                                                      "class": klass, "target": target}})]
    engine.commit(root, actor, build)
    save(root, m)
    hcore.ledger_append(root, {"kind": "autonomy", "event": "start", "target": target, "signature": m["signature"]})
    return m


def scope_tasks(board, m):
    tgt = m["target"]
    if tgt.startswith("FEAT"):
        stories = {s["id"] for s in board["stories"] if s.get("feature") == tgt}
    else:
        stories = {tgt}
    return [t for t in board["tasks"] if t.get("story") in stories]


def budget_problems(ctx):
    m = active(ctx.root)
    if not m:
        return []
    b = m.get("budget") or {}
    P = []
    ts = scope_tasks(ctx.board, m)
    dispatched = [t for t in ts if t.get("attempts", 0) > 0]
    if "tasks" in b and len(dispatched) >= int(b["tasks"]):
        P.append("orçamento de tasks esgotado (%d/%d)" % (len(dispatched), b["tasks"]))
    if "minutes" in b and (time.time() - m.get("started_ts", time.time())) / 60.0 > float(b["minutes"]):
        P.append("orçamento de minutos esgotado (%s min)" % b["minutes"])
    if "usd" in b and float((m.get("spent") or {}).get("usd", 0)) >= float(b["usd"]):
        P.append("orçamento em USD esgotado")
    return P


def retry_cap(ctx, mx):
    m = active(ctx.root)
    if m and "attempts" in (m.get("budget") or {}):
        return min(mx, int(m["budget"]["attempts"]))
    return mx


def _jacc(a, b):
    import re
    ta = set(re.findall(r"[a-z0-9_]{3,}", (a or "").lower()))
    tb = set(re.findall(r"[a-z0-9_]{3,}", (b or "").lower()))
    return len(ta & tb) / float(len(ta | tb)) if ta and tb else 0.0


def detect_escalation(root, board, m, ctx=None):
    """(condição, evidência) ou None."""
    import engine
    ctx = ctx or engine.Ctx(root, board)
    acked = set(m.get("acknowledged") or [])
    for cond, ev in _conditions(root, board, m, ctx, scope_tasks(board, m)):
        if escalation_key(cond, ev) not in acked:  # condição já decidida pelo humano (resume) não reescala
            return cond, ev
    return None


def escalation_key(cond, evidence):
    """Impressão digital (condição + evidência) de uma escalada: a decisão humana do `resume` a reconhece."""
    return hcore.sha256_bytes(hcore.canonical({"condition": cond, "evidence": evidence}).encode("utf-8"))


def _conditions(root, board, m, ctx, ts):
    """Gera (condição, evidência) na ordem de precedência."""
    import engine
    frozen = ctx.cfg.get("frozen_paths") or []
    for t in ts:
        if t["status"] in ("ACCEPTED", "DROPPED"):
            continue
        inv = engine.scoped_invariants(t)
        if inv:
            yield "invariant_or_frozen_touched", {"task": t["id"], "invariants": [i["id"] for i in inv]}
        if frozen and hcore.scopes_overlap(t["allowed_paths"], frozen):
            yield "invariant_or_frozen_touched", {"task": t["id"], "frozen": frozen}
    for t in ts:
        for a in t.get("abstentions") or []:
            if a.get("kind") == "spec_ambiguous":
                yield "material_ambiguity", {"task": t["id"], "reason": a.get("reason")}
    recs, _, _ = hcore.read_chain(hcore.state_paths(root)["events"])
    ids = {t["id"] for t in ts}
    reasons = {}
    for r in recs:
        if r.get("type") in ("delegation.reject", "delegation.verify", "delegation.return"):
            t = hcore.task_of_deleg(board, r.get("entity"))
            if not t or t["id"] not in ids:
                continue
            args = (r.get("data") or {}).get("args") or {}
            txt = args.get("reason") or "; ".join((r.get("data") or {}).get("problems") or [])
            if txt:
                reasons.setdefault(t["id"], []).append(txt)
    for tid, rs in reasons.items():
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                if _jacc(rs[i], rs[j]) >= 0.5:
                    yield "same_rejection_twice", {"task": tid, "reasons": [rs[i][:300], rs[j][:300]]}
    bp = budget_problems(ctx)
    if bp:
        yield "budget_exhausted", {"problems": bp}
    for s in board["sessions"]:
        if s["state"] != "IDLE" and s.get("class") == "risco":
            yield "risk_class_discovered", {"session": s["id"]}
    for f, sha in (m.get("acceptance_files_sha") or {}).items():
        full = os.path.join(root, f)
        if not os.path.isfile(full) or hcore.sha256_file(full) != sha:
            yield "acceptance_test_changed", {"file": f}
    for t in ts:
        att = t.get("attempts")
        cur = [r for r in t.get("reviews") or [] if r.get("attempt") == att]
        # precedência (engine.review_outcome): PASS×FAIL não é conflito (FAIL vence → retry); NEEDS_SPECIALIST
        # só escala quando não há outro gate para quem rotear.
        req = engine.open_specialist_requests(t) if cur else []
        others = set(hcore.gate_agents(ctx.team) if ctx.team else set()) - set(b for b, _ in req)
        if req and not others:
            yield "agent_conflict", {"task": t["id"], "reviews": [{"by": r["by"], "verdict": r["verdict"]} for r in cur]}


def escalate(root, m, cond, evidence):
    m["state"] = "ESCALATED"
    pack = {"condition": cond, "at": hcore.now_iso(), "evidence": evidence, "target": m["target"]}
    try:
        recs, _, _ = hcore.read_chain(hcore.state_paths(root)["events"])
        pack["events_tail"] = [{"seq": r["seq"], "type": r["type"], "entity": r.get("entity")} for r in recs[-10:]]
    except Exception:
        pass
    m["escalation"] = pack
    save(root, m)
    p = os.path.join(hcore.state_paths(root)["state_dir"], "escalation-%s.json5" % pack["at"].replace(":", "").replace(".", ""))
    hcore.write_json5(p, pack, "pacote de evidência de escalada do modo autônomo")
    hcore.ledger_append(root, {"kind": "autonomy", "event": "escalated", "condition": cond})
    return pack


def has_work(board, m):
    import engine
    ts = scope_tasks(board, m)
    for t in ts:
        d = engine.latest_deleg(t)
        if d and d["state"] in ("PLANNED", "BRIEFED", "RETURNED", "VERIFIED", "REVIEWED", "DISPATCHED"):
            return True
        if d and d["state"] == "REJECTED" and t["status"] != "BLOCKED":
            return True
    return False


def stop_decision(root, payload):
    """(block, reason). Bloqueia a parada só quando o loop deve continuar."""
    m = active(root)
    if not m:
        return False, None
    board = hcore.load_board(root)
    sess = [s for s in board["sessions"] if s["state"] != "IDLE"]
    if not sess or sess[-1]["state"] not in ("EXECUTING", "VERIFYING"):
        return False, None
    esc = detect_escalation(root, board, m)
    if esc:
        escalate(root, m, esc[0], esc[1])
        return False, None
    if not has_work(board, m) and sess[-1]["state"] != "VERIFYING":
        return False, None
    c = m.setdefault("counters", {"stop_blocks": 0, "noprogress": 0, "last_event_count": 0})
    mac = hcore.machines()["autonomy"]
    if board["event_count"] == c.get("last_event_count"):
        c["noprogress"] = int(c.get("noprogress", 0)) + 1
    else:
        c["noprogress"] = 0
    c["last_event_count"] = board["event_count"]
    c["stop_blocks"] = int(c.get("stop_blocks", 0)) + 1
    if c["noprogress"] >= mac["max_blocks_without_progress"]:
        escalate(root, m, "no_progress", {"stop_blocks": c["stop_blocks"], "event_count": board["event_count"]})
        return False, None
    if c["stop_blocks"] > mac["max_stop_blocks"]:
        escalate(root, m, "no_progress", {"reason": "teto de bloqueios de parada", "stop_blocks": c["stop_blocks"]})
        return False, None
    save(root, m)
    import engine
    import views
    nxt = views.next_lines(engine.Ctx(root, board))
    return True, "continue: cs-state next → " + (nxt[0] if nxt else "")


def checkpoint(root, rec):
    if not active(root):
        return
    import session
    session.save(root, did="delegação %s ACCEPTED" % rec["entity"], next_="cs-state next", auto=True)


def _machine_check(m, tname):
    t = (hcore.machines().get("autonomy") or {}).get("transitions", {}).get(tname)
    if t and m.get("state") not in t["from"]:
        raise hcore.Refused("mandato em %s: autonomy %s só sai de %s" % (m.get("state"), tname, "|".join(t["from"])))


def resume(root, actor, decision):
    """ESCALATED → ACTIVE com a decisão do humano. A condição escalada fica reconhecida (não reescala pela mesma
    evidência); contadores de progresso zeram. Nova condição (outra evidência) volta a escalar."""
    m = load(root)
    if not m:
        raise hcore.Refused("sem mandato")
    if not (decision or "").strip():
        raise hcore.Refused("--decision obrigatório: a decisão do humano que destrava a escalada")
    _machine_check(m, "resume")
    import engine
    esc = m.get("escalation") or {}
    rec = {"at": hcore.now_iso(), "by": actor, "decision": decision.strip(), "condition": esc.get("condition")}
    k = escalation_key(esc["condition"], esc.get("evidence")) if esc.get("condition") else None
    if k:
        m.setdefault("acknowledged", [])
        if k not in m["acknowledged"]:
            m["acknowledged"].append(k)

    def build(ctx):  # a decisão entra na cadeia de eventos: o validador confere `acknowledged` contra ela
        return [engine.Event("autonomy.resume", m["target"], [], {"args": {"signature": m["signature"], "ack": k,
                                                                           "condition": rec["condition"],
                                                                           "decision": rec["decision"]}})]
    engine.commit(root, actor, build)
    m.setdefault("decisions", []).append(rec)
    m.setdefault("escalations", []).append(esc)
    m["escalation"] = None
    m["state"] = "ACTIVE"
    m["mode"] = "autonomo"
    board = hcore.load_board(root)
    m["counters"] = {"stop_blocks": 0, "noprogress": 0, "last_event_count": board["event_count"]}
    save(root, m)
    hcore.ledger_append(root, {"kind": "autonomy", "event": "resume", "condition": rec["condition"],
                               "decision": rec["decision"][:300]})
    return m


def stop(root, actor, reason="parado pelo usuário"):
    m = load(root)
    if not m:
        raise hcore.Refused("sem mandato")
    if m["state"] in ("ACTIVE", "ESCALATED"):
        m["state"] = "STOPPED"
        m["stop_reason"] = reason
    m["mode"] = "assistido"
    save(root, m)
    hcore.ledger_append(root, {"kind": "autonomy", "event": "stop", "reason": reason})
    return report(root)


def report(root):
    import engine
    m = load(root)
    if not m:
        raise hcore.Refused("sem mandato")
    board = hcore.load_board(root)
    ctx = engine.Ctx(root, board)
    ts = scope_tasks(board, m)
    after = [engine.run_cmd(root, c, int(ctx.cfg.get("verify_timeout_s", 900))) for c in m["acceptance"]]
    try:
        import router
        st = router.stats(root)
    except Exception:
        st = {}
    lessons = []
    try:
        import mem
        lessons = [r["id"] for r in mem.read_jsonl(mem.mem_paths(root)["knowledge"]) if (r.get("created_at") or "") >= m["started_at"][:19]]
    except Exception:
        pass
    rep = {"target": m["target"], "state": m["state"], "class": m["class"], "budget": m["budget"],
           "elapsed_min": round((time.time() - m.get("started_ts", time.time())) / 60.0, 1), "spent": m.get("spent"),
           "tasks": [{"id": t["id"], "status": t["status"], "attempts": t["attempts"],
                      "verify": (t.get("gate_report") or {}).get("build") and {k: t["gate_report"]["build"].get(k) for k in
                                                                               ("exit_code", "output_sha256", "tree_sha256")},
                      "verify_waiver": engine.current_waiver(t),
                      "reviews": [{"by": r["by"], "verdict": r["verdict"]} for r in t.get("reviews") or []]} for t in ts],
           "acceptance_before": m.get("baseline"),
           "acceptance_after": [{"cmd": r["cmd"], "exit_code": r["exit_code"], "output_sha256": r["output_sha256"]} for r in after],
           "escalation": m.get("escalation"), "router": {"distribution": st.get("distribution"),
                                                         "estimated_cost_avoided_vs_top": st.get("estimated_cost_avoided_vs_top")},
           "lessons": lessons, "at": hcore.now_iso()}
    if m["state"] == "ACTIVE" and all(r["exit_code"] == 0 for r in after) and any(t["status"] == "ACCEPTED" for t in ts) and \
            all(t["status"] in ("ACCEPTED", "DROPPED") for t in ts):
        m["state"] = "DONE"
        m["mode"] = "assistido"
        save(root, m)
        rep["state"] = "DONE"
    hcore.write_json5(os.path.join(hcore.state_paths(root)["state_dir"], "autonomy-report.json5"), rep,
                      "relatório final do modo autônomo (cs-state autonomy report)")
    return rep


def forbidden_write(root, rel):
    """Proibições do modo autônomo para escrita: teste de aceite aprovado e área congelada."""
    m = active(root)
    if not m:
        return None
    if rel in (m.get("acceptance_files_sha") or {}):
        return "modo autônomo: teste de aceite aprovado %s não pode ser alterado (escale)" % rel
    if m.get("spec") == rel:
        return "modo autônomo: spec aprovada não pode ser alterada"
    return None
