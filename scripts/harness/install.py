"""install — `cs.py harness install`: copia o motor para <alvo>/.swarm/harness/, gera wrappers, mescla
.claude/settings.json (backup, sem destruir chaves), inicia o estado, gera specialists.mk e adapters advisory.
Idempotente: rodar de novo só atualiza o que mudou (e diz o quê).

Escrita FORA de .swarm/ (contrato `emit_fora`, igual ao `cs.py emit`; iteração 4): `.claude/settings.json`,
`.claude/hooks/cs-guard.sh`, `specialists.mk`, o bloco no `Makefile` e `.git/hooks/pre-commit`. O install primeiro
calcula o plano sem escrever (`--dry-run` só mostra); se houver escrita fora e faltar `--allow-outside`, nada é
escrito (nem dentro de .swarm/). Reinstalar sem mudança fora não pede a flag."""
import json
import os
import re
import shutil
import stat
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "engine")
MEMORY = os.path.join(os.path.dirname(HERE), "memory")
TEMPLATES = os.path.join(HERE, "templates")
for _p in (ENGINE, MEMORY):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hcore  # noqa: E402
import j5  # noqa: E402

ENGINE_FILES = ["hcore.py", "j5.py", "engine.py", "cmds.py", "views.py", "brief.py", "router.py", "autonomy.py",
                "session.py", "state.py", "validate.py", "guard.py", "bashscan.py", "selftest.py",
                "envfail.py", "tree.py", "auto.py"]
DATA_FILES = [(os.path.join(HERE, "machines.json5"), "machines.json5"), (os.path.join(HERE, "routing.json5"), "routing.json5"),
              (os.path.join(MEMORY, "mem.py"), "mem.py")]
BINS = ["cs-state", "cs-mem", "cs-session", "cs-route", "cs-precommit", "cs-auto"]
HOOK_CMD = '"$CLAUDE_PROJECT_DIR"/.claude/hooks/cs-guard.sh %s'
HOOKS = [
    ("PreToolUse", "Write|Edit|MultiEdit|NotebookEdit", "pre-write", 30),
    ("PreToolUse", "Bash", "pre-bash", 30),
    ("PreToolUse", "Agent|Task", "pre-agent", 60),
    ("PostToolUse", "Write|Edit|MultiEdit", "post-edit", 120),
    ("SubagentStart", None, "subagent-start", 30),
    ("SubagentStop", None, "subagent-stop", 30),
    ("Stop", None, "stop", 30),
    ("UserPromptSubmit", None, "user-prompt", 10),
    ("SessionStart", None, "session-start", 30),
    ("PreCompact", None, "pre-compact", 30),
]
MAKE_TARGETS = [
    ("next", "cs-state next", "próxima ação permitida"),
    ("board", "cs-state board", "árvore épico→feature→story→task com rollup"),
    ("add-epic", "cs-state add epic $(ARGS)", "ARGS='--title .. --objective .. --metric ..'"),
    ("add-feature", "cs-state add feature $(ARGS)", "ARGS='--epic EPIC-n --title .. --spec .. --accept-cmd ..'"),
    ("add-story", "cs-state add story $(ARGS)", "ARGS='--type us|bug|fix --feature FEAT-n --title ..'"),
    ("sprint-plan", "cs-state sprint plan $(ARGS)", "ARGS='--goal .. --budget tasks=N,attempts=2,minutes=M --stories US-1,BUG-2'"),
    ("sprint-start", "cs-state sprint start $(ARGS)", ""),
    ("sprint-review", "cs-state sprint review $(ARGS)", ""),
    ("sprint-close", "cs-state sprint close $(ARGS)", ""),
    ("brief", "cs-state brief --task $(ID) $(ARGS)", "ID=<task>"),
    ("dispatch", "cs-state dispatch --task $(ID) --manual $(ARGS)", "ID=<task> ARGS='--model sonnet'"),
    ("verify", "cs-state verify --task $(ID)", "ID=<task>"),
    ("review", "cs-state review --task $(ID) $(ARGS)", "ID=<task> ARGS='--by gate --verdict PASS --findings ..'"),
    ("accept", "cs-state accept --task $(ID)", "ID=<task>"),
    ("reject", "cs-state reject --task $(ID) $(ARGS)", "ID=<task> ARGS='--reason ..'"),
    ("abstain", "cs-state abstain --task $(ID) $(ARGS)", "ID=<task> ARGS='--kind spec_ambiguous --reason ..'"),
    ("session-save", "cs-session save $(ARGS)", "ARGS='--did .. --next ..'"),
    ("session-load", "cs-session load", ""),
    ("mem", "cs-mem search \"$(Q)\"", "Q='<consulta>'"),
    ("autonomy-start", "cs-state autonomy start --feature $(FEAT) $(ARGS)", "FEAT=FEAT-n ARGS='--budget tasks=6,attempts=2,minutes=90'"),
    ("autonomy-status", "cs-state autonomy status", ""),
    ("selftest", "python3 .swarm/harness/selftest.py --root .", "sondas negativas dos guards (G6)"),
    ("validate", "python3 .swarm/harness/validate.py --strict --allow-empty --root .", "validador do estado"),
    ("drift", "python3 .swarm/harness/selftest.py --drift --root .", "integridade do motor + revalidação da memória"),
]
MK_BEGIN = "# >>> codebase-specialists (bloco gerenciado; não editar) >>>"
MK_END = "# <<< codebase-specialists <<<"


_PLAN = None  # dry-run: {"root", "steps": [{path, action, reason}]} em vez de escrever


class OutsideRefused(hcore.StateError):
    """Escrita fora de .swarm/ sem --allow-outside: nada foi escrito."""

    def __init__(self, steps):
        self.steps = steps
        hcore.StateError.__init__(self, "%d escrita(s) FORA de .swarm/ exigem --allow-outside" % len(steps))


class ForeignHarness(OutsideRefused):
    """Outro harness (ou o diretório legado desta skill) no alvo: harness único — nada foi escrito (exit 3)."""

    def __init__(self, signals):
        steps = [{"path": rel, "action": "harness", "reason": why + " — substitua com `cs.py harness install "
                  "--replace-harness --allow-outside` (backup em .swarm/backups/harness-anterior/) ou, se for o "
                  "legado desta skill, `cs.py upgrade`"} for rel, why in signals]
        OutsideRefused.__init__(self, steps)
        self.signals = signals


def _plan(path, action, reason=""):
    _PLAN["steps"].append({"path": os.path.relpath(path, _PLAN["root"]), "action": action, "reason": reason})


def _write(path, data, mode=None, reason=""):
    old = None
    if os.path.isfile(path):
        with open(path, "rb") as f:
            old = f.read()
    if old == data:
        return False
    if _PLAN is not None:
        _plan(path, "update" if old is not None else "create", reason)
        return True
    hcore.atomic_write_bytes(path, data)
    if mode:
        os.chmod(path, mode)
    return True


def _read(path):
    with open(path, "rb") as f:
        return f.read()


def copy_engine(root, changes):
    dst = os.path.join(root, hcore.STATE_DIR, "harness")
    manifest = {}
    for fn in ENGINE_FILES:
        data = _read(os.path.join(ENGINE, fn))
        if _write(os.path.join(dst, fn), data, 0o644):
            changes.append(hcore.STATE_DIR + "/harness/" + fn)
        manifest[fn] = hcore.sha256_bytes(data)
    for src, name in DATA_FILES:
        data = _read(src)
        if _write(os.path.join(dst, name), data, 0o644):
            changes.append(hcore.STATE_DIR + "/harness/" + name)
        manifest[name] = hcore.sha256_bytes(data)
    _write(os.path.join(dst, "MANIFEST.json5"), j5.dumps({"files": manifest},
           header="sha256 dos arquivos do motor instalado (drift/selftest)").encode("utf-8"))
    return manifest


def ops_checks(root):
    """post_edit_checks a partir dos comandos verificados (facts/operations.json5) — lint/type-check."""
    p = hcore.state_paths(root)
    f = hcore.first_existing(os.path.join(p["facts_dir"], "operations.json5"), os.path.join(p["facts_dir"], "operations.json"))
    out = []
    if not f:
        return out
    try:
        data = hcore.read_any(f)
    except (OSError, ValueError):
        return out
    items = data if isinstance(data, list) else (data.get("commands") or data.get("facts") or data.get("operations") or [])
    for it in items:
        if not isinstance(it, dict):
            continue
        kind = (it.get("kind") or it.get("category") or it.get("type") or "").lower()
        cmd = it.get("cmd") or it.get("command")
        status = it.get("status") or it.get("state")
        if kind in ("lint", "typecheck", "type-check", "format-check", "check") and isinstance(cmd, str) and status == "verified":
            import shlex
            try:
                argv = shlex.split(cmd)
            except ValueError:
                continue
            out.append({"name": kind, "glob": it.get("scope") or ["**"], "argv": argv, "timeout_s": 60})
    return out[:4]


def write_config(root, changes):
    p = hcore.state_paths(root)["config"]
    cfg = {}
    if os.path.isfile(p):
        cfg = j5.load(p)
    added = False
    for k, v in hcore.DEFAULT_CONFIG.items():
        if k not in cfg:
            cfg[k] = v
            added = True
    if not cfg.get("post_edit_checks"):
        chk = ops_checks(root)
        if chk:
            cfg["post_edit_checks"] = chk
            added = True
    if (added or not os.path.isfile(p)) and _PLAN is not None:
        _plan(p, "update" if os.path.isfile(p) else "create")
        changes.append(hcore.STATE_DIR + "/harness/config.json5")
    elif added or not os.path.isfile(p):
        hcore.write_json5(p, cfg, "config.json5 do harness (protegido: só reinstalação ou edição humana fora do agente)")
        changes.append(hcore.STATE_DIR + "/harness/config.json5")


def write_bins(root, changes):
    b = os.path.join(root, hcore.STATE_DIR, "bin")
    for n in BINS:
        if _write(os.path.join(b, n), _read(os.path.join(TEMPLATES, "bin", n)), 0o755):
            changes.append(hcore.STATE_DIR + "/bin/" + n)
    if _write(os.path.join(root, ".claude", "hooks", "cs-guard.sh"), _read(os.path.join(TEMPLATES, "cs-guard.sh")), 0o755,
              reason="wrapper dos hooks do Claude Code (--no-settings não o evita)"):
        changes.append(".claude/hooks/cs-guard.sh")


def merge_settings(root, changes, path_env=False):
    p = os.path.join(root, ".claude", "settings.json")
    cur = {}
    if os.path.isfile(p):
        try:
            cur = json.loads(_read(p).decode("utf-8"))
        except ValueError as e:
            raise hcore.StateError("settings.json inválido (%s): não sobrescrevo; corrija à mão" % e)
        if not isinstance(cur, dict):
            raise hcore.StateError("settings.json não é objeto")
    new = json.loads(json.dumps(cur))
    hooks = new.setdefault("hooks", {})
    for ev in list(hooks):
        kept = []
        for grp in hooks[ev] or []:
            hs = [h for h in grp.get("hooks") or [] if "cs-guard.sh" not in (h.get("command") or "")]
            if hs:
                g2 = dict(grp)
                g2["hooks"] = hs
                kept.append(g2)
        hooks[ev] = kept
    for ev, matcher, mode, timeout in HOOKS:
        grp = {"hooks": [{"type": "command", "command": HOOK_CMD % mode, "timeout": timeout}]}
        if matcher:
            grp = dict({"matcher": matcher}, **grp)
        hooks.setdefault(ev, []).append(grp)
    env = new.setdefault("env", {})
    env.setdefault("CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH", "1")
    # env.PATH desligado por padrão: congela o PATH da instalação e não há garantia documentada de que chegue
    # a hooks/Bash (só após trust do workspace). Os artefatos chamam `.swarm/bin/cs-*` por caminho.
    if path_env and "PATH" not in env:
        env["PATH"] = os.path.join(root, hcore.STATE_DIR, "bin") + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")
    if new != cur:
        if os.path.isfile(p) and _PLAN is None:
            shutil.copy2(p, p + ".bak-%s" % time.strftime("%Y%m%d%H%M%S"))
        _write(p, (json.dumps(new, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
               reason="merge dos hooks cs-guard%s (evite: --no-settings)" % (" + backup .bak-*" if os.path.isfile(p)
                                                                              else ""))
        changes.append(".claude/settings.json")


def _existing_targets(text):
    return set(m.group(1) for m in re.finditer(r"^([A-Za-z0-9_.\-]+)\s*:(?!=)", text, re.M))


def write_makefile(root, changes):
    mk = os.path.join(root, "Makefile")
    existing = ""
    if os.path.isfile(mk):
        existing = _read(mk).decode("utf-8", "replace")
    outside = existing
    if MK_BEGIN in existing:
        a = existing.index(MK_BEGIN)
        b = existing.find(MK_END, a)
        outside = existing[:a] + (existing[b + len(MK_END):] if b >= 0 else "")
    taken = _existing_targets(outside)
    names = []
    lines = ["# specialists.mk — alvos finos do harness: cada alvo chama o script e nada mais (gerado; não editar).",
             "# Compatível com GNU make 3.81+ e BSD make. Variáveis: ID=<task> FEAT=<feature> Q=<consulta> ARGS='<flags>'.",
             "CS_BIN = .swarm/bin", ""]
    for name, cmd, helptxt in MAKE_TARGETS:
        tname = ("cs-" + name) if name in taken or name == "help" and "help" in taken else name
        names.append((tname, helptxt))
        full = cmd if cmd.startswith("python3") else "$(CS_BIN)/" + cmd
        lines += ["%s:" % tname, "\t@%s" % full, ""]
    help_name = "cs-help" if "help" in taken else "help"
    lines += ["%s:" % help_name]
    for tname, helptxt in names + [(help_name, "esta lista")]:
        lines.append("\t@echo '  make %-16s %s'" % (tname, helptxt.replace("'", "")))
    lines += ["", ".PHONY: %s %s" % (" ".join(n for n, _ in names), help_name), ""]
    if _write(os.path.join(root, "specialists.mk"), "\n".join(lines).encode("utf-8"),
              reason="alvos make do harness (evite: --no-makefile)"):
        changes.append("specialists.mk")
    block = "%s\ninclude specialists.mk\n%s\n" % (MK_BEGIN, MK_END)
    if not existing:
        content = "# Makefile mínimo gerado por codebase-specialists\n" + block
    elif MK_BEGIN in existing:
        a = existing.index(MK_BEGIN)
        b = existing.find(MK_END, a)
        content = existing[:a] + block.rstrip("\n") + (existing[b + len(MK_END):] if b >= 0 else "\n")
    else:
        content = existing + ("" if existing.endswith("\n") else "\n") + "\n" + block
    if _write(mk, content.encode("utf-8"), reason="bloco gerenciado `include specialists.mk` (evite: --no-makefile)"):
        changes.append("Makefile (bloco gerenciado)")
    return dict(names)


ADVISORY = {
    "cursor": ("Cursor", "E1 (+E2 com cs-precommit)", ".cursor/rules (emitido) instrui; não instalamos hooks do Cursor — os guards "
               "de pré-execução deste harness são do Claude Code"),
    "copilot": ("GitHub Copilot", "E1 (+E2 com cs-precommit/CI)", ".github/copilot-instructions.md instrui; sem hooks de pré-execução"),
    "codex": ("Codex / AGENTS.md", "E1 (+E2 com cs-precommit/CI)", "AGENTS.md instrui; sem hooks de pré-execução"),
}


def write_adapters(root, platforms, changes):
    d = os.path.join(root, hcore.STATE_DIR, "harness", "adapters")
    for p in platforms or []:
        if p not in ADVISORY:
            continue
        name, level, how = ADVISORY[p]
        txt = """# Harness codebase-specialists em %s — modo ADVISORY (enforcement %s)

%s. O estado e as regras são os mesmos do Claude Code; muda só QUEM impede o erro.

Protocolo (rode no terminal; a máquina de estado é só o script):
1. `.swarm/bin/cs-state next` — a próxima ação permitida.
2. Antes de escrever: `.swarm/bin/cs-state brief --task <id>` — escopo, checklist, invariantes (mesmo pacote do hook).
3. Escreva SÓ em `allowed_paths` da task; nunca em `.swarm/state`, `.swarm/harness`, `.claude/`.
4. Entregue: `cs-state submit --task <id> --files-changed ... --check ... --risk ...`; o orquestrador roda `cs-state verify`
   (executa o comando e confere git diff × allowed_paths — pega escrita fora do território depois do fato).
5. Ative o pre-commit: `ln -s ../../.swarm/bin/cs-precommit .git/hooks/pre-commit` (E2: bloqueia o commit).

Honestidade: sem hooks de pré-execução nada impede o agente de escrever fora do território no momento da escrita; o
`verify` e o `cs-precommit` detectam e reprovam depois. Ver references/harness.md (escada E0–E3).
""" % (name, level, how)
        if _write(os.path.join(d, "%s.md" % p), txt.encode("utf-8")):
            changes.append(hcore.STATE_DIR + "/harness/adapters/%s.md" % p)


def init_target_state(root):
    """Estado do alvo. Alvo NOVO nasce em ÁRVORE (backlog/ state/ archive/ + events.jsonl com 1º evento `init`
    layout tree; sem board plano, sem migrate). Já em árvore: nada. Board plano legado: preservado como está
    (a migração é explícita: `cs-state migrate state-tree`). → True se criou."""
    import engine
    import tree
    legacy = os.path.join(root, hcore.STATE_DIR, "state", "board.json5")
    if hcore.tree_mode(root):
        return False
    if os.path.isfile(legacy):
        return engine.init_state(root)
    return bool(tree.init(root))


def _apply(root, platforms, settings, makefile, git_hook, path_env):
    dry = _PLAN is not None
    changes = []
    copy_engine(root, changes)
    write_config(root, changes)
    write_bins(root, changes)
    if settings:
        merge_settings(root, changes, path_env)
    if dry:
        if not os.path.isdir(os.path.join(root, hcore.STATE_DIR, "state")):
            changes.append(hcore.STATE_DIR + "/state (init)")
    else:
        sys.path.insert(0, os.path.join(root, hcore.STATE_DIR, "harness"))
        if init_target_state(root):
            changes.append(hcore.STATE_DIR + "/state (init)")
        os.makedirs(os.path.join(root, hcore.STATE_DIR, "memory", "agents"), exist_ok=True)
    targets = write_makefile(root, changes) if makefile else {}
    write_adapters(root, platforms, changes)
    if git_hook:
        gh = os.path.join(root, ".git", "hooks", "pre-commit")
        if os.path.isdir(os.path.dirname(gh)) and not os.path.lexists(gh):
            if dry:
                _plan(gh, "create", "symlink → .swarm/bin/cs-precommit (evite: sem --git-hook)")
            else:
                os.symlink(os.path.join("..", "..", hcore.STATE_DIR, "bin", "cs-precommit"), gh)
            changes.append(".git/hooks/pre-commit")
    return changes, targets


def plan(root, platforms=None, settings=True, makefile=True, git_hook=False, path_env=False):
    """→ [{path, action, reason}] de TUDO que o install escreveria (nada é escrito)."""
    global _PLAN
    _PLAN = {"root": os.path.realpath(root), "steps": []}
    try:
        _apply(_PLAN["root"], platforms, settings, makefile, git_hook, path_env)
        return list(_PLAN["steps"])
    finally:
        _PLAN = None


def outside(steps):
    return [s for s in steps if not s["path"].startswith(hcore.STATE_DIR + "/")]


def render_outside(steps):
    if not steps:
        return "outside: nenhuma escrita fora de .swarm/"
    lines = ["outside: %d escrita(s) FORA de .swarm/ (exigem --allow-outside):" % len(steps)]
    for s in steps:
        lines.append("  %-8s %s%s" % (s["action"], s["path"], ("  (%s)" % s["reason"]) if s.get("reason") else ""))
    return "\n".join(lines)


def install(root, platforms=None, settings=True, makefile=True, git_hook=False, path_env=False, dry_run=False,
            allow_outside=False):
    root = os.path.realpath(root)
    skill_root = os.path.realpath(os.path.dirname(os.path.dirname(HERE)))
    if root == skill_root or root.startswith(skill_root + os.sep):
        raise hcore.StateError("alvo é a própria skill: recusado")
    if not dry_run:
        sig = hcore.foreign_harness_signals(root)
        if sig:
            raise ForeignHarness(sig)
    steps = plan(root, platforms, settings, makefile, git_hook, path_env)
    out = outside(steps)
    if dry_run:
        return {"root": root, "changes": [s["path"] for s in steps], "outside": out, "dry_run": True,
                "make_targets": []}
    if out and not allow_outside:
        raise OutsideRefused(out)
    changes, targets = _apply(root, platforms, settings, makefile, git_hook, path_env)
    return {"root": root, "changes": changes, "outside": out, "make_targets": sorted(targets)}
