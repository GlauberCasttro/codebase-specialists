#!/usr/bin/env python3
"""session — cs-session save|load (ARCHITECTURE §8-quater, G9). O modelo passa 1 linha; o script coleta o resto.

save: grava .swarm/session/resume.json5 com carimbo = sha256(board + hash do último evento + HEAD + fase).
load: carimbo bate (ou HEAD avançou só com commits de estado) → briefing curto (≤30 linhas, ≤2.000 tokens
estimados por chars/3,5) e nada mais; não bate → só o DELTA + briefing anterior. Sempre termina com o
próximo passo e o comando exato.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import hcore  # noqa: E402
import j5  # noqa: E402

MAX_LINES, MAX_TOKENS = 30, 2000
STATE_PREFIXES = (hcore.STATE_DIR + "/",)


def _git(root, args):
    try:
        p = subprocess.run(["git"] + args, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        return p.returncode, p.stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


def resume_path(root):
    return os.path.join(hcore.state_paths(root)["session_dir"], "resume.json5")


def _phase(root):
    p = hcore.state_paths(root)
    f = hcore.first_existing(p["run"], os.path.join(p["specialists"], "run.json"))
    if not f:
        return None
    try:
        r = hcore.read_any(f)
        return r.get("phase") or r.get("fase") or r.get("current_phase")
    except (OSError, ValueError):
        return None


def _area(path, team):
    for a in (team or {}).get("agents") or []:
        if any(hcore.path_matches(path, g) for g in a.get("territory") or []):
            return a["name"]
    return path.split("/")[0] if "/" in path else "(raiz)"


def stamp(board, head, phase):
    data = hcore.canonical({k: v for k, v in board.items()}) + "|" + board["last_event_hash"] + "|" + (head or "") + "|" + str(phase)
    return hcore.sha256_bytes(data.encode("utf-8"))


def collect(root):
    board = hcore.load_board(root)
    team = hcore.load_team(root)
    _, head = _git(root, ["rev-parse", "HEAD"])
    _, branch = _git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    _, st = _git(root, ["status", "--porcelain"])
    dirty = {}
    for ln in st.splitlines():
        if len(ln) > 3:
            path = ln[3:].split(" -> ")[-1]
            dirty.setdefault(_area(path, team), []).append(path)
    events, _, _ = hcore.read_chain(hcore.state_paths(root)["events"])
    by = {}
    for t in board["tasks"]:
        by.setdefault(t["status"], []).append(t["id"])
    sess = [s for s in board["sessions"] if s["state"] != "IDLE"]
    gates = {}
    p = hcore.state_paths(root)
    for name, f in (("selftest", p["selftest"]), ("acceptance", os.path.join(p["specialists"], "acceptance.json5"))):
        if os.path.isfile(f):
            try:
                d = j5.load(f)
                gates[name] = {"ok": d.get("ok", d.get("go")), "at": d.get("at")}
            except (OSError, ValueError):
                gates[name] = {"ok": None, "at": None}
    for t in board["tasks"]:
        b = (t.get("gate_report") or {}).get("build") or {}
        if b:
            gates["verify:" + t["id"]] = {"ok": b.get("exit_code") == 0, "at": b.get("at")}
    return board, {
        "head": head or None, "branch": branch or None, "phase": _phase(root),
        "tasks_by_status": by, "active_session": ({k: sess[-1].get(k) for k in ("id", "state", "class")} if sess else None),
        "active": [{"task": t["id"], "status": t["status"], "attempts": t["attempts"]} for t in board["tasks"]
                   if t["status"] in ("READY", "IN_PROGRESS", "SUBMITTED", "VERIFYING", "REJECTED")],
        "last_events": [{"seq": e["seq"], "type": e["type"], "entity": e.get("entity")} for e in events[-10:]],
        "event_count": board["event_count"], "dirty_by_area": dirty, "gates": gates,
        "task_status": {t["id"]: t["status"] for t in board["tasks"]},
    }


def _lessons_since(root, since):
    try:
        import mem
        rows = mem.read_jsonl(mem.mem_paths(root)["knowledge"])
        out = [r["id"] for r in rows if (r.get("created_at") or "") > (since or "")]
        return out[-10:]
    except Exception:
        return []


def _one_line(s, name):
    if s is None:
        return None
    s = " ".join(str(s).split())
    if len(s) > 240:
        raise hcore.Refused("--%s deve ter 1 linha (≤240 caracteres)" % name)
    return s


def _next_cmd(root, board):
    try:
        import engine
        import views
        L = views.next_lines(engine.Ctx(root, board))
        return L[-1] if L else "cs-state next"
    except Exception:
        return "cs-state next"


def save(root, did, next_, blocked=None, decision=None, commit=False, auto=False):
    did, next_ = _one_line(did, "did"), _one_line(next_, "next")
    blocked, decision = _one_line(blocked, "blocked"), _one_line(decision, "decision")
    if not did or not next_:
        raise hcore.Refused("save exige --did e --next (1 linha cada)")
    board, info = collect(root)
    prev = None
    if os.path.isfile(resume_path(root)):
        try:
            prev = j5.load(resume_path(root))
        except (OSError, ValueError):
            prev = None
    info["lessons_new"] = _lessons_since(root, (prev or {}).get("saved_at"))
    info.update({"did": did, "next": next_, "blocked": blocked, "decision": decision, "auto": auto,
                 "next_cmd": _next_cmd(root, board), "saved_at": hcore.now_iso()})
    info["stamp"] = stamp(board, info["head"], info["phase"])
    hcore.write_json5(resume_path(root), info, "resume.json5 — sessão salva por cs-session save (não editar)")
    try:
        import mem
        mem.record_episode(root, {"seq": "session:%s" % info["stamp"][:12], "at": info["saved_at"], "type": "session",
                                  "task": None, "actor": "session", "data": {}}, None)
        ep_path = mem.mem_paths(root)["episodes"]
        with open(ep_path, "ab") as f:
            f.write((mem.dumps_line({"seq": "session:%s" % info["stamp"][:12], "at": info["saved_at"], "type": "session",
                                     "task": None, "summary": "sessão salva: fez %s; próximo %s%s" % (
                                         did, next_, ("; bloqueio: %s" % blocked) if blocked else ""),
                                     "scope_paths": []}) + "\n").encode("utf-8"))
    except Exception:
        pass
    if commit:
        paths = [hcore.STATE_DIR + "/session", hcore.STATE_DIR + "/state"]
        _git(root, ["add", "--"] + paths)
        code, out = _git(root, ["commit", "-m", "chore(session): save %s" % info["stamp"][:12], "--"] + paths)
        info["commit"] = code == 0
    return info


def check_saved(root):
    """`cs-session save --check`: existe save e o carimbo bate com o estado atual."""
    if not os.path.isfile(resume_path(root)):
        return False, "nenhuma sessão salva (cs-session save --did ... --next ...)"
    prev = j5.load(resume_path(root))
    match, _ = _matches(root, prev)
    if not match:
        return False, "estado mudou desde o save: rode cs-session save"
    last = _last_approval_ts(root)
    if last and str(prev.get("saved_at") or "")[:19] < str(last)[:19]:
        # approve.3 (efeito): congelar o baseline DEPOIS da decisão do founder — save anterior não congela nada
        return False, "save (%s) é anterior à decisão do founder (%s): rode cs-session save de novo" % (
            prev.get("saved_at"), last)
    return True, "carimbo bate"


def _last_approval_ts(root):
    """ts da última decisão em .swarm/approvals.jsonl (cs.py approve), se houver."""
    p = os.path.join(root, hcore.STATE_DIR, "approvals.jsonl")
    last = None
    try:
        with open(p, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        last = json.loads(line).get("ts") or last
                    except ValueError:
                        continue
    except OSError:
        return None
    return last


def _matches(root, prev):
    board = hcore.load_board(root)
    _, head = _git(root, ["rev-parse", "HEAD"])
    phase = _phase(root)
    if stamp(board, head or None, phase) == prev.get("stamp"):
        return True, board
    if prev.get("head") and head and prev["head"] != head and stamp(board, prev["head"], phase) == prev.get("stamp"):
        code, out = _git(root, ["diff", "--name-only", "%s..%s" % (prev["head"], head)])
        if code == 0 and out and all(any(f.startswith(p) for p in STATE_PREFIXES) for f in out.splitlines()):
            return True, board
    return False, board


def _briefing(prev):
    L = ["sessão salva em %s (carimbo %s)" % (prev.get("saved_at", "?")[:19], prev.get("stamp", "")[:12])]
    if prev.get("active_session"):
        s = prev["active_session"]
        L.append("M1: %s [%s] classe=%s" % (s.get("id"), s.get("state"), s.get("class")))
    L.append("fez: %s" % prev.get("did"))
    if prev.get("blocked"):
        L.append("bloqueio: %s" % prev["blocked"])
    if prev.get("decision"):
        L.append("decisão: %s" % prev["decision"])
    for a in (prev.get("active") or [])[:6]:
        L.append("  %s %s (tent. %s)" % (a["task"], a["status"], a["attempts"]))
    if prev.get("dirty_by_area"):
        L.append("sujos por área: " + "; ".join("%s=%d" % (k, len(v)) for k, v in sorted(prev["dirty_by_area"].items()))[:300])
    bad = [k for k, g in (prev.get("gates") or {}).items() if g.get("ok") is False]
    if bad:
        L.append("gates vermelhos: " + ", ".join(bad[:6]))
    if prev.get("lessons_new"):
        L.append("lições novas: " + ", ".join(prev["lessons_new"][:5]))
    return L


def load(root, brief=False):
    if hcore.tree_mode(root):
        return tree_load(root)
    if not os.path.isfile(resume_path(root)):
        out = ["nenhuma sessão salva.", "próximo passo: cs-state next"]
        return "\n".join(out), False
    prev = j5.load(resume_path(root))
    match, board = _matches(root, prev)
    L = []
    if match:
        L += _briefing(prev)
    else:
        L.append("DELTA desde o save:")
        events, _, _ = hcore.read_chain(hcore.state_paths(root)["events"])
        new = [e for e in events if e["seq"] >= int(prev.get("event_count") or 0)]
        if new:
            L.append("eventos novos (%d): " % len(new) + "; ".join("%s %s" % (e["type"], e.get("entity") or "") for e in new[-6:]))
        _, head = _git(root, ["rev-parse", "HEAD"])
        if prev.get("head") and head and head != prev["head"]:
            code, out = _git(root, ["diff", "--name-only", "%s..%s" % (prev["head"], head)])
            team = hcore.load_team(root)
            areas = {}
            for f in out.splitlines():
                areas[_area(f, team)] = areas.get(_area(f, team), 0) + 1
            _, n = _git(root, ["rev-list", "--count", "%s..%s" % (prev["head"], head)])
            L.append("commits novos: %s; arquivos por área: %s" % (n, ", ".join("%s=%d" % kv for kv in sorted(areas.items()))[:300]))
        old = prev.get("task_status") or {}
        ch = ["%s %s→%s" % (t["id"], old.get(t["id"], "novo"), t["status"]) for t in board["tasks"] if old.get(t["id"]) != t["status"]]
        if ch:
            L.append("tasks que mudaram: " + "; ".join(ch[:8]))
        _, cur = collect(root)
        gch = ["%s %s→%s" % (k, (prev.get("gates") or {}).get(k, {}).get("ok"), g.get("ok"))
               for k, g in cur["gates"].items() if (prev.get("gates") or {}).get(k, {}).get("ok") != g.get("ok")]
        if gch:
            L.append("gates que mudaram: " + "; ".join(gch[:6]))
        if cur.get("phase") != prev.get("phase"):
            L.append("fase: %s→%s" % (prev.get("phase"), cur.get("phase")))
        L.append("briefing anterior:")
        L += ["  " + x for x in _briefing(prev)[1:6]]
    nxt = prev.get("next")
    cmd = _next_cmd(root, board) if not match else (prev.get("next_cmd") or "cs-state next")
    L.append("próximo passo: %s" % nxt)
    L.append("comando: %s" % cmd)
    L = L[:MAX_LINES - 2] + L[-2:] if len(L) > MAX_LINES else L
    text = "\n".join(L)
    max_chars = int(MAX_TOKENS * 3.5)
    if len(text) > max_chars:
        head_part = "\n".join(L[:-2])[: max_chars - 400]
        text = head_part + "\n" + "\n".join(L[-2:])
    return text, match


# ================================================================ estado em árvore: carimbo de 8 blocos
TITLES = ("Fechado nesta sessão", "Frente atual", "Tasks da frente atual", "Em andamento", "Próximos passos",
          "Backlog imediato", "Decisões e pendências humanas", "Integridade")
STEP_TOOLS = ("cs-state", "cs-session")
MAX_BLOCK_LINES = 12


def sessoes_dir(root):
    return os.path.join(root, hcore.STATE_DIR, "state", "sessoes")


def last_stamp(root):
    d = sessoes_dir(root)
    if not os.path.isdir(d):
        return None, None
    fs = sorted(f for f in os.listdir(d) if f.endswith(".json5"))
    if not fs:
        return None, None
    p = os.path.join(d, fs[-1])
    try:
        return p, hcore.read_any(p)
    except (OSError, ValueError):
        return p, None


def _trim(lines, n=MAX_BLOCK_LINES):
    lines = [" ".join(str(x).split())[:220] for x in lines if str(x).strip()]
    if len(lines) > n:
        lines = lines[:n - 1] + ["(+%d — cs-state board)" % (len(lines) - n + 1)]
    return lines


def _steps(tv):
    """Passos prontos: `cs-state …` executável como está (sem placeholder), na ordem do pipeline."""
    import engine
    import tree
    tasks = sorted([it for it in tv.items.values() if it["kind"] == "task" and tree.zone_of(it["path"]) == "state"],
                   key=lambda x: x["path"])
    sp, front = tree.front(tv)
    if front:
        pre = tree.rest_of(tv.folder(front)) + "/"
        tasks.sort(key=lambda x: (0 if tree.rest_of(x["path"]).startswith(pre) else 1, x["path"]))
    by = {"RETURNED": [], "VERIFIED": [], "ACCEPTED": [], "REJECTED": [], "BRIEFED": [], "NEW": [], "DISPATCHED": []}
    for it in tasks:
        t = tv.m2(it)
        d = engine.latest_deleg(t) if t else None
        if t is None or (it.get("reaberta") and t["status"] in tree.M2_DONE):
            by["NEW"].append((it, t, d))
        elif t["status"] in ("ACCEPTED", "DROPPED"):
            by["ACCEPTED"].append((it, t, d))
        elif d and d["state"] in ("VERIFIED", "REVIEWED"):
            by["VERIFIED"].append((it, t, d))
        elif d and d["state"] in by:
            by[d["state"]].append((it, t, d))
    S = []
    for it, t, d in by["RETURNED"]:
        S.append(("cs-state verify %s" % it["id"], "verificar a entrega de %s (%s)" % (it["id"], it.get("agent"))))
    for it, t, d in by["VERIFIED"]:
        if not engine.GUARDS["reviews_satisfy_class"](tv.ctx, "deleg", d, {}):
            S.append(("cs-state accept %s" % it["id"], "aceitar %s (verify e review por gate ok)" % it["id"]))
        else:
            S.append(("cs-state brief %s --phase review" % it["id"], "review por gate de %s (pacote de revisão)" % it["id"]))
    for it, t, d in by["ACCEPTED"]:
        S.append(('cs-state close %s --summary "entregue"' % it["id"], "fechar %s (vai para archive/)" % it["id"]))
    for it, t, d in by["REJECTED"]:
        S.append(("cs-state retry %s" % it["id"], "nova tentativa de %s com os achados da rejeição" % it["id"]))
    for it, t, d in by["BRIEFED"]:
        m = ((d or {}).get("route") or {}).get("model") or "sonnet"
        S.append(("cs-state brief %s" % it["id"], "despachar %s para %s (model %s) pela ferramenta Agent" % (
            it["id"], it.get("agent"), m)))
    for it, t, d in by["NEW"][:3]:
        S.append(("cs-state start %s" % it["id"], "iniciar %s (%s, %s)" % (it["id"], it.get("tipo"), it.get("agent"))))
    if by["DISPATCHED"]:
        ids = ", ".join(it["id"] for it, _, _ in by["DISPATCHED"])
        S.append(("cs-state board", "aguardar o retorno de %s (subagente em voo)" % ids))
    if front and not tasks and not [x for x in tv.descendants(front) if not x.get("closed")]:
        S.append(('cs-state close %s --summary "feature entregue"' % front["id"], "fechar a feature %s" % front["id"]))
    if not S:
        S.append(("cs-state board", "nada em execução: escolher a próxima frente no backlog"))
    seen, out = set(), []
    for cmd, why in S:
        if cmd in seen:
            continue
        seen.add(cmd)
        out.append("%d. `%s` — %s" % (len(out) + 1, cmd, why))
        if len(out) >= 6:
            break
    return out


def tree_blocks(root, since_seq=None):
    import engine
    import tree
    import validate
    tv = tree.load_view(root)
    p = hcore.state_paths(root)
    events, _, lh = hcore.read_chain(p["events"])
    if since_seq is None:
        _, prev = last_stamp(root)
        since_seq = int((prev or {}).get("event_count") or 0)
    B = {}
    closed = []
    for e in events[since_seq:]:
        if e.get("type") == "arvore.close" and e.get("entity") not in closed:
            closed.append(e["entity"])
    L = []
    for cid in closed:
        it = tv.get(cid)
        if it and tree.zone_of(it["path"]) == "archive":
            L.append("%s %s → %s" % (it["id"], it.get("title") or "", tree.sd_rel(it["path"])))
    B[1] = L or ["nenhum"]
    sp, front = tree.front(tv)
    head_it = front or sp
    if head_it:
        tasks = sorted(tv.same_rest(head_it, "task"), key=lambda x: x["path"])
        if not front:
            tasks = [x for x in tasks if (tv.container_of(x) or {}).get("id") == sp["id"]]
        done = sum(1 for x in tasks if tree.zone_of(x["path"]) == "archive")
        B[2] = ["%s — %s (%d/%d tasks fechadas)" % (tree.chain(tv, head_it), head_it.get("title") or "", done, len(tasks))]
        B[3] = ["%s [%s] %s — %s%s" % (x["id"], tree.status_of(tv, x), x.get("title") or "", x.get("agent") or "-",
                                       (" (wave %s)" % x["wave"]) if x.get("wave") else "") for x in tasks] or ["nenhum"]
    else:
        B[2], B[3] = ["nenhum (sem feature/sprint ativa em state/)"], ["nenhum"]
    L, H = [], []
    for it in sorted(tv.items.values(), key=lambda x: x["path"]):
        if it["kind"] != "task" or tree.zone_of(it["path"]) != "state":
            continue
        t = tv.m2(it)
        d = engine.latest_deleg(t) if t else None
        if not d:
            continue
        if d["state"] in ("DISPATCHED", "RETURNED", "VERIFIED", "REVIEWED"):
            L.append("%s → %s (%s, model %s, tentativa %s)" % (it["id"], d["agent"], d["state"],
                                                              ((d.get("model") or {}).get("name") or
                                                               (d.get("route") or {}).get("model") or "?"), t.get("attempts")))
        if d["state"] in ("ESCALATED", "ABSTAINED"):
            H.append("%s %s — %s (decisão humana: retry --decision, reroute ou drop)" % (
                it["id"], d["state"], t.get("block_reason") or t.get("reject_reason") or "aguarda decisão"))
    B[4] = L or ["nenhum"]
    B[5] = _steps(tv)
    bl = sorted([it for it in tv.items.values() if tree.zone_of(it["path"]) == "backlog"], key=lambda x: x["path"])
    B[6] = ["%s %s — %s" % (it["id"], it["kind"], it.get("title") or "") for it in bl] or ["nenhum"]
    B[7] = H or ["nenhum"]
    _, head = _git(root, ["rev-parse", "HEAD"])
    _, branch = _git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    ok, errs, _ = validate.run(root, strict=False)
    B[8] = ["HEAD %s (%s) · validate %s · %d eventos · último hash %s" % (
        (head or "sem-git")[:7], branch or "-", "OK" if ok else "FALHOU: " + "; ".join(errs[:2]), len(events), lh[:12])]
    blocos = [{"titulo": TITLES[i - 1], "linhas": _trim(B[i])} for i in range(1, 9)]
    return blocos, {"event_count": len(events), "last_event_hash": lh, "head": head or None}


def render_blocks(blocos):
    out = []
    for i, b in enumerate(blocos):
        out.append("## %d. %s" % (i + 1, b.get("titulo")))
        out += list(b.get("linhas") or [])
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def tree_save(root):
    blocos, info = tree_blocks(root)
    text = render_blocks(blocos)
    if estimate_tokens(text) > MAX_TOKENS:
        for b in blocos:
            b["linhas"] = _trim(b["linhas"], 5)
        text = render_blocks(blocos)
    d = sessoes_dir(root)
    os.makedirs(d, exist_ok=True)
    ts = hcore.now_iso()
    name = ts.replace(":", "").replace("-", "").replace(".", "")[:22]
    path = os.path.join(d, "%s.json5" % name)
    n = 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(d, "%s-%d.json5" % (name, n))
    rec = dict(info, saved_at=ts, blocos=blocos)
    hcore.write_json5(path, rec, "carimbo de sessão (cs-session save) — 8 blocos; não editar")
    return text, path


STEP_RE = __import__("re").compile(r"^\d+\. ")
CMD_RE = __import__("re").compile(r"`([^`]+)`")


def check_blocks(blocos):
    """Problemas do carimbo (vazio = íntegro): 8 blocos, nenhum vazio sem 'nenhum', todo passo com comando pronto."""
    import shlex
    P = []
    if not isinstance(blocos, list) or len(blocos) != 8:
        return ["carimbo sem os 8 blocos (%s)" % (len(blocos) if isinstance(blocos, list) else "ausente")]
    for i, b in enumerate(blocos):
        title = TITLES[i]
        if not isinstance(b, dict) or b.get("titulo") != title:
            P.append("bloco %d deveria ser '%s'" % (i + 1, title))
            continue
        lines = [str(x) for x in b.get("linhas") or [] if str(x).strip()]
        if not lines:
            P.append("%d. %s: bloco vazio — sem conteúdo escreva 'nenhum' explicitamente" % (i + 1, title))
            continue
        if i == 4:
            for ln in lines:
                m = CMD_RE.search(ln)
                cmd = m.group(1) if m else ""
                try:
                    tool = os.path.basename(shlex.split(cmd)[0]) if cmd.strip() else ""
                except ValueError:
                    tool = ""
                if not STEP_RE.match(ln) or tool not in STEP_TOOLS or "<" in cmd or "..." in cmd:
                    P.append("%d. %s: passo sem comando pronto entre crases (`cs-state …`/`cs-session …`, sem "
                             "placeholder): %r" % (i + 1, title, ln[:120]))
    return P


def tree_check(root):
    path, rec = last_stamp(root)
    if not path:
        return ["nenhum carimbo salvo (cs-session save)"]
    if not isinstance(rec, dict):
        return ["carimbo ilegível: %s" % path]
    probs = list(check_blocks(rec.get("blocos")) or [])
    last = _last_approval_ts(root)
    if last and str(rec.get("saved_at") or "")[:19] < str(last)[:19]:
        # approve.3 (efeito), igual a check_saved: o carimbo tem de ser DEPOIS da decisão do founder
        probs.append("carimbo (%s) é anterior à decisão do founder (%s): rode cs-session save de novo"
                     % (rec.get("saved_at"), last))
    return probs


def tree_session_lines(root):
    """`cs-state next` em árvore: orientação da sessão M1 (paridade com views.next_lines do caminho plano)."""
    try:
        board = hcore.load_board(root)
    except hcore.StateError:
        return []
    sess = [s for s in board.get("sessions") or [] if s.get("state") != "IDLE"]
    if not sess:
        return ["sem sessão ativa → cs-state session start --request '<pedido do usuário>'"]
    s = sess[-1]
    return ["sessão %s [%s] classe=%s" % (s["id"], s["state"], s.get("class") or "?")]


def tree_load(root):
    path, rec = last_stamp(root)
    L = []
    if not rec:
        blocos, _ = tree_blocks(root, since_seq=0)
        L.append("nenhum carimbo salvo — estado atual (cs-session save grava o carimbo):")
        return "\n".join(L) + "\n\n" + render_blocks(blocos), False
    p = hcore.state_paths(root)
    events, _, lh = hcore.read_chain(p["events"])
    match = rec.get("last_event_hash") == lh
    L.append("carimbo de %s (%s)" % (rec.get("saved_at", "?")[:19], os.path.basename(path)))
    if not match:
        new = events[int(rec.get("event_count") or 0):]
        L.append("DELTA desde o carimbo — %d evento(s) novo(s):" % len(new))
        L += ["  %s %s" % (e.get("type"), e.get("entity") or "") for e in new[-12:]]
        L.append("(o carimbo abaixo é anterior ao delta: rode cs-session save para atualizar)")
    return "\n".join(L) + "\n\n" + render_blocks(rec.get("blocos") or []), match


def estimate_tokens(text):
    return int(len(text) / 3.5 + 0.999)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cs-session")
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("save")
    s.add_argument("--did")
    s.add_argument("--next", dest="next_")
    s.add_argument("--blocked")
    s.add_argument("--decision")
    s.add_argument("--commit", action="store_true")
    s.add_argument("--check", action="store_true", help="só confere se o save existe e o carimbo bate (exit 0/1)")
    l = sub.add_parser("load")
    l.add_argument("--brief", action="store_true", help="saída JSON para o hook SessionStart")
    a = ap.parse_args(argv)
    try:
        root = hcore.resolve_root(a.root)
        if hcore.tree_mode(root) and a.cmd in ("save", "load"):
            if a.cmd == "save" and a.check:
                probs = tree_check(root)
                if probs:
                    print("carimbo NÃO íntegro:")
                    for x in probs:
                        print("  - " + x)
                    return 1
                print("carimbo íntegro (8 blocos)")
                return 0
            if a.cmd == "save":
                text, path = tree_save(root)
                print(text.rstrip())
                sys.stderr.write("(carimbo gravado em %s)\n" % os.path.relpath(path, root))
                return 0
            text, _ = tree_load(root)
            if a.brief:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}},
                                 ensure_ascii=False))
            else:
                print(text)
            return 0
        if a.cmd == "save":
            if a.check:
                ok, msg = check_saved(root)
                print(msg)
                return 0 if ok else 1
            info = save(root, a.did, a.next_, a.blocked, a.decision, a.commit)
            print("sessão salva: carimbo %s (%s)" % (info["stamp"][:12], resume_path(root)))
        elif a.cmd == "load":
            text, _ = load(root)
            if a.brief:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}, ensure_ascii=False))
            else:
                print(text)
        else:
            ap.print_help(sys.stderr)
            return 2
    except hcore.Refused as e:
        sys.stderr.write(e.render() + "\n")
        return 1
    except hcore.StateError as e:
        sys.stderr.write("cs-session: %s\n" % e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
