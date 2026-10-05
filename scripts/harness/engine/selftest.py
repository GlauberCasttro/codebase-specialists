#!/usr/bin/env python3
"""selftest — gate G6: sondas NEGATIVAS contra os guards INSTALADOS (.claude/hooks/cs-guard.sh do alvo).

Sandbox: projeto temporário com estado sintético; o wrapper instalado roda com CLAUDE_PROJECT_DIR=sandbox
(o motor é o do alvo, resolvido pelo próprio wrapper). Também valida o estado real do alvo e a integridade
do motor (sha256 × MANIFEST.json5). Grava .swarm/state/selftest.json5.
  python3 selftest.py --root <alvo> [--drift]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
_mem = os.path.join(os.path.dirname(os.path.dirname(HERE)), "memory")
if os.path.isdir(_mem) and _mem not in sys.path:
    sys.path.insert(0, _mem)

import hcore  # noqa: E402
import j5  # noqa: E402

SB_TEAM = {"agents": [{"name": "dev-a", "kind": "dev", "territory": ["src/a/**"]},
                      {"name": "gate-r", "kind": "gate", "territory": []}]}


def integrity(root):
    h = os.path.join(root, hcore.STATE_DIR, "harness")
    mf = os.path.join(h, "MANIFEST.json5")
    if not os.path.isfile(mf):
        return ["MANIFEST.json5 ausente (reinstale)"]
    bad = []
    for fn, sha in (j5.load(mf).get("files") or {}).items():
        p = os.path.join(h, fn)
        if not os.path.isfile(p):
            bad.append("%s ausente" % fn)
        elif hcore.sha256_file(p) != sha:
            bad.append("%s alterado desde o install" % fn)
    return bad


def _git(root, *a):
    subprocess.run(["git"] + list(a), cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def make_sandbox():
    import engine
    import cmds
    sb = os.path.realpath(tempfile.mkdtemp(prefix="cs-selftest-"))
    for rel, txt in {"src/a/x.py": "X = 1\n", "src/b/y.py": "Y = 1\n", "README.md": "sb\n", ".gitignore": "__pycache__/\n"}.items():
        os.makedirs(os.path.dirname(os.path.join(sb, rel)), exist_ok=True)
        with open(os.path.join(sb, rel), "w") as f:
            f.write(txt)
    os.makedirs(os.path.join(sb, hcore.STATE_DIR))
    with open(os.path.join(sb, hcore.STATE_DIR, "team.json5"), "w") as f:
        f.write(j5.dumps(SB_TEAM))
    _git(sb, "init", "-q")
    _git(sb, "-c", "user.email=s@s", "-c", "user.name=s", "add", "-A")
    _git(sb, "-c", "user.email=s@s", "-c", "user.name=s", "commit", "-qm", "sb")
    engine.init_state(sb)
    A = "selftest"
    cmds.add_epic(sb, A, "e", "o", "m")
    cmds.level_transition(sb, A, "epic", "EPIC-1", "activate")
    cmds.add_feature(sb, A, "EPIC-1", "f", None, [])
    cmds.add_story(sb, A, "us", "FEAT-1", "s")
    # feature/story READY sem DoR seriam recusadas: o selftest usa o motor só para montar o estado de despacho
    # (feature READY: o dispatch promove feature.start pela máquina, com parent_epic_active — épico ACTIVE acima)
    b = hcore.load_board(sb)

    def force(ctx):
        return [engine.Event("feature.ready", "FEAT-1", [["set", "feature:FEAT-1", "state", "READY"]], {"args": {"selftest": True}}),
                engine.Event("story.ready", "US-1", [["set", "story:US-1", "state", "READY"]], {"args": {"selftest": True}})]
    engine.commit(sb, A, force, post=False)
    cmds.session_start(sb, A, "selftest")
    cmds.session_cmd(sb, A, "triage", {"class": "pequena", "why": "selftest"})
    cmds.session_cmd(sb, A, "plan")
    spec = {"story": "US-1", "agent": "dev-a", "title": "sonda", "goal": "sonda do selftest",
            "allowed_paths": ["src/a/x.py", "src/a/link/"], "verification_command": "true",
            "acceptance_criteria": ["AC-1|arquivo x.py contém X = 2|verification_command"],
            "briefing": {"references": ["src/a/x.py:1"], "scope": {"in": ["x"], "out": ["b: outro território"]}}}
    cmds.add_task(sb, A, spec, ready=True)
    cmds.session_cmd(sb, A, "execute")
    d = hcore.find(hcore.load_board(sb), "deleg", "T-1.d1")
    cmds.dispatch(sb, A, "T-1.d1", model=(d.get("route") or {}).get("model"), procedencia="declarada-no-despacho")
    os.symlink("/tmp", os.path.join(sb, "src", "a", "link"))
    return sb


def run_hook(wrapper, mode, sb, payload, env_extra=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=sb)
    env.pop("CS_GUARD_OFF", None)
    env.update(env_extra or {})
    p = subprocess.run(["/bin/sh", wrapper, mode], input=json.dumps(payload).encode("utf-8"), env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    return p.returncode, p.stderr.decode("utf-8", "replace")


def ledger_lines(sb):
    recs, errs, _ = hcore.read_chain(hcore.state_paths(sb)["ledger"])
    return recs


def probes(wrapper, sb):
    R = []
    sub = {"agent_id": "a1", "agent_type": "dev-a"}

    def w(path, actor=None):
        p = {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_use_id": "selftest",
             "tool_input": {"file_path": path, "content": "x"}, "session_id": "selftest", "cwd": sb}
        p.update(actor or {})
        return p

    def bash(cmd, actor=None):
        p = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_use_id": "selftest",
             "tool_input": {"command": cmd}, "session_id": "selftest", "cwd": sb}
        p.update(actor or {})
        return p

    def agent(desc, st="dev-a", model=None, actor=None):
        ti = {"description": desc, "prompt": "x", "subagent_type": st}
        if model:
            ti["model"] = model
        p = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_use_id": "selftest", "tool_input": ti,
             "session_id": "selftest", "cwd": sb}
        p.update(actor or {})
        return p

    cases = [
        ("principal escreve produto", "pre-write", w(os.path.join(sb, "src/a/x.py")), 2),
        ("subagente dentro do território (controle positivo)", "pre-write", w(os.path.join(sb, "src/a/x.py"), sub), 0),
        ("subagente fora do território", "pre-write", w(os.path.join(sb, "src/b/y.py"), sub), 2),
        ("X-01 symlink no território apontando para fora", "pre-write", w(os.path.join(sb, "src/a/link/evil.py"), sub), 2),
        ("subagente escreve no estado", "pre-write", w(os.path.join(sb, hcore.STATE_DIR, "state", "board.json5"), sub), 2),
        ("G-01 Bash apaga o próprio estado", "pre-bash", bash("rm -f .swarm/state/board.json5", sub), 2),
        ("Bash redireciona para fora", "pre-bash", bash("echo x > src/b/y.py", sub), 2),
        ("Bash não analisável", "pre-bash", bash("bash -c 'rm -rf src'", sub), 2),
        ("Bash $(...)", "pre-bash", bash("echo $(cat src/a/x.py) > src/a/x.py", sub), 2),
        ("subagente roda cs-state accept", "pre-bash", bash(".swarm/bin/cs-state accept --task T-1", sub), 2),
        ("principal se auto-aprova (review)", "pre-bash", bash("cs-state review --task T-1 --by gate-r --verdict PASS --findings x"), 2),
        ("despacho sem id de delegação", "pre-agent", agent("faz algo"), 2),
        ("subagente despacha subagente", "pre-agent", agent("T-1.d1: x", actor=sub), 2),
        ("leitura simples permitida", "pre-bash", bash("ls src", sub), 0),
    ]
    for name, mode, payload, want in cases:
        before = len(ledger_lines(sb))
        code, err = run_hook(wrapper, mode, sb, payload)
        ok = code == want
        logged = len(ledger_lines(sb)) > before
        if want == 2 and not logged:
            ok = False
        R.append({"probe": name, "expected": want, "got": code, "logged": logged, "ok": ok, "msg": err.strip()[:200]})
    before = len(ledger_lines(sb))
    code, err = run_hook(wrapper, "pre-write", sb, w(os.path.join(sb, "src/a/x.py")), {"CS_GUARD_OFF": "1"})
    recs = ledger_lines(sb)
    ks = [r for r in recs[before:] if r.get("kind") == "killswitch"]
    R.append({"probe": "kill-switch libera e registra", "expected": 0, "got": code, "logged": bool(ks),
              "ok": code == 0 and bool(ks) and bool(ks[-1].get("at"))})
    bp = hcore.state_paths(sb)["board"]
    os.rename(bp, bp + ".hidden")
    try:
        before = len(ledger_lines(sb))
        code, _ = run_hook(wrapper, "pre-write", sb, w(os.path.join(sb, hcore.STATE_DIR, "team.json5")))
        code2, _ = run_hook(wrapper, "pre-bash", sb, bash("touch src/a/x.py", sub))
        logged = len(ledger_lines(sb)) >= before + 2
        R.append({"probe": "estado ausente bloqueia (fail-closed)", "expected": 2, "got": [code, code2], "logged": logged,
                  "ok": code == 2 and code2 == 2 and logged})
    finally:
        os.rename(bp + ".hidden", bp)
    import validate
    ok1, errs, _ = validate.run(sb, strict=True)
    ev = hcore.state_paths(sb)["events"]
    with open(ev, "rb") as f:
        data = f.read()
    with open(ev, "wb") as f:
        f.write(data.replace(b'"selftest"', b'"forjado"', 1))
    ok2, errs2, _ = validate.run(sb, strict=True)
    R.append({"probe": "validate --strict verde no estado legítimo", "ok": ok1, "msg": "; ".join(errs[:3])})
    R.append({"probe": "validate --strict detecta edição manual", "ok": not ok2})
    return R


ADVISORY_PLATFORMS = ("cursor", "copilot", "codex")


def run_platforms(root):
    """Plataformas escolhidas no init (.swarm/run.json5); sem run.json5 → None (harness avulso)."""
    p = os.path.join(root, hcore.STATE_DIR, "run.json5")
    if not os.path.isfile(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return list(j5.loads(fh.read()).get("platforms") or [])
    except Exception:
        return None


def paused_before_install(root):
    """U-1: run PAUSADO antes da instalação do harness (validate.5 não concluída e run não finalizado). O pre-commit é
    instalado por validate.5: exigi-lo antes disso deixaria o selftest vermelho num alvo que só retoma depois.
    Alvo que já passou de validate.5 (ou finalizado) continua exigindo o pre-commit (anti-atalho)."""
    p = os.path.join(root, hcore.STATE_DIR, "run.json5")
    try:
        with open(p, "r", encoding="utf-8") as fh:
            r = j5.loads(fh.read())
    except Exception:
        return False
    if not isinstance(r, dict) or r.get("current_stage") in ("finished", "done", None):
        return False
    v5 = (((r.get("stages") or {}).get("validate") or {}).get("substages") or {}).get("validate.5") or {}
    return v5.get("status") != "done"


def git_hook_ok(root):
    gh = os.path.join(root, ".git", "hooks", "pre-commit")
    if not os.path.lexists(gh):
        return False
    if os.path.islink(gh):
        return os.readlink(gh).endswith("cs-precommit")
    try:
        with open(gh, "rb") as fh:
            return b"cs-precommit" in fh.read()
    except OSError:
        return False


def platform_probes(root):
    """validate.5 (efeito): o harness foi instalado para as plataformas do RUN — iteração 2: `harness install`
    sem flags deixava Cursor/Copilot/Codex sem adapter e sem pre-commit, e o selftest passava."""
    plats = run_platforms(root)
    if not plats:
        return []
    out = []
    adv = [p for p in plats if p in ADVISORY_PLATFORMS]
    for p in adv:
        f = os.path.join(root, hcore.STATE_DIR, "harness", "adapters", "%s.md" % p)
        out.append({"probe": "adapter %s instalado (plataforma do run)" % p, "ok": os.path.isfile(f),
                    "msg": "%s ausente: `cs.py harness install --platforms %s --git-hook`" % (
                        os.path.relpath(f, root), ",".join(adv))})
    if adv and os.path.isdir(os.path.join(root, ".git")) and not paused_before_install(root):
        out.append({"probe": "pre-commit → cs-precommit (E2 para %s)" % ",".join(adv), "ok": git_hook_ok(root),
                    "msg": ".git/hooks/pre-commit não chama cs-precommit: `cs.py harness install --platforms %s "
                           "--git-hook`" % ",".join(adv)})
    return out


def run(root, drift=False):
    root = os.path.realpath(root)
    res = {"at": hcore.now_iso(), "root": root, "results": []}
    integ = integrity(root)
    res["results"].append({"probe": "integridade do motor (sha256 × MANIFEST)", "ok": not integ, "msg": "; ".join(integ)})
    if drift:
        try:
            import mem
            res["memory_revalidate"] = mem.revalidate(root)
            res["memory_revalidate"]["lessons_stale"] = mem.revalidate_lessons(root)
        except Exception as e:
            res["results"].append({"probe": "revalidação da memória", "ok": False, "msg": str(e)})
    else:
        wrapper = os.path.join(root, ".claude", "hooks", "cs-guard.sh")
        if not os.path.isfile(wrapper):
            res["results"].append({"probe": "wrapper instalado", "ok": False, "msg": "%s ausente" % wrapper})
        else:
            sb = make_sandbox()
            try:
                res["results"] += probes(wrapper, sb)
            finally:
                shutil.rmtree(sb, ignore_errors=True)
            code, err = run_hook(wrapper, "pre-write", root, {"tool_name": "Write", "tool_input": {"file_path": os.path.join(root, "selftest-probe.txt")},
                                                              "session_id": "selftest", "tool_use_id": "selftest"})
            res["results"].append({"probe": "alvo real: principal escrevendo produto é bloqueado", "ok": code == 2, "got": code})
        import validate
        try:
            b = hcore.load_board(root)
            empty = sum(len(b[l]) for l in hcore.BOARD_LISTS.values()) == 0
        except hcore.StateError:
            empty = False
        ok, errs, _ = validate.run(root, strict=True, allow_empty=empty)
        res["results"].append({"probe": "validate --strict do alvo%s" % (" (allow-empty: recém-instalado)" if empty else ""),
                               "ok": ok, "msg": "; ".join(errs[:3])})
        res["results"] += platform_probes(root)
    sig = hcore.foreign_harness_signals(root)
    res["results"].append({"probe": "harness único (nenhum outro harness nem resíduo no alvo)", "ok": not sig,
                           "msg": "; ".join("%s (%s)" % x for x in sig[:5])})
    res["ok"] = all(r["ok"] for r in res["results"])
    # U-4: sem a pasta de estado (alvo legado ou não instalado) o resultado NÃO cria .swarm/ do nada (resíduo que
    # bloquearia o `cs.py upgrade`): só imprime.
    if os.path.isdir(os.path.join(root, hcore.STATE_DIR)):
        try:
            hcore.write_json5(hcore.state_paths(root)["selftest"], res, "resultado do selftest (G6) — escrito por selftest.py")
        except OSError:
            pass
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(prog="selftest")
    ap.add_argument("--root")
    ap.add_argument("--drift", action="store_true")
    a = ap.parse_args(argv)
    root = hcore.resolve_root(a.root)
    res = run(root, a.drift)
    for r in res["results"]:
        print("%s %s%s" % ("OK  " if r["ok"] else "FALHA", r["probe"], ("  — " + r["msg"]) if r.get("msg") and not r["ok"] else ""))
    print("G6 %s" % ("VERDE" if res["ok"] else "VERMELHO"))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
