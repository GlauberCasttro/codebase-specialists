"""Lógica do `cs.py upgrade`: plano (não escreve nada) e aplicação (backup → ações → verificação → restauração).

Separa "atualizar o mecanismo" de "refazer o conhecimento": só as ações das migrações no intervalo
(versão do alvo, versão da skill] rodam, e cada ação CHAMA o comando existente da skill (subprocesso do cs.py):
  harness       → cs.py harness install [--platforms <advisory do run>] [--git-hook se já ligado] [--allow-outside]
  emit          → cs.py emit [--allow-outside]
  scan          → cs.py scan --layers <união das camadas> [--no-exec]
  facts-refresh → cs.py facts check --layers X; se falhar → cs.py scan --layers X
  schema        → python3 <script> --target <alvo>  (conversor idempotente de team.json5/board)
  cards|probes  → cs.py <argv>  (sempre com aviso de reexame)
  rename-dir    → move o legado DESTA skill (paths.LEGACY_STATE_DIR → paths.STATE_DIR) e reescreve os caminhos no
                  mecanismo (.swarm/bin, .swarm/harness, hooks, settings, Makefile, emitidos, .git/hooks/pre-commit);
                  dados/histórico dentro da pasta (ledgers append-only, memória, board) são movidos SEM reescrita.
                  Qualquer outra pasta (from/to diferentes) é recusada (exit 2). Pasta nova já ocupada → exit 3.
  state-tree    → python3 <skill>/scripts/harness/engine/state.py --root <alvo> migrate state-tree (o motor converte
                  o board plano legado em árvore de pastas, idempotente, com backup do board/events); sem board legado
                  nem árvore (alvo pausado antes do harness) → nada a migrar.
Nunca refeito (salvo migração explícita): entrevista, roster aprovado, cartões aprovados, memória/lições, board/eventos.

Ordem canônica das ações consolidadas (cada uma roda UMA vez mesmo que várias migrações a peçam):
rename-dir → schema → scan → facts-refresh → harness → state-tree → emit → cards → probes.

Backup (U-2): `<pasta>/tmp/` (clones de exame) e todo `.git` aninhado ficam FORA do backup e são listados em
`manifest.json5` (`excluded`); `.git/hooks/pre-commit` (raiz de fora) é guardado sob outro nome (`stored_as`).
Alvo pausado antes da etapa que instala o harness (U-1, validate.5 pendente): a verificação não exige o pre-commit
que a etapa ainda não instalou; o run.json5 (etapa corrente, status) é preservado e o alvo retoma de onde parou.
"""

import os
import re
import shutil
import subprocess
import sys

from cslib import CsError, log, paths
from stage import engine as stage_engine
from . import version as V

CS_PY = os.path.join(V.HERE, "cs.py")
ORDER = ("rename-dir", "schema", "scan", "facts-refresh", "harness", "state-tree", "emit", "cards", "probes")
ADVISORY = ("cursor", "copilot", "codex")
LEGACY = paths.LEGACY_STATE_DIR
NEW = paths.STATE_DIR
_LEGACY_RE = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(LEGACY) + r"(?![A-Za-z0-9_])")
# raízes (além de OUTSIDE_ROOTS e do manifesto do emit) onde o rename-dir reescreve o caminho legado
RENAME_ROOTS = (".gitignore", ".claude", ".cursor", ".codex", ".github")
# dentro da pasta, só o MECANISMO é reescrito; dados/histórico (ledgers com cadeia de hash, memória) não
RENAME_INSIDE = ("bin", "harness")
# raízes fora da pasta gerada que o harness/emit gerenciam (backup integral de cada uma que existir)
OUTSIDE_ROOTS = (".claude", ".cursor", ".codex", ".github", "AGENTS.md", "CLAUDE.md", "Makefile", "specialists.mk",
                 os.path.join(".git", "hooks", "pre-commit"))
VERIFY = (("harness", "selftest"), ("harness", "validate", "--strict", "--allow-empty"), ("emit", "validate"))
PRESERVED = ("entrevista (%s/interview.jsonl)" % NEW, "roster aprovado (team-approvals.jsonl)",
             "cartões aprovados (team.json5 card, cards/status.json5, approvals.jsonl)",
             "memória e lições (%s/memory/)" % NEW, "board e eventos (%s/state/board.json5, events.jsonl)" % NEW)
CMD_TIMEOUT = 1800
# conferidos byte a byte antes/depois: mudança sem ação explícita (schema|cards|probes|rename-dir) = falha
PRESERVED_PATHS = ("interview.jsonl", "team-approvals.jsonl", "approvals.jsonl", os.path.join("cards", "status.json5"),
                   os.path.join("state", "board.json5"), os.path.join("state", "events.jsonl"), "memory")
EXPLICIT_KINDS = ("schema", "cards", "probes", "rename-dir", "state-tree")
STATE_PY = os.path.join(V.HERE, "harness", "engine", "state.py")     # motor DA SKILL (nunca um script do alvo)
# U-1: subetapa que instala o harness (e o pre-commit) no alvo; antes dela feita, o pre-commit não é exigido
HARNESS_SUBSTAGE = "validate.5"
PRECOMMIT_PROBE = "pre-commit"
# U-2: fora do backup — clones de exame (com .git) e repositórios aninhados; listados em manifest.json5 `excluded`
BACKUP_EXCLUDE_TOP = ("tmp",)
BACKUP_EXCLUDE_ANY = (".git",)


# ------------------------------------------------------------------ layout (pasta nova × legado)

def legacy_root(target):
    return os.path.join(target, LEGACY)


def is_legacy(target):
    """True se o estado do alvo ainda está no diretório legado (pasta nova sem run.json5)."""
    lg = legacy_root(target)
    return (os.path.isdir(lg) and not os.path.islink(lg)
            and not os.path.isfile(os.path.join(paths.specialists_dir(target), "run.json5")))


def state_root(target):
    """Pasta de estado VIGENTE do alvo: o legado enquanto o rename-dir não rodou; senão paths.STATE_DIR."""
    return legacy_root(target) if is_legacy(target) else paths.specialists_dir(target)


def _at(target, rel):
    """Caminho absoluto de um rel escrito com o nome NOVO, onde ele está HOJE (no legado antes do rename-dir)."""
    parts = os.path.normpath(rel).split(os.sep)
    if parts and parts[0] == NEW and is_legacy(target):
        parts[0] = LEGACY
    return os.path.join(target, *parts)


def read_run(target):
    from cslib import json5io
    p = os.path.join(state_root(target), "run.json5")
    return json5io.read(p) if os.path.isfile(p) else None


def check_rename_action(a):
    """rename-dir só move o legado DESTA skill (LEGACY → NEW). Qualquer outra pasta → CsError (exit 2)."""
    extra = sorted(k for k in a if k not in ("kind", "from", "to"))
    src, dst = a.get("from", LEGACY), a.get("to", NEW)
    if extra or src != LEGACY or dst != NEW:
        raise CsError("rename-dir recusado: só renomeia %s/ → %s/ (pedido: from=%r to=%r%s)"
                      % (LEGACY, NEW, a.get("from"), a.get("to"), (", chaves extras %s" % extra) if extra else ""),
                      "rename-dir não aceita outra pasta; corrija references/migrations.json5")
    return {"kind": "rename-dir"}


def rename_conflict(target):
    """→ motivo (str) se o rename-dir não pode mover o legado sem mesclar às cegas; None se pode."""
    lg, new = legacy_root(target), paths.specialists_dir(target)
    if os.path.islink(lg):
        return "%s/ é symlink; mova à mão" % LEGACY
    if not os.path.lexists(new):
        return None
    if os.path.islink(new) or not os.path.isdir(new):
        return "%s existe e não é diretório" % NEW
    if os.path.lexists(os.path.join(new, "instance.json")):
        return ("%s/instance.json de OUTRO harness junto do legado %s/: o upgrade não mescla dois harness "
                "(veja `cs.py init --replace-harness`)" % (NEW, LEGACY))
    if os.listdir(new):
        return "%s/ já existe com conteúdo junto do legado %s/: o upgrade não mescla às cegas" % (NEW, LEGACY)
    return None


def _walk_items(base, rel_base):
    """[(abs, rel)] de arquivos e symlinks sob base (sem seguir symlinks; sem __pycache__)."""
    if not os.path.isdir(base) or os.path.islink(base):
        return [(base, rel_base)]
    out = []
    for d, dirs, files in os.walk(base):
        links = [x for x in dirs if os.path.islink(os.path.join(d, x))]
        dirs[:] = [x for x in dirs if x != "__pycache__" and x not in links]
        for f in files + links:
            p = os.path.join(d, f)
            out.append((p, rel_base + "/" + os.path.relpath(p, base).replace(os.sep, "/")))
    return out


def rename_targets(target, inside_root=None):
    """[(abs, rel)] que o rename-dir reescreve (citam o legado em texto ou no destino do symlink): o MECANISMO
    dentro da pasta (bin/, harness/) e as raízes fora dela (harness/emit/plataformas). Produto não é tocado;
    dados/histórico dentro da pasta (ledgers com cadeia de hash, memória, board) também não."""
    root_in = inside_root or state_root(target)
    cands = [(os.path.join(root_in, sub), "%s/%s" % (NEW, sub)) for sub in RENAME_INSIDE]
    for r in _dedupe_roots(list(OUTSIDE_ROOTS) + list(RENAME_ROOTS) + _emit_manifest_paths(target)):
        cands.append((os.path.join(target, r), r.replace(os.sep, "/")))
    out = {}
    for base, rel_base in cands:
        if not os.path.lexists(base):
            continue
        for p, rel in _walk_items(base, rel_base):
            if os.path.islink(p):
                if _LEGACY_RE.search(os.readlink(p)):
                    out[rel] = p
                continue
            try:
                with open(p, "rb") as fh:
                    txt = fh.read().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if _LEGACY_RE.search(txt):
                out[rel] = p
    return [(out[k], k) for k in sorted(out)]


def _rewrite(p):
    if os.path.islink(p):
        dst = _LEGACY_RE.sub(NEW, os.readlink(p))
        os.unlink(p)
        os.symlink(dst, p)
        return
    mode = os.stat(p).st_mode & 0o7777
    with open(p, "rb") as fh:
        txt = fh.read().decode("utf-8")
    tmp = p + ".cs-rename.tmp"
    with open(tmp, "wb") as fh:
        fh.write(_LEGACY_RE.sub(NEW, txt).encode("utf-8"))
    os.chmod(tmp, mode)
    os.replace(tmp, p)


def rewrite_legacy_refs(target):
    """Reescreve o caminho legado no mecanismo e fora da pasta (idempotente). → [rel reescritos]."""
    done = []
    for p, rel in rename_targets(target, paths.specialists_dir(target)):
        _rewrite(p)
        done.append(rel)
    return done


def do_rename(target, say):
    """Move LEGACY → NEW (sem mesclar) e reescreve os caminhos do mecanismo. Dados/histórico vão intactos."""
    lg, new = legacy_root(target), paths.specialists_dir(target)
    if not os.path.isdir(lg) or os.path.islink(lg) or not is_legacy(target):
        say("    rename-dir: nada a renomear (o alvo já está em %s/)" % NEW)
        return True, ""
    why = rename_conflict(target)
    if why:
        return False, "rename-dir: " + why
    if os.path.isdir(new):
        os.rmdir(new)                                    # vazio (conferido em rename_conflict)
    os.rename(lg, new)
    done = rewrite_legacy_refs(target)
    say("    rename-dir: %s/ → %s/ (%d caminho(s) reescrito(s) no mecanismo)" % (LEGACY, NEW, len(done)))
    return True, ""


def _simulate_rename(target):
    """Cópia descartável do alvo (sem .git, vendor, backups e tmp do legado) com o rename-dir aplicado: os
    --dry-run de harness/emit rodam nela, porque no alvo real o legado faria o install recusar. → (tmp, sim)."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix="cs-upgrade-plan-")
    sim = os.path.join(tmp, "t")

    def ignore(d, names):
        rel = os.path.relpath(d, target)
        skip = set(n for n in names if n in paths.VENDOR_DIRS or n == "__pycache__")
        if rel == ".":
            skip.add(".git")
        elif rel == LEGACY:
            skip |= set(["backups", "tmp"])
        return skip & set(names)
    try:
        shutil.copytree(target, sim, symlinks=True, ignore=ignore)
        gh = os.path.join(target, ".git", "hooks", "pre-commit")
        if os.path.lexists(gh):
            _copy(gh, os.path.join(sim, ".git", "hooks", "pre-commit"))
        os.rename(os.path.join(sim, LEGACY), os.path.join(sim, NEW))
        rewrite_legacy_refs(sim)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return tmp, sim


# ------------------------------------------------------------------ utilitários

def run_cs(target, argv, timeout=CMD_TIMEOUT):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=target)
    cmd = [sys.executable, CS_PY, "--target", target] + list(argv)
    try:
        p = subprocess.run(cmd, cwd=target, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", "timeout (%ds): %s" % (timeout, " ".join(argv))
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def _tail(text, n=8):
    lines = [l for l in (text or "").splitlines() if l.strip()]
    return "\n".join("      " + l for l in lines[-n:])


def _outside_block(text):
    """→ (n, [(ação, path)]) do bloco `outside:` que harness install/emit imprimem no --dry-run."""
    n, items, inside = 0, [], False
    for line in (text or "").splitlines():
        m = re.match(r"^outside: (\d+) escrita", line)
        if m:
            n, inside = int(m.group(1)), True
            continue
        if line.startswith("outside:"):
            inside = False
            continue
        if inside:
            if not line.startswith("  "):
                inside = False
                continue
            parts = line.split()
            if len(parts) >= 2:
                items.append((parts[0], parts[1]))
    return n, items


def _inside_changes(text):
    out = []
    for line in (text or "").splitlines():
        parts = line.split()
        if not parts or line.startswith("outside:"):
            continue
        if len(parts) == 1 and parts[0].startswith(NEW + "/"):
            out.append(parts[0])                       # harness install --dry-run: "  <path>"
        elif len(parts) >= 2 and parts[0] in ("create", "update", "delete", "remove") \
                and parts[1].startswith(NEW + "/") and not line.startswith("  "):
            out.append(parts[1])                       # emit --dry-run: "<ação> <path>"
    return out


def _remove(p):
    if os.path.islink(p) or os.path.isfile(p):
        os.unlink(p)
    elif os.path.isdir(p):
        shutil.rmtree(p)


def _copy(src, dst, ignore=None):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.islink(src):
        os.symlink(os.readlink(src), dst)
    elif os.path.isdir(src):
        shutil.copytree(src, dst, symlinks=True, ignore=ignore)
    else:
        shutil.copy2(src, dst, follow_symlinks=False)


def _dedupe_roots(rels):
    out = []
    for r in sorted(set(os.path.normpath(x) for x in rels if x)):
        if r.startswith("..") or os.path.isabs(r) or r.split(os.sep)[0] in (paths.SPECIALISTS_DIRNAME, LEGACY):
            continue
        if any(r == o or r.startswith(o + os.sep) for o in out):
            continue
        out.append(r)
    return out


def _emit_manifest_paths(target):
    from cslib import json5io
    m = json5io.read(os.path.join(state_root(target), "emit", "manifest.json5"), required=False) or {}
    return [f.get("path") for f in m.get("files") or [] if isinstance(f, dict) and f.get("path")]


# ------------------------------------------------------------------ plano

def consolidate(migrations):
    """Ações das migrações no intervalo, consolidadas (cada uma roda uma vez) na ordem canônica."""
    acts = {}
    for m in migrations:
        for a in m.get("actions") or []:
            k = a["kind"]
            if k in ("harness", "emit"):
                acts.setdefault(k, {"kind": k})
            elif k == "scan":
                cur = acts.setdefault(k, {"kind": k, "layers": [], "no_exec": True})
                cur["layers"] = sorted(set(cur["layers"]) | set(a["layers"]), key=lambda x: int(x[1:]))
                cur["no_exec"] = cur["no_exec"] and bool(a.get("no_exec"))
            elif k == "facts-refresh":
                cur = acts.setdefault(k, {"kind": k, "layers": []})
                lay = a.get("layers") or ["L%d" % i for i in range(11)]
                cur["layers"] = sorted(set(cur["layers"]) | set(lay), key=lambda x: int(x[1:]))
            elif k == "rename-dir":   # só existe UM rename (LEGACY → NEW): parâmetros validados antes
                acts.setdefault(k, check_rename_action(a))
            else:   # schema, cards, probes: uma por entrada distinta
                lst = acts.setdefault(k, [])
                if a not in lst:
                    lst.append(dict(a))
    out = []
    for k in ORDER:
        v = acts.get(k)
        if v is None:
            continue
        out.extend(v if isinstance(v, list) else [v])
    return out


def _harness_argv(target, run, allow_outside=False, dry=False):
    argv = ["harness", "install"]
    adv = [p for p in run.get("platforms") or [] if p in ADVISORY]
    if adv:
        argv += ["--platforms", ",".join(adv)]
    if os.path.islink(os.path.join(target, ".git", "hooks", "pre-commit")):
        argv.append("--git-hook")          # preserva a escolha já feita (no-op se o link existe)
    if dry:
        argv.append("--dry-run")
    elif allow_outside:
        argv.append("--allow-outside")
    return argv


def _script_path(script):
    if os.path.isabs(script):
        return script
    for base in (V.SKILL_ROOT, os.path.dirname(os.path.abspath(V.migrations_file()))):
        p = os.path.join(base, script)
        if os.path.isfile(p):
            return p
    return os.path.join(V.SKILL_ROOT, script)


def describe(a):
    k = a["kind"]
    if k == "harness":
        return "harness: reinstala motor/guards/wrappers (`cs.py harness install`)"
    if k == "emit":
        return "emit: reemite os artefatos por plataforma (`cs.py emit`)"
    if k == "scan":
        return "scan: refaz SÓ as camadas %s (`cs.py scan --layers %s`)" % (",".join(a["layers"]),
                                                                          ",".join(a["layers"]))
    if k == "facts-refresh":
        return "facts-refresh: confere frescor de %s e refaz só as velhas" % ",".join(a["layers"])
    if k == "schema":
        return "schema: conversor idempotente %s" % a["script"]
    if k in V.REEXAM_KINDS:
        return "%s: %s — AVISO: haverá reexame (sonda de maestria)" % (k, " ".join(a.get("argv") or []) or "(sem comando)")
    if k == "rename-dir":
        return ("rename-dir: move %s/ → %s/ e reescreve os caminhos do mecanismo (hooks, settings, Makefile, "
                "emitidos, %s/bin, %s/harness); dados e histórico vão intactos" % (LEGACY, NEW, NEW, NEW))
    if k == "state-tree":
        return ("state-tree: converte o board plano legado (%s/state/board.json5) em árvore de pastas "
                "(`cs-state migrate state-tree`; idempotente, backup do board/events em %s/backups/)" % (NEW, NEW))
    return "%s: reservado (ainda sem implementação)" % k


def _dry_runs(plan, root, run, kinds):
    """--dry-run de harness/emit em `root` (o alvo, ou a simulação do rename-dir)."""
    target = plan["target"]
    if "harness" in kinds:
        rc, out, err = run_cs(root, _harness_argv(target, run, dry=True))
        plan["dry"]["harness"] = (rc, out, err)
        if rc != 0:
            plan["conflict"] = "harness install --dry-run falhou (exit %d):\n%s" % (rc, _tail(err or out))
        plan["inside"] += _inside_changes(out)
        plan["outside"] += [("harness", act, p) for act, p in _outside_block(out)[1]]
    if "emit" in kinds:
        rc, out, err = run_cs(root, ["emit", "--dry-run"])
        plan["dry"]["emit"] = (rc, out, err)
        if rc != 0:
            plan["conflict"] = "emit --dry-run: conflito com conteúdo humano ou erro (exit %d):\n%s" % (
                rc, _tail(err or out))
        plan["inside"] += _inside_changes(out)
        plan["outside"] += [("emit", act, p) for act, p in _outside_block(out)[1]]


def build_plan(target):
    run = read_run(target)
    if run is None:
        raise CsError("alvo sem %s/run.json5 (nem %s/run.json5): não é um repositório gerado pela skill"
                      % (NEW, LEGACY),
                      "gere o time primeiro (`cs.py init` e as etapas) — upgrade só atualiza alvos existentes")
    cat = V.load_catalog()
    to_v = V.current_version()
    from_v, legacy = V.target_version(run)
    if V.parse(from_v) > V.parse(to_v):
        raise CsError("alvo na versão %s, mais nova que a skill (%s)" % (from_v, to_v),
                      "atualize a skill antes; upgrade não faz downgrade")
    migs = V.pending(cat, from_v, to_v)
    for m in migs:                       # rename-dir com outra pasta: recusa ANTES de qualquer escrita (exit 2)
        for a in m.get("actions") or []:
            if a.get("kind") == "rename-dir":
                check_rename_action(a)
    layout_legacy = is_legacy(target)
    plan = {"target": target, "from": from_v, "to": to_v, "legacy": legacy, "migrations": migs,
            "actions": consolidate(migs), "run": run, "inside": [], "outside": [], "conflict": None,
            "reexam": False, "dry": {}, "layout_legacy": layout_legacy, "renaming": False}
    for a in plan["actions"]:
        if a["kind"] in V.RESERVED_KINDS:
            raise CsError("ação %s ainda não implementada (migração %s)" % (a["kind"], to_v),
                          "cadastre a migração junto com a implementação")
        if a["kind"] in V.REEXAM_KINDS:
            plan["reexam"] = True
    kinds = set(a["kind"] for a in plan["actions"])
    plan["backup"] = backup_rel(target, from_v, to_v)
    if not migs:
        return plan
    if layout_legacy and "rename-dir" not in kinds:
        plan["conflict"] = ("o alvo está no diretório legado %s/ e nenhuma migração no intervalo tem rename-dir "
                            "(o mecanismo atual só opera em %s/)" % (LEGACY, NEW))
        return plan
    sim_tmp, root = None, target
    if layout_legacy:
        plan["renaming"] = True
        why = rename_conflict(target)
        if why:
            plan["conflict"] = "rename-dir: " + why
            return plan
        plan["inside"].append("%s/ → %s/ (move; board, eventos, memória, ledgers e aprovações intactos)"
                              % (LEGACY, NEW))
        plan["outside"] += [("rename-dir", "update", rel) for _, rel in rename_targets(target)
                            if not rel.startswith(NEW + "/")]
        sim_tmp, root = _simulate_rename(target)
    try:
        _dry_runs(plan, root, run, kinds)
    finally:
        if sim_tmp:
            shutil.rmtree(sim_tmp, ignore_errors=True)
    for a in plan["actions"]:
        if a["kind"] == "scan":
            plan["inside"] += ["%s/facts/<camadas %s>.json5 + index.json5" % (NEW, ",".join(a["layers"]))]
        elif a["kind"] == "schema":
            plan["inside"] += ["%s/team.json5 / state (conversor %s)" % (NEW, a["script"])]
        elif a["kind"] == "state-tree":
            plan["inside"] += ["%s/state/board.json5 → %s/{backlog,state,archive}/ + %s/events.jsonl "
                               "(migrate state-tree; legado em %s/backups/)" % (NEW, NEW, NEW, NEW)]
    return plan


def render_plan(plan):
    here = (LEGACY if plan.get("layout_legacy") else NEW) + "/"
    L = ["upgrade: %s" % plan["target"],
         "  versão do alvo:  %s%s" % (plan["from"], "  (partindo de repositório legado: run.json5 sem skill_version)"
                                      if plan["legacy"] else ""),
         "  versão da skill: %s" % plan["to"]]
    if not plan["migrations"]:
        L.append("  nada a fazer: o alvo já está na versão da skill")
        return "\n".join(L)
    L.append("  migrações no intervalo (%d):" % len(plan["migrations"]))
    for m in plan["migrations"]:
        L.append("    %s — %s" % (m["to"], m["why"]))
    L.append("  ações (cada uma roda uma vez, nesta ordem):")
    for a in plan["actions"]:
        L.append("    - " + describe(a))
    if plan["reexam"]:
        L.append("  AVISO: esta migração mexe em cartões/sondas — haverá reexame")
    if plan.get("renaming"):
        L.append("  pasta gerada: %s/ → %s/ (rename-dir; o restante do plano já vale para %s/)" % (LEGACY, NEW, NEW))
    L.append("  muda dentro de %s (%d):" % (here, len(plan["inside"])))
    for p in plan["inside"] or ["(nada)"]:
        L.append("    " + p)
    L.append("  fora de %s (%d; exige --allow-outside):" % (here, len(plan["outside"])))
    for src, act, p in plan["outside"] or [("", "", "(nada)")]:
        L.append("    %-8s %s%s" % (act, p, ("  [%s]" % src) if src else ""))
    L.append("  preservado (nunca refeito): " + "; ".join(PRESERVED))
    L.append("  backup: %s" % plan["backup"])
    L.append("  verificação: cs.py harness selftest; cs.py harness validate --strict --allow-empty; "
             "cs.py emit validate (falhou → restaura o backup, exit 1)")
    if plan["conflict"]:
        L.append("  BLOQUEIO: " + plan["conflict"])
    L.append("  próximo: cs.py upgrade --apply%s" % (" --allow-outside" if plan["outside"] else ""))
    return "\n".join(L)


# ------------------------------------------------------------------ backup / restauração

def backup_rel(target, from_v, to_v):
    """Rel do backup com o nome NOVO da pasta (no legado, ele nasce lá e o rename-dir o leva junto)."""
    base = os.path.join(paths.SPECIALISTS_DIRNAME, "backups", "upgrade-%s-%s" % (from_v, to_v))
    rel, i = base, 2
    while os.path.lexists(_at(target, rel)) or os.path.lexists(os.path.join(target, rel)):
        rel, i = "%s-%d" % (base, i), i + 1
    return rel


def stored_name(r):
    """Nome de `r` (raiz de fora) DENTRO do backup: nenhum segmento `.git` (U-2: `sanitize --check` reprova `.git`
    aninhado) — `.git/hooks/pre-commit` vira `dot-git/hooks/pre-commit`."""
    return "/".join("dot-git" if x == ".git" else x for x in os.path.normpath(r).split(os.sep))


def _nested_git(base, rel_base):
    """[rel] de todo `.git` (dir ou arquivo) sob base, sem descer neles."""
    out = []
    for d, dirs, files in os.walk(base):
        for n in [x for x in dirs + files if x in BACKUP_EXCLUDE_ANY]:
            out.append(rel_base + "/" + os.path.relpath(os.path.join(d, n), base).replace(os.sep, "/"))
        dirs[:] = [x for x in dirs if x not in BACKUP_EXCLUDE_ANY and not os.path.islink(os.path.join(d, x))]
    return sorted(out)


def _excluding(base, rel_base, excluded):
    """ignore do copytree: pula `.git` aninhado e registra em `excluded` (rel ao alvo)."""
    def ignore(d, names):
        skip = [n for n in names if n in BACKUP_EXCLUDE_ANY]
        for n in skip:
            excluded.append(rel_base + "/" + os.path.relpath(os.path.join(d, n), base).replace(os.sep, "/"))
        return set(skip)
    return ignore


def make_backup(target, rel, outside_paths):
    """Backup integral do mecanismo/estado, MENOS `<pasta>/tmp/` e `.git` aninhado (U-2): o que ficou de fora vai
    para manifest.json5 `excluded` (caminhos relativos ao alvo; os `.git` de dentro do tmp/ também são listados).
    → manifest das raízes de fora ({rel: existia})."""
    dest = _at(target, rel)
    sp = state_root(target)
    legacy_layout = is_legacy(target)
    sp_name = os.path.basename(sp)
    os.makedirs(os.path.join(dest, "specialists"))
    excluded = []
    for name in sorted(os.listdir(sp)):
        if name == "backups":
            continue
        src, rb = os.path.join(sp, name), "%s/%s" % (sp_name, name)
        if name in BACKUP_EXCLUDE_TOP or name in BACKUP_EXCLUDE_ANY:
            excluded.append(rb)
            if os.path.isdir(src) and not os.path.islink(src):
                excluded += _nested_git(src, rb)
            continue
        _copy(src, os.path.join(dest, "specialists", name), ignore=_excluding(src, rb, excluded))
    roots = _dedupe_roots(list(OUTSIDE_ROOTS) + list(RENAME_ROOTS) + list(outside_paths)
                          + _emit_manifest_paths(target))
    manifest, stored = {}, {}
    for r in roots:
        src = os.path.join(target, r)
        existed = os.path.lexists(src)
        manifest[r] = existed
        if existed:
            name = stored_name(r)
            if name != r.replace(os.sep, "/"):
                stored[r] = "outside/" + name
            _copy(src, os.path.join(dest, "outside", *name.split("/")),
                  ignore=_excluding(src, r.replace(os.sep, "/"), excluded))
    from cslib import json5io
    # no legado o guard de escrita (só <alvo>/STATE_DIR/) recusaria o caminho: grava sem ele (dest é do upgrade)
    json5io.dump({"outside": manifest, "layout": LEGACY if legacy_layout else NEW, "excluded": excluded,
                  "stored_as": stored},
                 os.path.join(dest, "manifest.json5"),
                 "backup do cs.py upgrade: raízes fora da pasta gerada (true = existia antes); excluded = fora do "
                 "backup (tmp/ e .git aninhado; preservados no alvo numa restauração); stored_as = nome no backup",
                 target=None if legacy_layout else target)
    return manifest


def _excluded_roots(excluded):
    """Só os excluídos de topo (um `.git` dentro de um tmp/ excluído já vai junto com ele)."""
    ex = sorted(set(excluded))
    return [e for e in ex if not any(e != o and e.startswith(o + "/") for o in ex)]


def _stash_excluded(target, sp, excluded):
    """Move para fora do caminho da restauração o que o backup não tem (tmp/, .git aninhado). → [(stash, dest)]."""
    import tempfile
    sp_name, moved = os.path.basename(sp), []
    stash_root = None
    for e in _excluded_roots(excluded):
        parts = e.split("/")
        if parts[0] in (sp_name, LEGACY, NEW):
            cur = os.path.join(sp, *parts[1:])
        else:
            cur = os.path.join(target, *parts)
        if not os.path.lexists(cur):
            continue
        if stash_root is None:
            os.makedirs(os.path.join(sp, "backups"), exist_ok=True)
            stash_root = tempfile.mkdtemp(prefix=".restore-stash-", dir=os.path.join(sp, "backups"))
        st = os.path.join(stash_root, str(len(moved)))
        os.rename(cur, st)
        moved.append((st, cur))
    return stash_root, moved


def _unstash(stash_root, moved):
    for st, cur in moved:
        if os.path.lexists(cur):
            _remove(cur)
        os.makedirs(os.path.dirname(cur), exist_ok=True)
        os.rename(st, cur)
    if stash_root:
        shutil.rmtree(stash_root, ignore_errors=True)


def restore_backup(target, rel, manifest, layout_legacy=False):
    """Restaura o backup. layout_legacy: o alvo estava no legado — desfaz o rename-dir (se já rodou) antes."""
    new = paths.specialists_dir(target)
    sp = legacy_root(target) if layout_legacy else new
    if layout_legacy and os.path.lexists(new) and new != sp:
        if not os.path.lexists(sp):
            os.rename(new, sp)
        else:
            nb, ob = os.path.join(new, "backups"), os.path.join(sp, "backups")
            if os.path.isdir(nb):
                os.makedirs(ob, exist_ok=True)
                for name in os.listdir(nb):
                    if not os.path.lexists(os.path.join(ob, name)):
                        os.rename(os.path.join(nb, name), os.path.join(ob, name))
            _remove(new)
    src = os.path.join(sp, *os.path.normpath(rel).split(os.sep)[1:])
    from cslib import json5io
    meta = json5io.read(os.path.join(src, "manifest.json5"), required=False) or {}
    stored = meta.get("stored_as") or {}
    stash_root, moved = _stash_excluded(target, sp, meta.get("excluded") or [])
    try:
        for name in os.listdir(sp):
            if name != "backups":
                _remove(os.path.join(sp, name))
        for name in sorted(os.listdir(os.path.join(src, "specialists"))):
            _copy(os.path.join(src, "specialists", name), os.path.join(sp, name))
        for r, existed in sorted(manifest.items()):
            cur = os.path.join(target, r)
            if os.path.lexists(cur):
                _remove(cur)
            if existed:
                b = os.path.join(src, *stored.get(r, "outside/" + r.replace(os.sep, "/")).split("/"))
                if not os.path.lexists(b):                        # backup antigo (sem stored_as)
                    b = os.path.join(src, "outside", r)
                _copy(b, cur)
    finally:
        _unstash(stash_root, moved)


# ------------------------------------------------------------------ preservação

def preserved_snapshot(target):
    """{relpath: sha256} de entrevista, aprovações, cartões, board/eventos e memória (o que o upgrade não refaz).
    Lê a pasta VIGENTE (o legado enquanto o rename-dir não rodou); relpaths relativos a ela (comparáveis)."""
    import hashlib
    sp = state_root(target)
    out = {}
    for rel in PRESERVED_PATHS:
        p = os.path.join(sp, rel)
        files = [p] if os.path.isfile(p) else []
        if os.path.isdir(p):
            for d, _, fs in os.walk(p):
                files += [os.path.join(d, f) for f in fs]
        for f in files:
            with open(f, "rb") as fh:
                out[os.path.relpath(f, sp)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def preserved_violations(before, after):
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


# ------------------------------------------------------------------ aplicação

def do_state_tree(target, say):
    """Ação state-tree: orquestra `cs-state migrate state-tree` do motor (o motor converte, faz backup e é
    idempotente). Sem board legado e sem árvore (alvo pausado antes do harness, nada para converter) → nada a fazer."""
    sd = paths.specialists_dir(target)
    has_board = os.path.isfile(os.path.join(sd, "state", "board.json5"))
    has_tree = os.path.isfile(os.path.join(sd, "events.jsonl"))
    if not has_board and not has_tree:
        say("    state-tree: nada a migrar (sem %s/state/board.json5)" % NEW)
        return True, ""
    env = dict(os.environ, CLAUDE_PROJECT_DIR=target)
    env.pop("CS_GUARD_OFF", None)
    cmd = [sys.executable, STATE_PY, "--root", target, "--actor", "lead", "migrate", "state-tree"]
    try:
        p = subprocess.run(cmd, cwd=target, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=CMD_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, "cs-state migrate state-tree: timeout (%ds)" % CMD_TIMEOUT
    out, err = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    if p.returncode != 0:
        return False, "cs-state migrate state-tree → exit %d\n%s" % (p.returncode, _tail(err or out))
    say("    cs-state migrate state-tree: ok%s" % ((" — " + out.strip().splitlines()[-1]) if out.strip() else ""))
    return True, ""


def _run_action(target, run, a, allow_outside, say):
    k = a["kind"]
    if k == "rename-dir":
        return do_rename(target, say)
    if k == "state-tree":
        return do_state_tree(target, say)
    if k == "harness":
        steps = [_harness_argv(target, run, allow_outside=allow_outside)]
    elif k == "emit":
        steps = [["emit"] + (["--allow-outside"] if allow_outside else [])]
    elif k == "scan":
        steps = [["scan", "--layers", ",".join(a["layers"])] + (["--no-exec"] if a.get("no_exec") else [])]
    elif k == "facts-refresh":
        rc, out, err = run_cs(target, ["facts", "check", "--layers", ",".join(a["layers"])])
        if rc == 0:
            say("    facts-refresh: fatos frescos; nada refeito")
            return True, ""
        steps = [["scan", "--layers", ",".join(a["layers"])]]
    elif k == "schema":
        script = _script_path(a["script"])
        if not os.path.isfile(script):
            return False, "conversor ausente: %s" % script
        env = dict(os.environ, CLAUDE_PROJECT_DIR=target)
        p = subprocess.run([sys.executable, script, "--target", target], cwd=target, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=CMD_TIMEOUT)
        if p.returncode != 0:
            return False, "schema %s exit %d\n%s" % (a["script"], p.returncode,
                                                     _tail(p.stderr.decode("utf-8", "replace")))
        say("    schema %s: ok" % a["script"])
        return True, ""
    elif k in V.REEXAM_KINDS:
        say("    AVISO: %s — haverá reexame dos especialistas afetados" % k)
        if not a.get("argv"):
            return True, ""
        steps = [list(a["argv"])]
    else:
        return False, "ação %s não implementada" % k
    for argv in steps:
        rc, out, err = run_cs(target, argv)
        if rc != 0:
            return False, "cs.py %s → exit %d\n%s" % (" ".join(argv), rc, _tail(err or out))
        say("    cs.py %s: ok" % " ".join(argv))
    return True, ""


def harness_stage_pending(run):
    """U-1: o alvo parou ANTES da subetapa que instala o harness (validate.5 não feita e run não finalizado)?"""
    run = run or {}
    if run.get("current_stage") == "finished":
        return False
    for st in (run.get("stages") or {}).values():
        sub = ((st or {}).get("substages") or {}).get(HARNESS_SUBSTAGE)
        if sub is not None:
            return (sub or {}).get("status") != "done"
    return bool(run.get("stages"))          # tem etapas registradas, mas nunca chegou em validate.5


def _only_precommit_failed(out):
    fails = [l for l in (out or "").splitlines() if l.startswith("FALHA")]
    return bool(fails) and all(PRECOMMIT_PROBE in l for l in fails)


def verify(target, say, run=None, hook_before=None):
    """Verificação pós-ações. `run`/`hook_before` (U-1): alvo pausado antes de validate.5 e sem pre-commit antes do
    upgrade → a sonda do pre-commit (efeito de validate.5) não reprova; qualquer outra sonda reprova normalmente.
    Alvo que já passou de validate.5 (ou que já tinha o hook) continua exigindo o pre-commit."""
    lenient = run is not None and not hook_before and harness_stage_pending(run)
    for argv in VERIFY:
        rc, out, err = run_cs(target, list(argv))
        if rc != 0 and lenient and tuple(argv) == ("harness", "selftest") and _only_precommit_failed(out):
            say("    cs.py harness selftest: ok — pre-commit não exigido: %s ainda não feita (o alvo instala ao "
                "retomar a etapa)" % HARNESS_SUBSTAGE)
            continue
        if rc != 0:
            return False, "cs.py %s → exit %d\n%s" % (" ".join(argv), rc, _tail(out + "\n" + err))
        say("    cs.py %s: ok" % " ".join(argv))
    return True, ""


def apply(target, allow_outside=False, out=None):
    """→ exit code. 0 aplicado (ou nada a fazer) · 1 falhou e restaurou · 3 recusado sem escrever."""
    out = out or sys.stdout
    say = lambda s: out.write(s + "\n")  # noqa: E731
    plan = build_plan(target)
    say(render_plan(plan))
    if not plan["migrations"]:
        return 0
    if plan["conflict"]:
        sys.stderr.write("upgrade recusado (nada escrito): %s\n" % plan["conflict"].splitlines()[0])
        return 3
    if plan["outside"] and not allow_outside:
        sys.stderr.write("upgrade recusado (nada escrito): %d escrita(s) FORA de %s/ exigem "
                         "--allow-outside (mostre a lista acima ao usuário antes)\n"
                         % (len(plan["outside"]), LEGACY if plan["layout_legacy"] else NEW))
        return 3
    rel = plan["backup"]
    hook_before = os.path.lexists(os.path.join(target, ".git", "hooks", "pre-commit"))
    manifest = make_backup(target, rel, [p for _, _, p in plan["outside"]])
    say("aplicando (backup em %s):" % rel)
    keep = preserved_snapshot(target)
    explicit = any(a["kind"] in EXPLICIT_KINDS for a in plan["actions"])
    ok, why = True, ""
    for a in plan["actions"]:
        try:
            ok, why = _run_action(target, plan["run"], a, allow_outside, say)
        except Exception as exc:  # qualquer falha de ação → restauração (nunca meio-aplicado)
            ok, why = False, "%s: %s" % (a["kind"], exc)
        if not ok:
            break
    if ok and plan["renaming"]:
        try:                         # resíduo do caminho legado deixado por ações posteriores (idempotente)
            left = rewrite_legacy_refs(target)
            if left:
                say("    rename-dir: %d caminho(s) legado(s) residual(is) reescrito(s)" % len(left))
        except Exception as exc:
            ok, why = False, "rename-dir (resíduo): %s" % exc
    if ok:
        say("verificando:")
        ok, why = verify(target, say, run=plan["run"], hook_before=hook_before)
    if ok and plan["renaming"] and os.path.lexists(legacy_root(target)):
        ok, why = False, "rename-dir: %s/ reapareceu depois das ações" % LEGACY
    if ok and not explicit:
        bad = preserved_violations(keep, preserved_snapshot(target))
        if bad:
            ok, why = False, ("o upgrade alterou conhecimento preservado sem migração explícita: %s"
                              % ", ".join(NEW + "/" + b for b in bad[:8]))
        else:
            say("    preservados intactos (entrevista, aprovações, cartões, board/eventos, memória): ok")
    if not ok:
        restore_backup(target, rel, manifest, plan["layout_legacy"])
        sys.stderr.write("upgrade FALHOU: %s\nbackup restaurado (%s); alvo continua em %s\n"
                         % (why, rel, plan["from"]))
        return 1
    run = stage_engine.read_run(target)
    hist = list(run.get("upgrade_history") or [])
    entry = {"from": plan["from"], "to": plan["to"], "at": log.now_iso(), "legacy": plan["legacy"],
             "migrations": [m["to"] for m in plan["migrations"]],
             "actions": [a["kind"] for a in plan["actions"]], "backup": rel,
             "reexam_required": plan["reexam"]}
    hist.append(entry)
    run["skill_version"] = plan["to"]
    run["upgrade_history"] = hist
    stage_engine.write_run(target, run)
    log.ledger(target, "upgrade", actor="cs.py upgrade", **{k: v for k, v in entry.items() if k != "at"})
    say("upgrade aplicado: %s → %s (run.json5 skill_version + upgrade_history)" % (plan["from"], plan["to"]))
    return 0
