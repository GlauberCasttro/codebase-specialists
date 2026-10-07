"""cmds — comandos de cs-state (cada um monta eventos e passa por engine.commit)."""
import copy
import os
import re

import engine
import hcore
from engine import Event, Refused, ref, transition, latest_deleg
from hcore import StateError


def _now():
    return hcore.now_iso()


def _ctx_ro(root, actor="lead"):
    return engine.Ctx(root, hcore.load_board(root), actor)


def _task(ctx, tid):
    t = ctx.find("task", tid)
    if t is None:
        raise Refused("task %s inexistente (cs-state status lista as tasks)" % tid)
    return t


def _deleg(ctx, tid, states=None):
    """states: lista explícita OU nome de transição da delegação — aí os estados de origem vêm de machines.json5
    (fonte única; nada de lista duplicada no código)."""
    if isinstance(states, str):
        states = list(ctx.M["machines"]["delegation"]["transitions"][states]["from"])
    t = _task(ctx, tid)
    d = latest_deleg(t)
    if d is None:
        raise Refused("task %s sem delegação" % tid)
    if states and d["state"] not in states:
        raise Refused("delegação %s está em %s; esperado %s" % (d["id"], d["state"], "|".join(states)),
                      hint=engine.hint_for(ctx, "deleg", d))
    return t, d


def resolve_task_id(ctx, ident):
    """Aceita id de task ou de delegação."""
    if ctx.find("task", ident):
        return ident
    t = hcore.task_of_deleg(ctx.board, ident)
    if t:
        return t["id"]
    raise Refused("%s não é task nem delegação" % ident)


def _start_story_chain(ctx, prior, story):
    """story READY → IN_PROGRESS (story.start) e, havendo feature fora de IN_PROGRESS, feature.start — ambas pela
    transição da máquina (guardas avaliadas; parent_epic_active inclusive). Retorna os eventos; recusa propaga."""
    evs = []
    if story and story.get("state") == "READY":
        evs.append(engine.promote(ctx, prior, "story", story["id"], "start", {}))
    return evs + _start_feature_of(ctx, list(prior) + evs, story)


def _start_feature_of(ctx, prior, story):
    f = ctx.find("feature", (story or {}).get("feature") or "")
    if f and f["state"] != "IN_PROGRESS":
        if _legacy_hierarchy_acked(ctx, story, f):
            return []  # D-1-04: story legada reconhecida por legacy-ack — não promove a feature (seguiria recusada)
        return [engine.promote(ctx, prior, "feature", f["id"], "start", {})]
    return []


def _legacy_hierarchy_acked(ctx, story, feature):
    """story JÁ IN_PROGRESS (no board, antes deste comando) com feature fora de IN_PROGRESS, incoerência reconhecida
    por harness.legacy_ack e ainda vigente (engine.acked_hierarchy)."""
    cur = ctx.find("story", (story or {}).get("id") or "")
    if not cur or cur.get("state") != "IN_PROGRESS":
        return False
    key = ("story", cur["id"], "IN_PROGRESS", "feature", feature["id"], feature.get("state"))
    events, _, _ = hcore.read_chain(ctx.paths["events"])
    return key in engine.acked_hierarchy(events)


def _story_to_review(ctx, prior, task, need_accepted_other=False):
    """story IN_PROGRESS → IN_REVIEW (story.review, guarda story_tasks_accepted) quando a última task fecha."""
    st = ctx.find("story", task.get("story") or "")
    if not st or st["state"] != "IN_PROGRESS":
        return []
    others = [x for x in ctx.board["tasks"] if x.get("story") == st["id"] and x["id"] != task["id"]]
    if need_accepted_other and not (others and any(x["status"] == "ACCEPTED" for x in others)):
        return []
    if not all(x["status"] in ("ACCEPTED", "DROPPED") for x in others):
        return []
    return [engine.promote(ctx, prior, "story", st["id"], "review", {})]


def _block_if_exhausted(ctx, task, deleg, to):
    if to != "REJECTED":
        return []
    import autonomy
    cap = autonomy.retry_cap(ctx, int(ctx.M["limits"]["max_retries"]))
    if int(deleg.get("retries") or 0) >= cap:
        return [["set", ref("task", task["id"]), "status", "BLOCKED"],
                ["set", ref("task", task["id"]), "block_reason", "tentativas esgotadas (%d retries): escalar ou reroute" % cap]]
    return []


# ================================================================ processo
def add_epic(root, actor, title, objective, metric=None):
    def build(ctx):
        eid = engine.next_id(ctx.board, "epic", "EPIC")
        e = {"id": eid, "state": "PROPOSED", "title": title, "objective": objective, "metric": metric, "created_at": _now()}
        return [Event("epic.add", eid, [["create", "epic", None, e]])]
    return engine.commit(root, actor, build)


def add_feature(root, actor, epic, title, spec, accept_cmds, accept_files=None):
    def build(ctx):
        if not ctx.find("epic", epic):
            raise Refused("épico %s inexistente" % epic)
        fid = engine.next_id(ctx.board, "feature", "FEAT")
        f = {"id": fid, "state": "BACKLOG", "epic": epic, "title": title, "spec": spec, "acceptance": list(accept_cmds or []),
             "acceptance_files": list(accept_files or []), "created_at": _now()}
        return [Event("feature.add", fid, [["create", "feature", None, f]])]
    return engine.commit(root, actor, build)


def add_sprint(root, actor, goal, budget):
    def build(ctx):
        sid = engine.next_id(ctx.board, "sprint", "SPRINT", 2)
        s = {"id": sid, "state": "PLANNED", "goal": goal, "budget": budget, "stories": [], "created_at": _now()}
        return [Event("sprint.add", sid, [["create", "sprint", None, s]])]
    return engine.commit(root, actor, build)


def add_story(root, actor, stype, feature, title, **kw):
    if stype not in ("us", "bug", "fix"):
        raise Refused("--type deve ser us|bug|fix")

    def build(ctx):
        if not ctx.find("feature", feature):
            raise Refused("feature %s inexistente" % feature)
        if kw.get("reopens"):
            old = ctx.find("story", kw["reopens"])
            if stype != "bug" or not old or old["state"] != "DONE":
                raise Refused("reabrir exige story DONE e uma nova story --type bug")
        sid = engine.next_id(ctx.board, "story", stype.upper())
        s = {"id": sid, "type": stype, "state": "BACKLOG", "feature": feature, "title": title, "findings": [], "created_at": _now()}
        for k in ("as_a", "i_want", "so_that", "criteria", "repro", "failing_test", "severity", "environment", "fixes",
                  "proving_test", "regression", "reopens"):
            if kw.get(k) not in (None, [], ""):
                s[k] = kw[k]
        return [Event("story.add", sid, [["create", "story", None, s]])]
    return engine.commit(root, actor, build)


def level_transition(root, actor, kind, eid, tname, a=None):
    a = dict(a or {})

    def build(ctx):
        ent = ctx.find(kind, eid)
        extra = None
        if kind == "story" and tname == "requeue":
            def extra(to, probs):
                return [["append", ref("story", eid), "findings", {"at": _now(), "reason": a.get("reason")}]]
        if kind == "story" and tname == "reject":
            def extra(to, probs):
                return [["append", ref("story", eid), "findings", {"at": _now(), "reason": a.get("reason"), "rejected": True}]]
        if kind == "sprint" and tname == "plan":
            def extra(to, probs):
                cur = list(ent.get("stories") or [])
                return [["set", ref("sprint", eid), "stories", cur + [s for s in a.get("add") or [] if s not in cur]]]
        if kind == "sprint" and tname == "start":
            def extra(to, probs):
                return [["set", ref("sprint", eid), "started_at", _now()]]
        if kind == "sprint" and tname == "review":
            def extra(to, probs):
                delivered = [s for s in ent.get("stories") or [] if (ctx.find("story", s) or {}).get("state") == "DONE"]
                undone = [s for s in ent.get("stories") or [] if s not in delivered]
                ts = [t for t in ctx.board["tasks"] if t.get("sprint") == eid or t.get("story") in (ent.get("stories") or [])]
                metrics = {"stories": len(ent.get("stories") or []), "delivered": len(delivered),
                           "attempts": sum(t.get("attempts", 0) for t in ts),
                           "accepted_tasks": sum(1 for t in ts if t["status"] == "ACCEPTED")}
                return [["set", ref("sprint", eid), "review", {"at": _now(), "delivered": delivered,
                                                                "returned": [{"id": s, "reason": a.get("reason") or "não entregue no sprint"} for s in undone],
                                                                "metrics": metrics}]]
        if kind in ("feature", "story") and a.get("_runs") is None:
            pass
        ev = transition(ctx, kind, eid, tname, a, extra)
        if a.get("_runs"):
            ev.data["runs"] = [{k: r[k] for k in ("cmd", "exit_code", "output_sha256", "duration_s")} for r in a["_runs"]]
        evs = [ev]
        if kind == "sprint" and tname == "close":
            for item in (ent.get("review") or {}).get("returned") or []:
                s = ctx.find("story", item["id"])
                if s and s["state"] not in ("BACKLOG", "DONE"):
                    if s["state"] == "REJECTED" or s["state"] in ("READY", "IN_PROGRESS", "IN_REVIEW"):
                        def rq_extra(to, probs, sid=s["id"], reason=item["reason"]):
                            return [["append", ref("story", sid), "findings", {"at": _now(), "reason": reason, "sprint": eid}]]
                        evs.append(engine.promote(ctx, evs, "story", s["id"], "requeue", {"reason": item["reason"]}, rq_extra))
        if kind == "story" and tname == "start":
            evs += _start_feature_of(ctx, evs, ent)
        return evs
    return engine.commit(root, actor, build)


# ================================================================ M1
def session_start(root, actor, request, mode="assistido"):
    def build(ctx):
        act = [s["id"] for s in ctx.board["sessions"] if s["state"] != "IDLE"]
        if act:
            raise Refused("já existe sessão ativa: %s (feche com cs-state session close)" % ", ".join(act))
        sid = engine.next_id(ctx.board, "session", "S")
        s = {"id": sid, "state": "TRIAGE", "request": request, "mode": mode, "class": None, "why": None,
             "assumptions": [], "confirmation": None, "reviews": [], "created_at": _now()}
        return [Event("session.start", sid, [["create", "session", None, s]])]
    return engine.commit(root, actor, build)


def active_session(ctx):
    for s in reversed(ctx.board["sessions"]):
        if s["state"] != "IDLE":
            return s
    return None


def session_cmd(root, actor, tname, a=None):
    a = dict(a or {})

    def build(ctx):
        s = active_session(ctx)
        if s is None:
            raise Refused("nenhuma sessão ativa", hint="cs-state session start --request '<pedido do usuário>'")

        def extra(to, probs):
            ops = []
            if tname == "triage":
                ops += [["set", ref("session", s["id"]), "class", a["class"]], ["set", ref("session", s["id"]), "why", a["why"]]]
                for x in a.get("assume") or []:
                    ops.append(["append", ref("session", s["id"]), "assumptions", x])
            if tname == "confirm":
                ops.append(["set", ref("session", s["id"]), "confirmation", {"note": a["note"], "at": _now()}])
            if tname == "review":
                ops.append(["append", ref("session", s["id"]), "reviews", {"by": a["by"], "verdict": a["verdict"],
                                                                         "findings": a["findings"], "at": _now()}])
            return ops
        return [transition(ctx, "session", s["id"], tname, a, extra)]
    return engine.commit(root, actor, build)


# ================================================================ tasks / M2
def _ac_list(items):
    out = []
    for i, it in enumerate(items or []):
        if isinstance(it, dict):
            out.append(it)
            continue
        parts = [p.strip() for p in it.split("|")]
        if len(parts) == 2:
            parts = ["AC-%d" % (i + 1)] + parts
        if len(parts) != 3:
            raise Refused("--ac deve ser 'AC-n|critério|verified_by' (verified_by: verification_command|test:<id>|reviewer)")
        out.append({"id": parts[0], "criterion": parts[1], "verified_by": parts[2]})
    return out


QUICK_LANE_CLASSES = ("trivial", "pequena")
WORK_TYPES = ("US", "BUG", "FIX")


def _quick_session(ctx, spec):
    """Faixa avulsa: só com sessão triada trivial|pequena; devolve a sessão."""
    sess = active_session(ctx)
    if sess is None:
        raise Refused("task avulsa (--quick) exige sessão triada como trivial|pequena",
                      hint="cs-state session start --request '<pedido>' ; cs-state session triage --class trivial|pequena --why ...")
    klass = sess.get("class")
    if klass not in QUICK_LANE_CLASSES:
        lane = engine.lane_of(ctx, klass)
        if lane == "consulta":
            msg = "sessão %s é classe pergunta (faixa consulta): sem escrita — use cs-state ask <agente> \"<pergunta>\"" % sess["id"]
        elif klass:
            msg = ("sessão %s é classe %s (fluxo completo): --quick só em trivial|pequena — use épico → feature → story → "
                   "cs-state add task --story <US-n>" % (sess["id"], klass))
        else:
            msg = "sessão %s sem classe: cs-state session triage --class trivial|pequena --why ..." % sess["id"]
        raise Refused(msg)
    if sess["state"] not in ("TRIAGE", "PLANNING", "EXECUTING"):
        raise Refused("sessão %s em %s: task avulsa só em TRIAGE|PLANNING|EXECUTING" % (sess["id"], sess["state"]))
    if spec.get("session") and spec["session"] != sess["id"]:
        raise Refused("--session %s ≠ sessão ativa %s" % (spec["session"], sess["id"]))
    return sess


def _quick_defaults(spec, sess):
    """--quick: story implícita da sessão; goal = título; AC padrão = verification_command. Brief continua exigindo
    allowed_paths e verification_command (território e prova não afrouxam)."""
    for k in ("story", "epic", "feature", "sprint"):
        if spec.get(k):
            raise Refused("--quick dispensa a hierarquia: não passe --%s (sem --quick para o fluxo completo)" % k)
    if not spec.get("allowed_paths"):
        raise Refused("--quick exige --allowed-path <arquivo> (território não afrouxa)")
    if not (spec.get("verification_command") or "").strip():
        raise Refused("--quick exige --verify-cmd \"<cmd>\" (prova executável não afrouxa)")
    spec["story"] = engine.AVULSA_PREFIX + sess["id"]
    spec["session"] = sess["id"]
    if not (spec.get("goal") or "").strip():
        spec["goal"] = spec.get("title") or ""
    if not spec.get("acceptance_criteria"):
        spec["acceptance_criteria"] = [{"id": "AC-1", "criterion": "%s — verification_command com exit 0" % (spec.get("title") or "task avulsa"),
                                        "verified_by": "verification_command"}]
    wt = (spec.get("work_type") or "US").upper()
    if wt not in WORK_TYPES:
        raise Refused("--work-type deve ser us|bug|fix")
    spec["work_type"] = wt


def add_task(root, actor, spec, ready=False):
    """spec: dict no formato de brief-schema.json5 (campos do brief; o motor preenche o resto).
    spec["quick"]=True → faixa avulsa (story implícita STORY-AVULSA-<sessão>, só em trivial|pequena, já BRIEFED)."""
    spec = copy.deepcopy(spec)
    quick = bool(spec.get("quick"))

    def build(ctx):
        pre = []
        if quick:
            sess = _quick_session(ctx, spec)
            _quick_defaults(spec, sess)
            probs = engine.quick_problems(ctx, sess, spec["agent"], spec["allowed_paths"])
            if probs:
                raise Refused(probs)
            story = {"id": spec["story"], "state": "IN_PROGRESS"}
            if sess["state"] == "TRIAGE":
                pre.append(transition(ctx, "session", sess["id"], "plan", {}))
        else:
            story = ctx.find("story", spec.get("story") or "")
            if not story:
                raise Refused("toda task pertence a uma Story: --story US-n|BUG-n|FIX-n",
                              hint="mudança pequena sem hierarquia: sessão trivial|pequena + cs-state add task --quick ...")
            if story["state"] in ("DONE", "REJECTED", "BACKLOG"):
                raise Refused("story %s em %s: só READY/IN_PROGRESS recebe task (DoR primeiro)" % (story["id"], story["state"]))
        sess = active_session(ctx)
        sid = spec.get("session") or (sess or {}).get("id")
        tid = spec.get("id")
        if not tid:
            seq = len(ctx.board["tasks"]) + 1
            typ = (spec.get("type") or "").upper()
            tid = "TASK-%s-%03d-%s" % (spec.get("sprint") or "00", seq, typ) if typ in engine.TASK_TYPES else "T-%d" % seq
        if not engine.ID_RE.match(tid) or ctx.find("task", tid):
            raise Refused("id de task inválido ou repetido: %s" % tid)
        ap = [hcore.norm_rel(p) for p in spec.get("allowed_paths") or []]
        pp = [hcore.norm_rel(p) for p in spec.get("protected_paths") or []]
        br = dict(spec.get("briefing") or {})
        br["invariants"] = engine.required_invariants(ctx, ap) if ap else []
        br.setdefault("references", [])
        br.setdefault("scope", {"in": [], "out": []})
        t = {
            "id": tid, "story": story["id"], "sprint": spec.get("sprint"), "session": sid, "agent": spec["agent"],
            "title": spec.get("title", ""), "goal": spec.get("goal", ""), "class": spec.get("class"),
            "wave": int(spec.get("wave") or 1), "depends_on": list(spec.get("depends_on") or []),
            "flags": spec.get("flags") or {"hot_path": False, "security_gate": False},
            "readonly": bool(spec.get("readonly")),
            "allowed_paths": ap, "protected_paths": pp, "briefing": br,
            "acceptance_criteria": _ac_list(spec.get("acceptance_criteria")), "dod": list(spec.get("dod") or []),
            "verification_command": engine.with_protection(spec.get("verification_command") or "", pp),
            "knowledge_context": knowledge_context(root, spec, ap), "handoff": spec.get("handoff") or {},
            "status": "DRAFT", "attempts": 0, "amendments": [], "submission": None, "reviews": [],
            "gate_report": {"build": None, "verdict": None, "by": None, "at": None},
            "created_at": _now(), "updated_at": _now(),
        }
        if quick:
            t["quick"] = True
            t["work_type"] = spec["work_type"]
        d = {"id": "%s.d1" % tid, "agent": t["agent"], "state": "PLANNED", "retries": 0, "created_at": _now()}
        evs = pre + [Event("task.add", tid, [["create", "task", None, t], ["create", "deleg", tid, d]])]
        if ready or quick:
            ctx2 = engine.Ctx(root, copy.deepcopy(ctx.board), actor)
            for ev in evs:
                hcore.apply_ops(ctx2.board, ev.ops)
            evs.append(_ready_event(ctx2, t, d))
        return evs
    return engine.commit(root, actor, build)


def knowledge_context(root, spec, ap):
    try:
        import mem
        res = mem.search(root, "%s %s" % (spec.get("title", ""), " ".join(ap)), k=3, paths=ap)
        return [{"id": r["id"], "text": r["text"][:200]} for r in res]
    except Exception:
        return []


def _ready_event(ctx, task, d):
    import router
    import tree
    got = {}

    def extra(to, probs):
        rec = router.recommend(ctx, task, d, act="dev")
        got["route"] = rec
        return [["set", ref("deleg", d["id"]), "route", rec]]
    ev = transition(ctx, "deleg", d["id"], "ready", {}, extra)
    return tree.sync_m2_event(ctx.board, ev, task["id"], ctx.actor, "ready", agent=d.get("agent"),
                              route=got.get("route"))


def ready(root, actor, tid):
    def build(ctx):
        t, d = _deleg(ctx, tid, "ready")
        return [_ready_event(ctx, t, d)]
    return engine.commit(root, actor, build)


DISPATCH_VIA_AGENT = ("despacho sem tool_use_id não lança subagente nenhum: só mudaria o estado para DISPATCHED e "
                      "gastaria a tentativa (despacho fantasma, D-1-02)")


def dispatch(root, actor, ident, model=None, tool_use_id=None, procedencia=None, override_reason=None,
             require_tool_use_id=False, manual=False):
    """BRIEFED → DISPATCHED. No Claude Code o despacho legítimo vem do hook pre-agent (ferramenta Agent com o id da
    delegação na description), que passa o tool_use_id. Plataformas SEM hook pre-agent (Cursor, Copilot, Codex)
    declaram a execução com manual=True (`cs-state dispatch --manual`): tool_use_id "manual:<timestamp>",
    dispatch_origin "manual", consome tentativa normalmente. require_tool_use_id=True (CLI): sem tool_use_id e sem
    manual recusa — DEPOIS das guardas (a recusa por guarda continua nomeando a guarda)."""
    if manual and tool_use_id:
        raise Refused("--manual e --tool-use-id são excludentes (--manual é para plataforma sem hook pre-agent)")
    if manual:
        tool_use_id = "manual:%s" % _now()

    def build(ctx):
        tid = resolve_task_id(ctx, ident)
        t, d = _deleg(ctx, tid, "dispatch")
        a = {"model": model, "tool_use_id": tool_use_id, "procedencia": procedencia}
        if manual:
            a["dispatch_origin"] = "manual"

        def extra(to, probs):
            base = engine.git_dirty(ctx.root)
            ops = [["inc", ref("task", tid), "attempts", 1],
                   ["set", ref("deleg", d["id"]), "attempt", t["attempts"] + 1],
                   ["set", ref("deleg", d["id"]), "dispatched_at", _now()],
                   ["set", ref("deleg", d["id"]), "tool_use_id", tool_use_id],
                   ["set", ref("deleg", d["id"]), "model", {"name": model, "procedencia": procedencia or "declarada-no-despacho"}],
                   ["set", ref("deleg", d["id"]), "baseline", base if base is not None else {"__nogit__": True}],
                   ["set", ref("task", tid), "reject_reason", None]]
            if manual:
                ops.append(["set", ref("deleg", d["id"]), "dispatch_origin", "manual"])
            # D-0-13: a base da TASK é fixada no 1º dispatch e não muda em retry/retomada/reroute. Board antigo (task
            # já despachada sem change_base) grava a base derivada do 1º evento de dispatch, se der para derivar.
            if not t.get("change_base"):
                cb = engine.new_change_base(ctx.root, base) if not t["attempts"] else \
                    engine.fallback_change_base(ctx.root, t)
                if cb:
                    ops.append(["set", ref("task", tid), "change_base", cb])
            return ops
        ev = transition(ctx, "deleg", d["id"], "dispatch", a, extra)
        if require_tool_use_id and not tool_use_id:
            m = model or (d.get("route_override") or {}).get("model") or (d.get("route") or {}).get("model") or "<model>"
            raise Refused(DISPATCH_VIA_AGENT, hint="despache pela ferramenta Agent com o id da delegação na description "
                          "(o hook pre-agent faz a transição e grava o tool_use_id): Agent(subagent_type=%r, model=%r, "
                          "description='%s: <resumo>'); fora do Claude Code (sem hook pre-agent) use --manual: "
                          "cs-state dispatch --task %s --manual [--model M]" % (d["agent"], m, d["id"], tid))
        s = ctx.find("story", t["story"])
        if s and s["state"] in ("READY", "IN_PROGRESS"):
            return [ev] + _start_story_chain(ctx, [ev], s)
        return [ev]
    return engine.commit(root, actor, build)


def submit(root, actor, tid, submission):
    def build(ctx):
        t, d = _deleg(ctx, resolve_task_id(ctx, tid), "submit")
        sub = dict(submission)
        sub.setdefault("risks", [])
        sub.setdefault("handoff_notes", "")
        sub.setdefault("abstain", None)
        sub["files_changed"] = [hcore.norm_rel(f) for f in sub.get("files_changed") or []]

        def extra(to, probs):
            s2 = dict(sub)
            s2["attempt"] = t["attempts"]
            s2["at"] = _now()
            return [["set", ref("task", t["id"]), "submission", s2]]
        return [transition(ctx, "deleg", d["id"], "submit", {"submission": sub}, extra)]
    return engine.commit(root, actor, build)


def is_phantom_dispatch(d):
    """D-1-02: delegação DISPATCHED sem tool_use_id = despacho fantasma (`cs-state dispatch` pelo Bash de motor antigo):
    só o estado mudou, nenhum subagente foi lançado."""
    return bool(d) and d.get("state") == "DISPATCHED" and not d.get("tool_use_id")


def return_(root, actor, tid, reason="protocol_failure: retorno sem submission"):
    """DISPATCHED → REJECTED. Despacho FANTASMA (sem tool_use_id): devolve a tentativa que ele consumiu (attempts -1) e
    marca a delegação (`phantom_dispatch`) para o retry seguinte não contar retry — depois de `return` + `retry` a task
    tem a MESMA contagem de antes do fantasma."""
    def build(ctx):
        t, d = _deleg(ctx, resolve_task_id(ctx, tid), "return")
        phantom = is_phantom_dispatch(d)

        def extra(to, probs):
            ops = [["set", ref("task", t["id"]), "reject_reason", reason]]
            if not phantom:
                return ops + _block_if_exhausted(ctx, t, d, to)
            ops += [["inc", ref("task", t["id"]), "attempts", -1],
                    ["set", ref("deleg", d["id"]), "phantom_dispatch",
                     {"at": _now(), "reason": reason, "attempt_refunded": d.get("attempt") or t["attempts"],
                      "pending_retry": True}]]
            cb = t.get("change_base") or {}
            # a base da TASK fotografada pelo fantasma (1º dispatch) não é base de trabalho nenhum: o 1º despacho REAL a refaz
            if t["attempts"] <= 1 and cb.get("source") == engine.CHANGE_BASE_FIRST:
                ops.append(["set", ref("task", t["id"]), "change_base", None])
            return ops
        return [transition(ctx, "deleg", d["id"], "return", {"reason": reason, "phantom_dispatch": phantom}, extra)]
    return engine.commit(root, actor, build)


def verify(root, actor, tid):
    """Duas fases: executa FORA do lock (comando pode demorar), depois confirma sob lock."""
    ctx0 = _ctx_ro(root, actor)
    tid = resolve_task_id(ctx0, tid)
    t0, d0 = _deleg(ctx0, tid, "verify")
    timeout = int(ctx0.cfg.get("verify_timeout_s", 900))
    # D-1-03: sufixo legado de checagem crua da árvore removido; protected_paths são provados em diff_check
    build_run = engine.run_cmd(root, engine.strip_protection(t0["verification_command"]), timeout)
    ac_runs = []
    for ac in t0.get("acceptance_criteria") or []:
        vb = ac.get("verified_by") or ""
        if vb.startswith("test:"):
            cmd = engine.resolve_test(ctx0.cfg, vb[5:])
            r = engine.run_cmd(root, cmd, timeout) if cmd else {"exit_code": 127, "cmd": None}
            ac_runs.append({"ac": ac["id"], "test": vb[5:], "cmd": cmd, "exit_code": r["exit_code"],
                            "output_sha256": r.get("output_sha256"), "tail": (r.get("tail") or "")[-600:]})
    files_changed = (t0.get("submission") or {}).get("files_changed") or []
    diff_problems = diff_check(ctx0, t0, d0, files_changed)
    lesson_failures = []
    try:
        import mem
        chk = mem.check(root, t0["agent"], files_changed, run=True)
        lesson_failures = ["lição %s violada: %s (check: %s)" % (f["id"], f["rule"], f.get("check")) for f in chk["failed"]]
    except ImportError:
        pass
    tree_files = set(files_changed) | set(engine.files_in_scope(root, t0["allowed_paths"]))
    # R1 (iter18): ignorado pelo git (saída de build de qualquer task) não entra no tree_sha256
    tree_files = sorted(tree_files - engine.git_ignored(root, sorted(tree_files)))
    dirty_now = engine.git_dirty(root) or {}
    build_run.update({"attempt": t0["attempts"], "tree_sha256": engine.tree_sha(root, tree_files), "tree_files": tree_files,
                      "changed_sha256": engine.tree_sha(root, files_changed),
                      "dirty_in_scope": {p: dirty_now[p] for p in tree_files if p in dirty_now}})
    import envfail
    fkind, ftools = envfail.classify(root, [build_run] + ac_runs, diff_problems + lesson_failures)
    gate = {"build": build_run, "ac_tests": ac_runs, "diff_problems": diff_problems, "lesson_failures": lesson_failures}
    os.makedirs(hcore.state_paths(root)["evidence"], exist_ok=True)

    def build(ctx):
        t, d = _deleg(ctx, tid, "verify")
        if t["attempts"] != t0["attempts"] or d["id"] != d0["id"]:
            raise Refused("estado mudou durante o verify; rode de novo")

        def extra(to, probs):
            gr = {"build": {k: build_run[k] for k in ("exit_code", "at", "tree_sha256", "command_sha256", "output_sha256",
                                                      "duration_s", "cmd", "attempt", "tree_files", "timed_out",
                                                      "changed_sha256", "dirty_in_scope")},
                  "ac_tests": ac_runs, "verdict": None, "by": None, "at": None}
            gr["build"]["tail"] = (build_run.get("tail") or "")[-600:]
            if to == "REJECTED" and fkind:
                gr["failure_kind"] = fkind
                gr["missing_tools"] = ftools
            ops = [["set", ref("task", tid), "gate_report", gr]]
            if to == "REJECTED":
                pre = "verify (AMBIENTE: %s ausente): " % ", ".join(ftools) if fkind == envfail.ENVIRONMENT else "verify: "
                ops.append(["set", ref("task", tid), "reject_reason", pre + "; ".join(probs)[:1500]])
                ops += _block_if_exhausted(ctx, t, d, to)
            return ops
        ev = transition(ctx, "deleg", d["id"], "verify", {"_gate": gate}, extra)
        ev.data["gate"] = {"exit_code": build_run["exit_code"], "output_sha256": build_run["output_sha256"],
                           "failure_kind": fkind, "missing_tools": ftools,
                           "tail": build_run["tail"][-600:], "ac_tests": ac_runs, "diff_problems": diff_problems,
                           "lesson_failures": lesson_failures}
        return [ev]
    return engine.commit(root, actor, build)


def reverify(root, actor, tid):
    """REJECTED (falha de AMBIENTE) ou ESCALATED → RETURNED e roda o verify de novo (ambiente consertado). Não consome
    tentativa; o pipeline segue normal (review por gate, accept).
    De VERIFIED/REVIEWED (árvore mudou desde o verify — iter18): as reviews da tentativa ficam se o conteúdo dos
    files_changed é o mesmo do verify; senão vão para `reviews_invalidated` (o accept exige nova review)."""
    def build(ctx):
        t, d = _deleg(ctx, resolve_task_id(ctx, tid), "reverify")
        was_verified = d["state"] in ("VERIFIED", "REVIEWED")

        def extra(to, probs):
            ops = [["set", ref("task", t["id"]), "block_reason", None]]
            if was_verified:
                ops += _invalidate_reviews_if_changed(ctx, t)
                ops += _post_verify_changes(ctx, t, d)
            return ops
        return [transition(ctx, "deleg", d["id"], "reverify", {}, extra)]
    engine.commit(root, actor, build)
    return verify(root, actor, tid)


def _invalidate_reviews_if_changed(ctx, t):
    """Reviews da tentativa julgaram o conteúdo dos files_changed do verify: mesmo conteúdo → ficam; mudou (ou verify
    antigo sem changed_sha256) → saem de `reviews` para `reviews_invalidated` (registro mantido)."""
    b = ((t.get("gate_report") or {}).get("build") or {})
    files = (t.get("submission") or {}).get("files_changed") or []
    if b.get("changed_sha256") and engine.tree_sha(ctx.root, files) == b["changed_sha256"]:
        return []
    cur = [r for r in t.get("reviews") or [] if r.get("attempt") == t["attempts"]]
    if not cur:
        return []
    keep = [r for r in t.get("reviews") or [] if r.get("attempt") != t["attempts"]]
    gone = list(t.get("reviews_invalidated") or []) + [dict(r, invalidated_at=_now(),
                                                            invalidated_by="reverify: files_changed mudaram") for r in cur]
    return [["set", ref("task", t["id"]), "reviews", keep], ["set", ref("task", t["id"]), "reviews_invalidated", gone]]


def _post_verify_changes(ctx, t, d):
    """Arquivos do escopo, fora dos files_changed, que mudaram DEPOIS do verify (outra task, build, humano): o verify
    do reverify não os cobra desta delegação. Verify antigo sem `dirty_in_scope` → nada tolerado (conservador)."""
    old = ((t.get("gate_report") or {}).get("build") or {}).get("dirty_in_scope")
    if old is None:
        return []
    files = set((t.get("submission") or {}).get("files_changed") or [])
    now = engine.git_dirty(ctx.root) or {}
    post = {p: sha for p, sha in now.items()
            if p not in files and hcore.matches_any(p, t["allowed_paths"]) and old.get(p, "__absent__") != sha}
    if not post:
        return []
    return [["set", ref("deleg", d["id"]), "post_verify_changes", dict(d.get("post_verify_changes") or {}, **post)]]


def waive_verify(root, actor, tid, reason, by, evidence):
    """Exceção de AMBIENTE com portão humano: REJECTED/ESCALATED → VERIFIED com `verify_waiver` (motivo, quem, evidência).
    Só quando o último verify desta tentativa falhou por ambiente (nunca teste/asserção); review por gate continua
    obrigatória (≥1 PASS, mesmo em classe que não exigiria)."""
    def build(ctx):
        t, d = _deleg(ctx, resolve_task_id(ctx, tid), "waive_verify")

        def extra(to, probs):
            gr = t.get("gate_report") or {}
            w = {"attempt": t["attempts"], "delegation": d["id"], "by": by, "reason": reason, "evidence": evidence[:4000],
                 "failure_kind": gr.get("failure_kind") or engine.verify_failure(ctx, t)[0],
                 "missing_tools": gr.get("missing_tools") or engine.verify_failure(ctx, t)[1],
                 "output_sha256": (gr.get("build") or {}).get("output_sha256"), "recorded_by": actor, "at": _now()}
            return [["set", ref("task", t["id"]), "verify_waiver", w],
                    ["append", ref("task", t["id"]), "waivers", w],
                    ["set", ref("task", t["id"]), "block_reason", None]]
        return [transition(ctx, "deleg", d["id"], "waive_verify", {"reason": reason, "by": by, "evidence": evidence}, extra)]
    return engine.commit(root, actor, build)


def diff_check(ctx, task, deleg, files_changed):
    """files_changed × git × allowed_paths — nada fora. Território: desde a base da TASK (1º dispatch, D-0-13);
    fora dele: desde o baseline do dispatch desta delegação."""
    P = []
    dirty = engine.git_dirty(ctx.root)
    if dirty is None:
        if ctx.cfg.get("require_git_diff_check", True):
            return ["não é repositório git: impossível conferir git diff × allowed_paths (fail-closed; config require_git_diff_check)"]
        return []
    base = deleg.get("baseline") or {}
    changed = {p for p, sha in dirty.items() if base.get(p, "__absent__") != sha}
    changed |= {p for p in base if p != "__nogit__" and p not in dirty}
    # D-0-13: dentro de allowed_paths, "alterado" = difere da base da TASK (1º dispatch), não da fotografia desta
    # delegação — retry/retomada/reroute sobre trabalho já na árvore não vira "não alterado". Fora do território
    # continua valendo a fotografia desta delegação.
    cb = engine.task_change_base(ctx.root, task)
    if cb:
        ap = task["allowed_paths"]
        cands = changed | set(dirty) | set(files_changed) | engine.task_base_candidates(ctx.root, cb)
        in_scope = {f for f in cands if hcore.matches_any(f, ap)}
        task_changed = engine.task_changed_files(ctx.root, cb, in_scope)
        if cb.get("source") == engine.CHANGE_BASE_FIRST:
            changed = {f for f in changed if not hcore.matches_any(f, ap)} | task_changed
        else:
            # base derivada (board antigo, HEAD aproximado pelo horário): só resgata o que foi DECLARADO; o resto
            # do território segue a fotografia da delegação (não inventa "alterado e não declarado").
            changed |= task_changed & set(files_changed)
    lead_ok = ctx.cfg.get("lead_write_allow") or []
    # trabalho de OUTRAS delegações já despachadas (ondas-irmãs em voo/verificadas/paradas, ou fechadas depois do
    # baseline desta) não conta como escrita fora do território desta task.
    since = deleg.get("dispatched_at") or ""
    others = [x for x in ctx.board["tasks"] if x["id"] != task["id"] for dd in x.get("delegations") or []
              if dd.get("dispatched_at") and (
                  dd["state"] in ("DISPATCHED", "RETURNED", "VERIFIED", "REVIEWED", "REJECTED", "ESCALATED", "ABSTAINED")
                  or (dd.get("updated_at") or "") >= since)]
    for f in files_changed:
        if f not in changed:
            if ctx.board.get("mandatos"):
                import auto  # M5: arquivo comum já entregue (idêntico) por nó ACEITO da sub-onda anterior
                if auto.mandate_shared_file(ctx.board, task, f):
                    continue
            P.append("declarado em files_changed mas não alterado segundo git: %s" % f)
    # R2 (iter18): mudança no escopo DEPOIS do verify (gravada pelo reverify de VERIFIED/REVIEWED) não é desta delegação
    tol = deleg.get("post_verify_changes") or {}
    changed = {f for f in changed if f in files_changed or f not in tol or dirty.get(f) != tol[f]}
    prot = task.get("protected_paths") or []
    for f in sorted(changed):
        if f.startswith(hcore.STATE_DIR + "/") or hcore.matches_any(f, lead_ok):
            continue
        # D-1-03: protected_paths provados contra o que ESTA delegação mudou (não contra a árvore inteira): trabalho
        # de task-irmã em voo dentro do protected não é culpa desta; mudança desta delegação no protected reprova.
        if prot and hcore.matches_any(f, prot) and not any(hcore.matches_any(f, o["allowed_paths"]) for o in others):
            P.append("protected_path alterado por esta delegação: %s (protected_paths: %s)" % (f, ", ".join(prot)))
            continue
        if hcore.matches_any(f, task["allowed_paths"]):
            if f not in files_changed:
                P.append("alterado e não declarado em files_changed: %s" % f)
            continue
        if any(hcore.matches_any(f, o["allowed_paths"]) for o in others):
            continue
        P.append("alterado FORA de allowed_paths: %s" % f)
    return P


def review(root, actor, tid, by, verdict, findings):
    def build(ctx):
        t, d = _deleg(ctx, resolve_task_id(ctx, tid), "review")

        def extra(to, probs):
            r = {"by": by, "verdict": verdict, "findings": findings, "at": _now(), "attempt": t["attempts"], "delegation": d["id"]}
            gr = dict(t.get("gate_report") or {})
            gr.update({"verdict": verdict, "by": by, "at": r["at"]})
            return [["append", ref("task", t["id"]), "reviews", r], ["set", ref("task", t["id"]), "gate_report", gr]]
        return [transition(ctx, "deleg", d["id"], "review", {"by": by, "verdict": verdict, "findings": findings}, extra)]
    return engine.commit(root, actor, build)


def accept(root, actor, tid):
    def build(ctx):
        t, d = _deleg(ctx, resolve_task_id(ctx, tid), "accept")

        ev = transition(ctx, "deleg", d["id"], "accept", {})
        return [ev] + _story_to_review(ctx, [ev], t)
    return engine.commit(root, actor, build)


def reject(root, actor, tid, reason):
    def build(ctx):
        t, d = _deleg(ctx, resolve_task_id(ctx, tid), "reject")

        def extra(to, probs):
            return [["set", ref("task", t["id"]), "reject_reason", reason]] + _block_if_exhausted(ctx, t, d, to)
        return [transition(ctx, "deleg", d["id"], "reject", {"reason": reason}, extra)]
    return engine.commit(root, actor, build)


def retry(root, actor, tid, findings=None, decision=None):
    """REJECTED → BRIEFED (consome tentativa) ou ESCALATED/ABSTAINED → BRIEFED (retomada por decisão humana: os achados
    são a decisão, não consome tentativa e a task sai do bloqueio)."""
    findings = _joined(decision, findings)

    def build(ctx):
        t, d = _deleg(ctx, resolve_task_id(ctx, tid), "retry")
        human = d["state"] in engine.awaiting_human(ctx)
        f = findings if human else (findings or t.get("reject_reason"))
        # D-1-02: retry depois do `return` de um despacho fantasma não conta retry (ninguém trabalhou)
        phantom = d["state"] == "REJECTED" and bool((d.get("phantom_dispatch") or {}).get("pending_retry"))

        def extra(to, probs):
            import router
            ops = []
            nd = dict(d)
            if phantom:
                pd = dict(d["phantom_dispatch"])
                pd["pending_retry"] = False
                ops.append(["set", ref("deleg", d["id"]), "phantom_dispatch", pd])
            elif not human:
                nd["retries"] = int(d.get("retries") or 0) + 1
                ops.append(["inc", ref("deleg", d["id"]), "retries", 1])
            rec = {"at": _now(), "findings": f}
            if human:
                rec.update({"decision": True, "from": d["state"]})
                ops.append(["set", ref("task", t["id"]), "block_reason", None])
            got["route"] = router.recommend(ctx, t, nd, act="dev")
            return ops + [["append", ref("deleg", d["id"]), "findings_in", rec],
                          ["set", ref("deleg", d["id"]), "route", got["route"]],
                          ["set", ref("deleg", d["id"]), "route_override", None]]
        got = {}
        ev = transition(ctx, "deleg", d["id"], "retry", {"findings": findings}, extra)
        import tree  # modo árvore: o arquivo da task acompanha a delegação vigente (agent/route), com de/para no evento
        return [tree.sync_m2_event(ctx.board, ev, t["id"], ctx.actor, "retry", agent=d.get("agent"),
                                   route=got.get("route"))]
    return engine.commit(root, actor, build)


def _joined(decision, findings):
    parts = []
    if decision and str(decision).strip():
        parts.append("decisão do humano: %s" % str(decision).strip())
    if findings and str(findings).strip():
        parts.append(str(findings).strip())
    return " | ".join(parts) or None


def escalate(root, actor, tid, reason):
    def build(ctx):
        t, d = _deleg(ctx, resolve_task_id(ctx, tid))

        def extra(to, probs):
            return [["set", ref("task", t["id"]), "block_reason", "escalado: " + reason]]
        return [transition(ctx, "deleg", d["id"], "escalate", {"reason": reason}, extra)]
    return engine.commit(root, actor, build)


def reroute(root, actor, tid, agent, reason, allowed_paths=None, decision=None):
    """Troca de agente. De ESCALATED/ABSTAINED é a saída "trocar de agente" da decisão humana (--decision vira o motivo)."""
    reason = _joined(decision, reason)

    def build(ctx):
        t, d = _deleg(ctx, resolve_task_id(ctx, tid))
        ap = [hcore.norm_rel(p) for p in allowed_paths] if allowed_paths else None

        def extra(to, probs):
            n = len(t.get("delegations") or []) + 1
            nd = {"id": "%s.d%d" % (t["id"], n), "agent": agent, "state": "PLANNED", "retries": 0, "created_at": _now(),
                  "rerouted_from": d["id"]}
            ops = [["set", ref("task", t["id"]), "agent", agent], ["create", "deleg", t["id"], nd]]
            if t.get("block_reason"):
                ops.append(["set", ref("task", t["id"]), "block_reason", None])
            if ap:
                ops.append(["set", ref("task", t["id"]), "allowed_paths", ap])
                br = dict(t.get("briefing") or {})
                br["invariants"] = engine.required_invariants(ctx, ap)
                ops.append(["set", ref("task", t["id"]), "briefing", br])
            return ops
        ev = transition(ctx, "deleg", d["id"], "reroute", {"reason": reason, "agent": agent, "allowed_paths": ap}, extra)
        import tree  # modo árvore: arquivo da task com o agente novo; route nulo até o `ready` da nova delegação
        return [tree.sync_m2_event(ctx.board, ev, t["id"], ctx.actor, "reroute", agent=agent, route=None)]
    return engine.commit(root, actor, build)


def drop(root, actor, tid, reason):
    """Descarta a task por decisão humana: delegação ESCALATED/ABSTAINED/REJECTED → DROPPED; task DROPPED (fechada)."""
    def build(ctx):
        t, d = _deleg(ctx, resolve_task_id(ctx, tid))

        def extra(to, probs):
            return [["set", ref("task", t["id"]), "drop_reason", reason], ["set", ref("task", t["id"]), "block_reason", None]]
        ev = transition(ctx, "deleg", d["id"], "drop", {"reason": reason}, extra)
        return [ev] + _story_to_review(ctx, [ev], t, need_accepted_other=True)
    return engine.commit(root, actor, build)


def abstain(root, actor, tid, kind, reason):
    def build(ctx):
        t, d = _deleg(ctx, resolve_task_id(ctx, tid))

        def extra(to, probs):
            sub = dict(t.get("submission") or {"files_changed": [], "checks_run": [], "risks": [], "handoff_notes": ""})
            sub["abstain"] = {"kind": kind, "reason": reason, "at": _now()}
            return [["set", ref("task", t["id"]), "submission", sub],
                    ["append", ref("task", t["id"]), "abstentions", {"kind": kind, "reason": reason, "at": _now(), "delegation": d["id"]}]]
        return [transition(ctx, "deleg", d["id"], "abstain", {"reason": reason, "abstain_kind": kind}, extra)]
    return engine.commit(root, actor, build)


def delegate(root, actor, tid):
    """Nova delegação PLANNED depois de ABSTAINED (spec corrigida com amend)."""
    def build(ctx):
        t = _task(ctx, tid)
        d = latest_deleg(t)
        if d and d["state"] not in ("ABSTAINED",):
            raise Refused("nova delegação só após ABSTAINED (atual %s)" % d["state"])
        n = len(t.get("delegations") or []) + 1
        nd = {"id": "%s.d%d" % (t["id"], n), "agent": t["agent"], "state": "PLANNED", "retries": 0, "created_at": _now()}
        return [Event("delegation.create", nd["id"], [["create", "deleg", t["id"], nd]])]
    return engine.commit(root, actor, build)


AMENDABLE = ("title", "goal", "allowed_paths", "protected_paths", "verification_command", "acceptance_criteria",
             "dod", "depends_on", "wave", "briefing", "handoff", "flags")


def amend(root, actor, tid, field, after, reason, found_by=None):
    """Correção formal do brief (evento), nunca edição silenciosa. field pode ser pontuado:
    acceptance_criteria.AC-2 | briefing.scope.out | allowed_paths ..."""
    if not reason:
        raise Refused("--reason obrigatório")

    def build(ctx):
        t = _task(ctx, tid)
        top = field.split(".")[0]
        if top not in AMENDABLE:
            raise Refused("campo não emendável: %s (permitidos: %s)" % (field, ", ".join(AMENDABLE)))
        new_t = copy.deepcopy(t)
        before = _set_dotted(new_t, field, after)
        if top in ("allowed_paths", "protected_paths"):
            new_t[top] = [hcore.norm_rel(p) for p in new_t[top]]
        if top in ("verification_command", "protected_paths"):
            new_t["verification_command"] = engine.with_protection(new_t["verification_command"], new_t.get("protected_paths") or [])
        if top == "allowed_paths":
            br = dict(new_t.get("briefing") or {})
            br["invariants"] = engine.required_invariants(ctx, new_t["allowed_paths"])
            new_t["briefing"] = br
        d = latest_deleg(t)
        if d and d["state"] not in ("PLANNED",):
            probs = engine.brief_problems(ctx, new_t, d["agent"])
            if probs:
                raise Refused(["emenda deixaria o brief inválido:"] + probs)
        ops = []
        for k in set([top, "verification_command", "briefing"]):
            if new_t.get(k) != t.get(k):
                ops.append(["set", ref("task", tid), k, new_t.get(k)])
        ops.append(["append", ref("task", tid), "amendments", {"at": _now(), "by": actor, "field": field, "before": before,
                                                               "after": after, "reason": reason, "found_by": found_by}])
        return [Event("task.amend", tid, ops, {"args": {"field": field, "reason": reason}})]
    return engine.commit(root, actor, build)


def _set_dotted(obj, path, value):
    parts = path.split(".")
    cur = obj
    for i, p in enumerate(parts[:-1]):
        if isinstance(cur, list):
            cur = _list_by_id(cur, p)
        else:
            cur = cur.setdefault(p, {})
    last = parts[-1]
    if isinstance(cur, list):
        for i, it in enumerate(cur):
            if isinstance(it, dict) and it.get("id") == last:
                before = copy.deepcopy(it)
                if isinstance(value, dict):
                    cur[i] = dict(value, id=last)
                else:
                    cur[i]["criterion"] = value
                return before
        cur.append(dict(value, id=last) if isinstance(value, dict) else {"id": last, "criterion": value,
                                                                        "verified_by": "reviewer"})
        return None
    before = copy.deepcopy(cur.get(last))
    cur[last] = value
    return before


def _list_by_id(lst, ident):
    for it in lst:
        if isinstance(it, dict) and it.get("id") == ident:
            return it
    raise Refused("item %s não encontrado" % ident)


# ================================================================ M4 — consulta (faixa pergunta)
def ask(root, actor, agent, question, paths=None):
    """Delegação de consulta SÓ LEITURA, já BRIEFED; sem task/story. Devolve o id (ASK-n)."""
    if not (question or "").strip():
        raise Refused("pergunta vazia: cs-state ask <agente> \"<pergunta>\"")
    paths = [hcore.norm_rel(p) for p in paths or []]

    def build(ctx):
        if ctx.team is None:
            raise Refused("team.json5 ausente: impossível validar o agente (fail-closed)")
        if not hcore.team_agent(ctx.team, agent):
            raise Refused("agente %r não existe em team.json5" % agent)
        sess = active_session(ctx)
        cid = engine.next_id(ctx.board, "consult", "ASK")
        try:
            import router
            tiers = router.tiers() or ["sonnet"]
        except Exception:
            tiers = ["sonnet"]
        model = "sonnet" if "sonnet" in tiers else tiers[len(tiers) // 2]  # consulta: tier do meio
        c = {"id": cid, "kind": "consult", "state": "BRIEFED", "agent": agent, "question": question.strip(),
             "paths": paths or ctx.territory(agent), "session": (sess or {}).get("id"), "readonly": True,
             "route": {"model": model, "band": "consulta"}, "created_at": _now()}
        return [Event("consult.ask", cid, [["create", "consult", None, c]], {"args": {"agent": agent, "question": question[:300]}})]
    _, ev = engine.commit(root, actor, build)
    return ev[0]["entity"]


def consult_dispatch(root, actor, cid, model=None, tool_use_id=None):
    def build(ctx):
        c = ctx.find("consult", cid)
        if c is None:
            raise Refused("consulta %s inexistente" % cid)

        def extra(to, probs):
            return [["set", ref("consult", cid), "dispatched_at", _now()],
                    ["set", ref("consult", cid), "tool_use_id", tool_use_id],
                    ["set", ref("consult", cid), "model", {"name": model, "procedencia": "declarada-no-despacho"}]]
        return [transition(ctx, "consult", cid, "dispatch", {"model": model, "tool_use_id": tool_use_id}, extra)]
    return engine.commit(root, actor, build)


def consult_answer(root, actor, cid):
    def build(ctx):
        def extra(to, probs):
            return [["set", ref("consult", cid), "answered_at", _now()]]
        return [transition(ctx, "consult", cid, "answer", {}, extra)]
    return engine.commit(root, actor, build)


def consult_cancel(root, actor, cid, reason):
    def build(ctx):
        return [transition(ctx, "consult", cid, "cancel", {"reason": reason})]
    return engine.commit(root, actor, build)


def override_model(root, actor, ident, model, reason):
    def build(ctx):
        tid = resolve_task_id(ctx, ident)
        t, d = _deleg(ctx, tid, ["BRIEFED", "REJECTED"])
        if not reason:
            raise Refused("override exige --reason")
        return [Event("delegation.override_model", d["id"], [
            ["set", ref("deleg", d["id"]), "route_override", {"model": model, "reason": reason, "at": _now(), "by": actor}]],
            {"args": {"model": model, "reason": reason}})]
    return engine.commit(root, actor, build)


def legacy_ack(root, actor, reason):
    """Reconhece, NA CADEIA DE EVENTOS, o histórico que só um motor antigo/hotfix explicaria (transições hoje ilegais,
    ACCEPTED sem gate). Não muda estado nenhum; o validador passa a aceitar SÓ esses itens, só para eventos anteriores
    ao ack — transição nova continua sujeita a machines.json5. Ato do humano (o guard bloqueia agentes)."""
    if not (reason or "").strip():
        raise Refused("--reason obrigatório (por que esse histórico existe: hotfix, versão antiga do motor…)")
    import validate

    def build(ctx):
        events, cerr, _ = hcore.read_chain(ctx.paths["events"])
        if cerr:
            raise Refused(["cadeia de eventos quebrada — legacy-ack não conserta adulteração:"] + cerr[:5])
        illegal, accepted = validate.history_problems(root, events, ctx.board)
        # D-1-04: incoerências de hierarquia EXISTENTES agora e ainda não reconhecidas (uma por item: filho+estado,
        # pai+estado) — o validador aceita só essas e só enquanto continuarem as mesmas
        acked = engine.acked_hierarchy(events)
        hierarchy = [it for it in engine.hierarchy_items(ctx.board) if engine.hierarchy_key(it) not in acked]
        if not illegal and not accepted and not hierarchy:
            raise Refused("histórico já é canônico: nada a reconhecer (validate --strict)")
        return [Event("harness.legacy_ack", "harness", [], {"args": {"reason": reason.strip(), "transitions": illegal,
                                                                       "accepted": accepted, "hierarchy": hierarchy}})]
    return engine.commit(root, actor, build)
