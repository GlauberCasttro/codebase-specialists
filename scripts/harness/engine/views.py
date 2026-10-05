"""views — `cs-state next` (≤10 linhas), `why <id>`, `board` (árvore com rollup), `status`."""
import hcore
import engine
from engine import latest_deleg


RUNNING_GUARDS = {"feature_dor", "feature_dod", "story_dor", "story_dod"}


def _gate_for(ctx, author):
    gs = sorted(g for g in hcore.gate_agents(ctx.team) if g != author) if ctx.team else []
    return gs[0] if gs else "<gate>"


def _specialist_for(ctx, author, asked, requests):
    """Gate citado nos achados do NEEDS_SPECIALIST; senão `security` se existir; senão outro gate."""
    gates = sorted(g for g in (hcore.gate_agents(ctx.team) if ctx.team else set()) if g != author and g not in asked)
    text = " ".join(str(r.get("findings") or "") for _, r in requests).lower()
    for g in gates:
        if g.lower() in text:
            return g
    if "security" in gates:
        return "security"
    return gates[0] if gates else "<especialista>"


LANE_HINT = {
    "consulta": "faixa CONSULTA (só leitura): cs-state ask <agente> \"<pergunta>\" [--paths <glob>] → Agent com o id ASK-n",
    "avulsa": "faixa AVULSA: cs-state add task --quick --agent <a> --title ... --allowed-path <arq> --verify-cmd \"<cmd>\"",
    "completo": "faixa COMPLETA: épico → feature → story READY → cs-state add task --story <US-n> ... --ready",
}


def lane_line(ctx, klass):
    lane = engine.lane_of(ctx, klass)
    return LANE_HINT.get(lane) if lane else None


def env_exits(tid, tools=()):
    """Saídas de um verify que falhou por AMBIENTE (ferramenta/módulo ausente)."""
    miss = ", ".join(tools) or "ferramenta"
    return ["reverificar (depois de instalar %s): cs-state reverify --task %s" % (miss, tid),
            "exceção de ambiente (o HUMANO roda no terminal dele): cs-state waive-verify --task %s --reason '<por que>' "
            "--by <humano> --evidence '<saída do verify com %s ausente>'" % (tid, miss)]


def _env_failure(ctx, t):
    try:
        fk, tools = engine.verify_failure(ctx, t)
    except Exception:
        return None
    return tools if fk == "environment" else None


def waiver_line(t):
    w = engine.current_waiver(t)
    if not w:
        return None
    return "verify DISPENSADO por ambiente (%s ausente) — por %s: %s" % (", ".join(w.get("missing_tools") or []) or "?",
                                                                      w.get("by"), (w.get("reason") or "")[:120])


def exits_for(ctx, t, st):
    """Saídas de uma delegação ESCALATED/ABSTAINED: as de ambiente (se o verify falhou por ambiente) + as três humanas."""
    env = _env_failure(ctx, t) if st == "ESCALATED" else None
    return (env_exits(t["id"], env) if env is not None else []) + human_exits(t["id"], st == "ABSTAINED")


def human_exits(tid, abstained=False):
    """As três saídas de uma delegação que espera decisão humana (ESCALATED/ABSTAINED), com o comando pronto."""
    first = ("retomar (corrija o brief com cs-state amend se preciso): cs-state retry --task %s --decision '<decisão do humano>'"
             if abstained else "retomar: cs-state retry --task %s --decision '<decisão do humano>'") % tid
    return [first,
            "trocar de agente: cs-state reroute --task %s --agent <outro> --decision '<decisão do humano>' "
            "[--allowed-path <glob>]" % tid,
            "descartar: cs-state drop --task %s --reason '<por que descartar>'" % tid]


def next_for(ctx, kind, ent):
    """Próximo comando para uma entidade (1 linha)."""
    if kind == "consult":
        if ent["state"] == "BRIEFED":
            m = (ent.get("route") or {}).get("model") or "sonnet"
            return "Agent(subagent_type=%r, model=%r, description='%s: %s')" % (
                ent["agent"], m, ent["id"], " ".join(ent.get("question", "").split())[:60])
        if ent["state"] == "DISPATCHED":
            return "aguarde a resposta de %s (%s, só leitura); fecha sozinha ao terminar" % (ent["id"], ent["agent"])
        return None
    if kind == "deleg":
        t = hcore.task_of_deleg(ctx.board, ent["id"])
        st = ent["state"]
        tid = t["id"]
        if st == "PLANNED":
            return "cs-state ready --task %s" % tid
        if st == "BRIEFED":
            m = (ent.get("route_override") or {}).get("model") or (ent.get("route") or {}).get("model") or "<model>"
            return "Agent(subagent_type=%r, model=%r, description='%s: %s')" % (ent["agent"], m, ent["id"], t["title"][:40])
        if st == "DISPATCHED" and not ent.get("tool_use_id"):
            return ("despacho FANTASMA (DISPATCHED sem tool_use_id: nenhum subagente foi lançado) → cs-state return --task %s "
                    "--reason 'despacho fantasma' e depois cs-state retry --task %s --findings '...' (devolve a tentativa); "
                    "depois despache pela ferramenta Agent" % (tid, tid))
        if st == "DISPATCHED":
            return "aguarde o retorno de %s (subagente %s); sem submission → cs-state return --task %s" % (ent["id"], ent["agent"], tid)
        if st == "RETURNED":
            return "cs-state verify --task %s" % tid
        if st in ("VERIFIED", "REVIEWED"):
            probs = engine.GUARDS["reviews_satisfy_class"](ctx, "deleg", ent, {})
            wl = waiver_line(t)
            pre = "[%s] " % wl if wl else ""
            if not probs:
                return pre + "cs-state accept --task %s" % tid
            outcome = engine.review_outcome(t)
            if outcome == "FAIL":
                return "cs-state reject --task %s --reason '<achados do FAIL>' (qualquer FAIL vence)" % tid
            if outcome == "NEEDS_SPECIALIST":
                asked = set(b for b, _ in engine.open_specialist_requests(t))
                spec = _specialist_for(ctx, ent["agent"], asked, engine.open_specialist_requests(t))
                return ("NEEDS_SPECIALIST: Agent(subagent_type=%r, description='%s: review') → cs-state review --task %s "
                        "--by %s --verdict PASS|FAIL --findings ..." % (spec, ent["id"], tid, spec))
            return pre + "Agent(subagent_type=%r, description='%s: review') → cs-state review --task %s --by <gate> --verdict PASS|FAIL|NEEDS_SPECIALIST --findings ..." % (
                _gate_for(ctx, ent["agent"]), ent["id"], tid)
        if st == "REJECTED":
            env = _env_failure(ctx, t)
            if env is not None:
                return "verify falhou por AMBIENTE (%s ausente), não por código → %s" % (
                    ", ".join(env) or "?", " | ".join(x.split(": ", 1)[1] for x in env_exits(tid, env)))
            if t["status"] == "BLOCKED":
                return "cs-state escalate --task %s --reason ... | cs-state reroute --task %s --agent <outro> --reason ..." % (tid, tid)
            return "cs-state retry --task %s --findings '<achados>'" % tid
        if st in ("ESCALATED", "ABSTAINED"):
            return "%s: aguarda decisão do humano → %s" % (
                st, " | ".join(x.split(": ", 1)[1] for x in exits_for(ctx, t, st)))
        if st == "REROUTED":
            return "cs-state ready --task %s" % tid
        return None
    if kind == "session":
        s = ent
        if s["state"] == "TRIAGE":
            if not s.get("class"):
                return "cs-state session triage --class pergunta|trivial|pequena|feature|risco --why '<critério>'"
            lane = engine.lane_of(ctx, s["class"])
            if lane == "consulta":
                return "cs-state ask <agente> \"<pergunta>\" (opcional) ; depois cs-state session answer"
            if lane == "avulsa":
                return ("cs-state add task --quick --agent <a> --title ... --allowed-path <arq> --verify-cmd \"<cmd>\" "
                        "(planeja e prepara o brief)")
            return "cs-state session plan"
        if s["state"] == "PLANNING":
            if engine.lane_of(ctx, s.get("class")) == "avulsa":
                return "cs-state add task --quick ... (se faltar) ; depois cs-state session execute"
            return "cs-state add task --story <US-n> --agent <a> ... ; depois cs-state session execute"
        if s["state"] == "EXECUTING":
            return "cs-state session verify"
        if s["state"] == "VERIFYING":
            c = ctx.cls(s.get("class"))
            if c.get("final_review") and not any(r["verdict"] == "PASS" for r in s.get("reviews") or []):
                return "cs-state session review --by %s --verdict PASS --findings '...'" % _gate_for(ctx, None)
            return "cs-state session report"
        if s["state"] == "REPORTING":
            return "relate ao usuário e cs-state session close"
    return None


def next_lines(ctx):
    import autonomy
    L = []
    m = autonomy.load(ctx.root)
    if m and m.get("state") == "ESCALATED":
        e = m.get("escalation") or {}
        return ["ESCALADO (%s): leve ao usuário com o pacote de evidência" % e.get("condition"),
                "cs-state autonomy status ; cs-state autonomy report",
                "retomar: cs-state autonomy resume --decision '<decisão do humano>'",
                "encerrar: cs-state autonomy stop --reason '<motivo>'"]
    sess = [s for s in ctx.board["sessions"] if s["state"] != "IDLE"]
    if not sess:
        return ["sem sessão ativa → cs-state session start --request '<pedido do usuário>'"]
    s = sess[-1]
    L.append("sessão %s [%s] classe=%s" % (s["id"], s["state"], s.get("class") or "?"))
    lh = lane_line(ctx, s.get("class"))
    if lh:
        L.append(lh)
    for c in ctx.board.get("consults") or []:
        if c.get("session") == s["id"] and c["state"] in ("BRIEFED", "DISPATCHED"):
            L.append(next_for(ctx, "consult", c))
    if s["state"] in ("EXECUTING", "PLANNING"):
        ts = [t for t in ctx.board["tasks"] if t.get("session") == s["id"]]
        order = {"RETURNED": 0, "VERIFIED": 1, "REVIEWED": 1, "REJECTED": 2, "PLANNED": 3, "BRIEFED": 4, "ABSTAINED": 5,
                 "ESCALATED": 5, "DISPATCHED": 6}
        cands = []
        for t in ts:
            d = latest_deleg(t)
            if d and d["state"] in order:
                cands.append((order[d["state"]], t.get("wave", 1), t["id"], d))
        cands.sort(key=lambda x: x[:3])
        for _, _, tid, d in cands:
            if d["state"] == "BRIEFED" and s["state"] == "EXECUTING":
                _, probs = engine.evaluate(ctx, "deleg", d, "dispatch", {"model": "x"})
                probs = [p for p in probs if not p.startswith("model=") and "sem model" not in p]
                if probs:
                    L.append("%s não despacha: %s" % (d["id"], probs[0]))
                    continue
            if d["state"] == "BRIEFED" and s["state"] == "PLANNING":
                continue
            if d["state"] in ("ESCALATED", "ABSTAINED"):
                L.append("%s %s: aguarda decisão do humano; saídas:" % (d["id"], d["state"]))
                L += ["  " + x for x in exits_for(ctx, ctx.find("task", tid), d["state"])]
                if len(L) >= 7:
                    break
                continue
            n = next_for(ctx, "deleg", d)
            if n:
                L.append(n)
            if len(L) >= 7:
                break
        if s["state"] == "PLANNING" or len(L) <= 2:
            L.append(next_for(ctx, "session", s))
    else:
        L.append(next_for(ctx, "session", s))
    return [x for x in L if x][:10]


def why(ctx, ident):
    kind = hcore.kind_of(ctx.board, ident)
    if kind is None:
        return "%s: não encontrado no board" % ident
    ent = ctx.find(kind, ident)
    if kind == "task":
        d = latest_deleg(ent)
        lines = ["task %s: status %s, tentativas %d, agente %s" % (ident, ent["status"], ent["attempts"], ent["agent"])]
        if ent.get("reject_reason"):
            lines.append("último motivo: %s" % ent["reject_reason"][:300])
        fk = (ent.get("gate_report") or {}).get("failure_kind")
        if fk:
            lines.append("falha do último verify: %s%s" % (fk, " (%s ausente)" % ", ".join(
                (ent.get("gate_report") or {}).get("missing_tools") or []) if fk == "environment" else ""))
        wl = waiver_line(ent)
        if wl:
            lines.append(wl)
        if d:
            lines.append(why(ctx, d["id"]))
        lines.append(_history(ctx, ident))
        return "\n".join(lines)
    mname = hcore.KIND_MACHINE[kind]
    m = ctx.M["machines"][mname]
    cur = ent.get(m.get("field", "state"))
    lines = ["%s %s: estado %s" % (mname, ident, cur)]
    for tname, t in (m.get("transitions") or {}).items():
        if cur not in t["from"]:
            continue
        if tname == "verify" or set(t.get("guards") or []) & RUNNING_GUARDS:
            lines.append("  %-9s → %s  (executa verification_command + ACs test: + git diff × allowed_paths)" % (tname, t["to"]))
            continue
        try:
            to, probs = engine.evaluate(ctx, kind, ent, tname, {"_why": True})
        except hcore.Refused as e:
            probs, to = e.problems, None
        arg_only = [p for p in probs if p.startswith("--") or "obrigatório" in p or "sem model" in p or "deve ser" in p]
        real = [p for p in probs if p not in arg_only]
        mark = "OK" if not real else "X"
        lines.append("  %-9s → %-10s [%s] %s" % (tname, t["to"], mark, "; ".join(real)[:240] if real else
                                                 ("(exige %s)" % ", ".join(sorted(set(p.split()[0] for p in arg_only))) if arg_only else "")))
    if kind == "deleg" and cur in ("ESCALATED", "ABSTAINED"):
        t_ = hcore.task_of_deleg(ctx.board, ident)
        env = _env_failure(ctx, t_) if cur == "ESCALATED" else None
        if env is not None:
            lines.append("o último verify falhou por AMBIENTE (%s ausente), não por código" % (", ".join(env) or "?"))
        lines.append("aguarda decisão do humano; saídas:")
        lines += ["  " + x for x in exits_for(ctx, t_, cur)]
        return "\n".join(lines)
    n = next_for(ctx, kind, ent)
    if n:
        lines.append("próximo: " + n)
    return "\n".join(lines)


def _history(ctx, ident):
    """status_history derivado de events.jsonl (fonte única)."""
    recs, _, _ = hcore.read_chain(ctx.paths["events"])
    hist = []
    for r in recs:
        for op in r.get("ops") or []:
            if op[0] == "set" and op[2] in ("status", "state") and op[1].split(":", 1)[1] in (ident,) :
                hist.append("%s %s→%s" % (r["at"][:19], r["type"], op[3]))
            elif op[0] == "set" and op[2] in ("status", "state") and op[1].startswith("deleg:%s." % ident):
                hist.append("%s %s→%s" % (r["at"][:19], r["type"], op[3]))
    return "histórico: " + (" | ".join(hist[-8:]) or "(vazio)")


def _pct(items, done=("DONE",)):
    if not items:
        return "—"
    return "%d%%" % round(100.0 * sum(1 for i in items if i["state"] in done) / len(items))


def board_tree(ctx):
    b = ctx.board
    L = []
    for e in b["epics"]:
        fs = [f for f in b["features"] if f.get("epic") == e["id"]]
        L.append("%s [%s] %s — features DONE %s" % (e["id"], e["state"], e.get("title", ""), _pct(fs, ("DONE", "DROPPED"))))
        for f in fs:
            ss = [s for s in b["stories"] if s.get("feature") == f["id"]]
            L.append("  %s [%s] %s — stories DONE %s" % (f["id"], f["state"], f.get("title", ""), _pct(ss)))
            for s in ss:
                ts = [t for t in b["tasks"] if t.get("story") == s["id"]]
                acc = sum(1 for t in ts if t["status"] == "ACCEPTED")
                blk = [t["id"] for t in ts if t["status"] == "BLOCKED"]
                L.append("    %s [%s] %s — tasks %d/%d%s" % (s["id"], s["state"], s.get("title", "")[:60], acc, len(ts),
                                                          (" BLOQUEADAS: " + ",".join(blk)) if blk else ""))
                for t in ts:
                    d = latest_deleg(t)
                    L.append("      %s [%s/%s] %s (%s, tent.%d)" % (t["id"], t["status"], (d or {}).get("state"), t["title"][:50],
                                                                   t["agent"], t["attempts"]))
    for sp in b["sprints"]:
        ss = [ctx.find("story", s) for s in sp.get("stories") or []]
        ss = [s for s in ss if s]
        ts = [t for t in b["tasks"] if t.get("story") in (sp.get("stories") or [])]
        bud = sp.get("budget") or {}
        L.append("%s [%s] meta: %s — stories DONE %s; orçamento tasks %d/%s, tentativas %d/%s" % (
            sp["id"], sp["state"], sp.get("goal", ""), _pct(ss), sum(1 for t in ts if t["attempts"]), bud.get("tasks", "?"),
            sum(t["attempts"] for t in ts), bud.get("attempts", "?")))
    quick = [t for t in b["tasks"] if t.get("quick")]
    for sid in sorted({t["story"] for t in quick}):
        ts = [t for t in quick if t["story"] == sid]
        L.append("%s (implícita, faixa avulsa) — tasks %d/%d" % (sid, sum(1 for t in ts if t["status"] == "ACCEPTED"), len(ts)))
        for t in ts:
            d = latest_deleg(t)
            L.append("  %s [%s/%s] %s %s (%s, tent.%d)" % (t["id"], t["status"], (d or {}).get("state"), t.get("work_type", "US"),
                                                           t["title"][:50], t["agent"], t["attempts"]))
    for c in b.get("consults") or []:
        L.append("%s [%s] consulta a %s: %s" % (c["id"], c["state"], c["agent"], c.get("question", "")[:60]))
    orphans = [t for t in b["tasks"] if not t.get("quick") and not ctx.find("story", t.get("story") or "")]
    if orphans:
        L.append("tasks sem story: %s" % ", ".join(t["id"] for t in orphans))
    return "\n".join(L) or "(board vazio)"


def status(ctx, tid=None):
    if tid:
        return why(ctx, tid)
    by = {}
    for t in ctx.board["tasks"]:
        by.setdefault(t["status"], []).append(t["id"])
    L = ["eventos: %d  último hash: %s" % (ctx.board["event_count"], ctx.board["last_event_hash"][:12])]
    for k in hcore.machines()["machines"]["task"]["states"]:
        if by.get(k):
            L.append("%-11s %s" % (k, ", ".join(by[k])))
    return "\n".join(L)
