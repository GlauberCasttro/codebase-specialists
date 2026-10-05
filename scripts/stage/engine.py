"""Motor de etapas. Fonte única: references/stages.json5. Estado: <alvo>/.swarm/run.json5.

run.json5 (chaves desta camada; demais chaves de outros componentes são preservadas):
  {schema_version, run_id, target, commit, platforms[], skill, skill_version, upgrade_history[], current_stage,
   stages: {<etapa>: {status: pending|in_progress|done, started_at?, done_at?,
                      substages: {<id>: {status: done|failed, at, exit?, out_sha256?, detail?, answer?}}}}}
Handoff: <alvo>/.swarm/stages/<etapa>.handoff.json5 (≤ limits.handoff_max_tokens).
Tokens estimados como ceil(caracteres/4) — conservador para texto PT/EN com JSON5.
"""

import hashlib
import math
import os
import shlex
import shutil
import subprocess
import sys

from cslib import CsError, gitx, json5io, log, paths

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))           # scripts/
SKILL_ROOT = os.path.dirname(HERE)
STAGES_FILE = os.path.join(SKILL_ROOT, "references", "stages.json5")
CHECK_TIMEOUT = 900
HARNESS_BINS = {  # mesmo mapeamento de scripts/harness/templates/bin/cs-*
    "cs-state": os.path.join(HERE, "harness", "engine", "state.py"),
    "cs-session": os.path.join(HERE, "harness", "engine", "session.py"),
    "cs-route": os.path.join(HERE, "harness", "engine", "router.py"),
    "cs-mem": os.path.join(HERE, "memory", "mem.py"),
}
DEFAULT_PLATFORMS = ("claude-code", "cursor", "copilot", "codex")  # = emit.common.ALL_PLATFORMS
HEADER_RUN = "estado da execução (etapas, sub-etapas, checks) — gerado por cs.py init/stage"


def est_tokens(text):
    return int(math.ceil(len(text) / 4.0))


def load_stages(path=None):
    p = path or os.environ.get("CS_STAGES_FILE") or STAGES_FILE
    data = json5io.read(p)
    order = data.get("order") or []
    stages = data.get("stages") or {}
    if not order or set(order) != set(stages):
        raise CsError("stages.json5 inconsistente: order × stages divergem (%s)" % p,
                      "corrija references/stages.json5 (fonte única das etapas)")
    for name in order:
        ids = [s["id"] for s in stages[name].get("substages") or []]
        if not ids or len(ids) != len(set(ids)):
            raise CsError("etapa %s sem sub-etapas ou com id repetido" % name, "corrija stages.json5")
    return data


def run_path(target):
    return os.path.join(paths.specialists_dir(target), "run.json5")


def handoff_path(target, stage):
    return os.path.join(paths.specialists_dir(target), "stages", "%s.handoff.json5" % stage)


def read_run(target, required=True):
    p = run_path(target)
    if not os.path.exists(p):
        if required:
            raise CsError("run.json5 ausente (%s)" % p,
                          "rode `cs.py init` (ou `cs.py stage load init`) para criar o estado da execução")
        return None
    return json5io.read(p)


def write_run(target, run):
    json5io.dump(run, run_path(target), HEADER_RUN, target=target)


def check_platforms(platforms):
    bad = sorted(set(p for p in platforms or [] if p not in DEFAULT_PLATFORMS))
    if bad:
        raise CsError("plataforma desconhecida: %s" % ", ".join(bad),
                      "válidas: %s (default: as 4)" % ",".join(DEFAULT_PLATFORMS))
    return sorted(set(platforms or []))


def _sync_team_platforms(target, platforms):
    """team.json5 copia as plataformas do run no derive; init posterior não pode deixá-lo para trás."""
    tp = os.path.join(paths.specialists_dir(target), "team.json5")
    team = json5io.read(tp, required=False)
    if team is None or team.get("platforms") == platforms:
        return False
    team["platforms"] = platforms
    json5io.dump(team, tp, "team.json5 — roster e cartões; gerado por cs.py team (derive/card)", target=target)
    return True


def _skill_version():
    """VERSION da skill (fonte única em scripts/upgrade/version.py); o `cs.py upgrade` lê daqui a versão do alvo.
    Só a CRIAÇÃO grava: run.json5 existente sem skill_version é alvo legado e o merge do init não o mascara."""
    from upgrade import version as _v
    return _v.current_version()


def init_run(target, platforms=None, force=False, explicit=True):
    """`cs.py init` faz MERGE idempotente no run.json5 existente (iteração 3, contrato `init`): sem --force,
    nunca perde progresso; --platforms substitui as plataformas (e as do team.json5, se já derivado).
    Sem --platforms o default são as 4. `explicit=False` (criação automática por `stage load init`) não conta
    como init: `cs.py init --check` exige o `cs.py init` explícito. → (run, created, changes[])."""
    gitx.require_repo(target)
    platforms = check_platforms(platforms)
    run = read_run(target, required=False)
    if run is not None and not force:
        changes = []
        want = platforms or (None if run.get("platforms") else sorted(DEFAULT_PLATFORMS))
        if explicit and not platforms and not run.get("initialized_by"):
            want = want or run.get("platforms") or sorted(DEFAULT_PLATFORMS)
        if want is not None and want != run.get("platforms"):
            changes.append("platforms: %s → %s" % (",".join(run.get("platforms") or []) or "-", ",".join(want)))
            run["platforms"] = want
        if want is not None and _sync_team_platforms(target, run["platforms"]):
            changes.append("team.json5 platforms → %s" % ",".join(run["platforms"]))
        if explicit and not run.get("initialized_by"):
            run["initialized_by"] = "cs.py init"
            run["initialized_at"] = log.now_iso()
            changes.append("init explícito registrado")
        if changes:
            write_run(target, run)
            log.ledger(target, "init_merge", actor="cs.py init", changes=changes)
        return run, False, changes
    platforms = platforms or sorted(DEFAULT_PLATFORMS)
    commit = gitx.head(target) or ""
    seed = "%s|%s|%s" % (target, commit, log.now_iso())
    run = {"schema_version": 1, "run_id": hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16],
           "target": target, "commit": commit, "platforms": platforms,
           "skill": "codebase-specialists", "current_stage": "init", "created_at": log.now_iso(),
           "stages": {}, "skill_version": _skill_version(), "upgrade_history": []}
    if explicit:
        run["initialized_by"] = "cs.py init"
        run["initialized_at"] = log.now_iso()
    write_run(target, run)
    _sync_team_platforms(target, platforms)
    log.ledger(target, "init", actor="cs.py init", run_id=run["run_id"])
    return run, True, ["criado"]


def check_repo(target):
    """init.1 (efeito): o alvo É a raiz de um repositório git — `rev-parse --git-dir` também passa num
    subdiretório de outro repo, e aí `.swarm/` iria parar no lugar errado."""
    top = gitx.toplevel(target) if hasattr(gitx, "toplevel") else None
    if top is None:
        try:
            out = subprocess.run(["git", "-C", target, "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return False, "git indisponível"
        if out.returncode != 0:
            return False, "não é repositório git: %s" % target
        top = out.stdout.decode("utf-8", "replace").strip()
    if os.path.realpath(top) != os.path.realpath(target):
        return False, "alvo é subdiretório do repositório %s (use a raiz do repo como --target)" % top
    return True, "raiz do repositório git"


def stage_state(run, name):
    st = run.setdefault("stages", {}).setdefault(name, {})
    st.setdefault("status", "pending")
    st.setdefault("substages", {})
    return st


def find_substage(cfg, sid):
    for name in cfg["order"]:
        for s in cfg["stages"][name]["substages"]:
            if s["id"] == sid:
                return name, s
    raise CsError("sub-etapa desconhecida: %s" % sid, "veja `cs.py stage status` para os ids")


def previous_stage(cfg, name):
    i = cfg["order"].index(name)
    return cfg["order"][i - 1] if i > 0 else None


def require_known(cfg, name):
    if name not in cfg["stages"]:
        raise CsError("etapa desconhecida: %s" % name, "etapas: %s" % ", ".join(cfg["order"]))


def check_argv(check, target):
    """Converte o texto do `check` em argv (sem shell). `cs.py` → este cs.py com --target."""
    try:
        argv = shlex.split(check.replace("{target}", target))
    except ValueError as exc:
        raise CsError("check malformado: %r (%s)" % (check, exc), "corrija stages.json5")
    if not argv:
        raise CsError("check vazio", "corrija stages.json5")
    if argv[0] == "cs.py":
        return [sys.executable, os.path.join(HERE, "cs.py"), "--target", target] + argv[1:]
    if argv[0].startswith("cs-"):
        # bins do harness → o motor DA SKILL apontado ao alvo (nunca o script instalado no alvo)
        script = HARNESS_BINS.get(argv[0])
        if script and os.path.isfile(script):
            return [sys.executable, script, "--root", target] + argv[1:]
        return None
    if not shutil.which(argv[0]):
        return None
    return argv


def run_check(target, check):
    """→ (ok, exit, detail, out_sha256). Comando ausente = falha (fail-closed)."""
    argv = check_argv(check, target)
    if argv is None:
        return False, 127, "comando do check indisponível: %s" % check.split()[0], None
    env = dict(os.environ, CLAUDE_PROJECT_DIR=target, PYTHONDONTWRITEBYTECODE="1")
    try:
        p = subprocess.run(argv, cwd=target, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           stdin=subprocess.DEVNULL, env=env, timeout=CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, 124, "timeout de %ss" % CHECK_TIMEOUT, None
    out = p.stdout or b""
    tail = out.decode("utf-8", "replace").strip().splitlines()[-3:]
    return p.returncode == 0, p.returncode, " | ".join(tail)[:300], hashlib.sha256(out).hexdigest()


def mark(target, run, name, sub, ok, **kw):
    st = stage_state(run, name)
    rec = {"status": "done" if ok else "failed", "at": log.now_iso()}
    rec.update({k: v for k, v in kw.items() if v is not None})
    st["substages"][sub["id"]] = rec
    if st["status"] == "pending":
        st["status"] = "in_progress"
        st["started_at"] = log.now_iso()
    write_run(target, run)
    log.ledger(target, "stage_check", actor="cs.py stage", substage=sub["id"], ok=ok,
               exit=kw.get("exit"))
    return rec


def check_substage(target, cfg, run, sid, answer=None, note=None):
    name, sub = find_substage(cfg, sid)
    prev = previous_stage(cfg, name)
    if prev and stage_state(run, prev)["status"] != "done":
        raise CsError("etapa anterior '%s' não fechou" % prev,
                      "rode `cs.py stage done %s` antes de marcar %s" % (prev, sid))
    if sub.get("ctx") == "user" and answer is None and not sub.get("check"):
        raise CsError("%s é um toque do usuário: registre a resposta literal" % sid,
                      "cs.py stage check %s --answer \"<resposta literal>\"" % sid)
    if sub.get("check"):
        ok, code, detail, sha = run_check(target, sub["check"])
        rec = mark(target, run, name, sub, ok, exit=code, detail=detail, out_sha256=sha,
                   answer=answer, note=note)
    else:
        if answer is None and note is None:
            raise CsError("%s não tem `check` mecânico" % sid,
                          "marque com --note \"<o que foi feito>\" (ou --answer para toque do usuário)")
        rec = mark(target, run, name, sub, True, answer=answer, note=note, detail="manual")
        if answer is not None:
            from cslib import jsonio
            jsonio.append_jsonl(os.path.join(paths.specialists_dir(target), "interview.jsonl"),
                                {"ts": log.now_iso(), "substage": sid, "answer": answer}, target=target)
    return name, sub, rec


CLOSED = ("done", "skipped")


def pending(cfg, run, name):
    st = stage_state(run, name)
    return [s for s in cfg["stages"][name]["substages"]
            if (st["substages"].get(s["id"]) or {}).get("status") not in CLOSED]


def skipped(run):
    """[{id, stage, reason, at}] de toda sub-etapa pulada (caminho --fast) — vai ao status e ao relatório."""
    out = []
    for name, st in sorted((run.get("stages") or {}).items()):
        for sid, rec in sorted((st.get("substages") or {}).items()):
            if rec.get("status") == "skipped":
                out.append({"id": sid, "stage": name, "reason": rec.get("reason"), "at": rec.get("at")})
    return out


def skip_substage(target, cfg, run, sid, reason):
    """`cs.py stage skip <sub-etapa> --reason "..."` (contrato `fast`): pulo EXPLÍCITO e registrado. Só
    sub-etapas `skippable: true` em stages.json5 (o que o caminho --fast permite pular)."""
    name, sub = find_substage(cfg, sid)
    if not (reason or "").strip():
        raise CsError("--reason vazio", "diga por que pula (ex.: \"--fast pedido pelo usuário em init.2\")")
    if not sub.get("skippable"):
        allowed = [s["id"] for n in cfg["order"] for s in cfg["stages"][n]["substages"] if s.get("skippable")]
        raise CsError("%s não pode ser pulada" % sid, "puláveis (caminho --fast): %s" % ", ".join(allowed))
    prev = previous_stage(cfg, name)
    if prev and stage_state(run, prev)["status"] != "done":
        raise CsError("etapa anterior '%s' não fechou" % prev, "rode `cs.py stage done %s`" % prev)
    st = stage_state(run, name)
    st["substages"][sid] = {"status": "skipped", "reason": reason.strip(), "at": log.now_iso()}
    if st["status"] == "pending":
        st["status"] = "in_progress"
        st["started_at"] = log.now_iso()
    write_run(target, run)
    log.ledger(target, "stage_skip", actor="cs.py stage", substage=sid, reason=reason.strip())
    return name, sub


def _largest(node, path=()):
    """(tamanho_serializado, caminho, tipo) do maior item encolhível (lista >1 ou string >200)."""
    best = None
    if isinstance(node, dict):
        items = node.items()
    elif isinstance(node, list):
        items = enumerate(node)
    else:
        return None
    for k, v in items:
        if not path and k == "truncated":
            continue
        cand = None
        if isinstance(v, list) and len(v) > 1:
            cand = (len(json5io.dumps(v)), path + (k,), "list")
        elif isinstance(v, str) and len(v) > 200:
            cand = (len(v), path + (k,), "str")
        for c in (cand, _largest(v, path + (k,)) if isinstance(v, (dict, list)) else None):
            if c and (best is None or c[0] > best[0]):
                best = c
    return best


def _fit(obj, limit):
    """Encolhe a maior lista/string (em qualquer nível) até o JSON5 caber em `limit` tokens."""
    text = json5io.dumps(obj)
    truncated = set()
    while est_tokens(text) > limit:
        big = _largest(obj)
        if big is None:
            raise CsError("pacote não cabe em %d tokens mesmo truncado" % limit,
                          "reduza os campos fixos (goal/do) em stages.json5")
        _, path, kind = big
        parent = obj
        for k in path[:-1]:
            parent = parent[k]
        v = parent[path[-1]]
        parent[path[-1]] = v[:max(1, len(v) // 2)] if kind == "list" else v[:len(v) // 2] + "…"
        truncated.add(".".join(str(p) for p in path))
        obj["truncated"] = sorted(truncated)
        text = json5io.dumps(obj)
    return obj, text


def load_package(target, cfg, run, name):
    require_known(cfg, name)
    prev = previous_stage(cfg, name)
    if prev and stage_state(run, prev)["status"] != "done":
        raise CsError("etapa '%s' não pode começar: '%s' não fechou" % (name, prev),
                      "rode `cs.py stage load %s` e feche com `cs.py stage done %s`" % (prev, prev))
    st = stage_state(run, name)
    if st["status"] == "pending":
        st["status"] = "in_progress"
        st["started_at"] = log.now_iso()
    run["current_stage"] = name
    write_run(target, run)
    pend = pending(cfg, run, name)
    checklist = []
    for s in cfg["stages"][name]["substages"]:
        rec = st["substages"].get(s["id"]) or {}
        item = {"id": s["id"], "do": s["do"], "ctx": s.get("ctx", "main"),
                "state": rec.get("status", "pending")}
        if s.get("check"):
            item["check"] = s["check"]
        if s.get("per"):
            item["per"] = s["per"]
        if rec.get("status") == "failed" and rec.get("detail"):
            item["last_failure"] = rec["detail"][:160]
        if rec.get("status") == "skipped":
            item["skip_reason"] = rec.get("reason")
        checklist.append(item)
    pkg = {"stage": name, "goal": cfg["stages"][name].get("goal", ""),
           "resume_at": pend[0]["id"] if pend else None,
           "done": [s["id"] for s in cfg["stages"][name]["substages"] if s not in pend],
           "checklist": checklist,
           "next": ("cs.py stage check %s" % pend[0]["id"]) if pend else ("cs.py stage done %s" % name)}
    if prev:
        hp = handoff_path(target, prev)
        ho = json5io.read(hp, required=False)
        if ho is None:
            raise CsError("handoff da etapa '%s' ausente (%s)" % (prev, hp),
                          "rode `cs.py stage done %s` de novo para regravá-lo" % prev)
        pkg["handoff_from_%s" % prev.replace("-", "_")] = {
            k: ho.get(k) for k in ("produced", "numbers", "pending") if ho.get(k)}
        pkg["pending_inherited"] = ho.get("pending") or []
    limit = int((cfg.get("limits") or {}).get("handoff_max_tokens", 2000))
    pkg, text = _fit(pkg, limit)
    log.ledger(target, "stage_load", actor="cs.py stage", stage=name, resume_at=pkg["resume_at"],
               tokens=est_tokens(text))
    return pkg, text


def produced_summary(target):
    """Inventário compacto do que existe em .swarm/ (paths e números)."""
    sp = paths.specialists_dir(target)
    produced, numbers = [], {}
    for root, dirs, files in os.walk(sp):
        dirs[:] = sorted(d for d in dirs if d not in ("evidence",))
        for f in sorted(files):
            if f.startswith(".tmp-"):
                continue
            rel = os.path.relpath(os.path.join(root, f), os.path.dirname(sp)).replace(os.sep, "/")
            produced.append(rel)
            if f.endswith(".json5") and "/facts/" in "/" + rel and f != "index.json5":
                try:
                    numbers["facts." + f[:-6]] = len(json5io.load(os.path.join(root, f)).get("facts") or [])
                except (json5io.Json5Error, AttributeError):
                    numbers["facts." + f[:-6]] = -1
    return produced, numbers


def done_stage(target, cfg, run, name):
    require_known(cfg, name)
    prev = previous_stage(cfg, name)
    if prev and stage_state(run, prev)["status"] != "done":
        raise CsError("etapa anterior '%s' não fechou" % prev, "feche-a com `cs.py stage done %s`" % prev)
    failures = []
    for s in cfg["stages"][name]["substages"]:
        st = stage_state(run, name)
        if (st["substages"].get(s["id"]) or {}).get("status") == "skipped":
            continue  # pulo explícito registrado (stage skip): não roda o check
        if s.get("check"):
            ok, code, detail, sha = run_check(target, s["check"])
            mark(target, run, name, s, ok, exit=code, detail=detail, out_sha256=sha,
                 answer=(st["substages"].get(s["id"]) or {}).get("answer"),
                 note=(st["substages"].get(s["id"]) or {}).get("note"))
            if not ok:
                failures.append((s["id"], "check `%s` falhou (exit %s): %s" % (s["check"], code, detail)))
        elif (st["substages"].get(s["id"]) or {}).get("status") != "done":
            flag = '--answer "<resposta literal do usuário>"' if s.get("ctx") == "user" else '--note "<o que foi feito>"'
            failures.append((s["id"], "sem check mecânico e não marcado (use `cs.py stage check %s %s`)"
                             % (s["id"], flag)))
    if failures:
        log.ledger(target, "stage_done_blocked", actor="cs.py stage", stage=name,
                   failures=[f[0] for f in failures])
        return False, failures, None
    st = stage_state(run, name)
    produced, numbers = produced_summary(target)
    inherited = []
    if prev:
        ho = json5io.read(handoff_path(target, prev), required=False) or {}
        inherited = list(ho.get("pending") or [])
    notes = [{"id": sid, "note": rec.get("note") or rec.get("answer")}
             for sid, rec in sorted(st["substages"].items()) if rec.get("note") or rec.get("answer")]
    skips = [{"id": k, "reason": v.get("reason")} for k, v in sorted(st["substages"].items())
             if v.get("status") == "skipped"]
    handoff = {"schema_version": 1, "stage": name, "goal": cfg["stages"][name].get("goal", ""),
               "produced": produced, "numbers": numbers, "notes": notes, "pending": inherited,
               "commit": gitx.head(target) or ""}
    if skips:
        handoff["skipped"] = skips
    limit = int((cfg.get("limits") or {}).get("handoff_max_tokens", 2000))
    handoff, _ = _fit(handoff, limit)
    json5io.dump(handoff, handoff_path(target, name),
                 "handoff da etapa %s (≤%d tokens) — gerado por cs.py stage done" % (name, limit),
                 target=target)
    st["status"] = "done"
    st["done_at"] = log.now_iso()
    i = cfg["order"].index(name)
    run["current_stage"] = cfg["order"][i + 1] if i + 1 < len(cfg["order"]) else "finished"
    write_run(target, run)
    log.ledger(target, "stage_done", actor="cs.py stage", stage=name)
    return True, [], handoff
