"""Plano + aplicação: decide o que fazer com cada artefato e escreve atomicamente.

Garantias:
- idempotente: mesma entrada -> mesmos bytes (sem timestamp, ordem estável, LF);
- conteúdo humano fora dos blocos gerenciados nunca é alterado;
- arquivo humano (sem marcador) em caminho de arquivo gerado = conflito (proposta + diff em
  .swarm/emit/conflicts/), nada é escrito; `--force` faz backup + diff e sobrescreve;
- arquivo com conteúdo humano que recebe bloco pela 1ª vez ganha backup + diff;
- destino symlink ou fora da raiz = recusado (nem com --force).
"""
import difflib
from pathlib import Path
from cslib.paths import STATE_DIR

from emit import j5
from emit.common import GEN_TOKEN, atomic_write, find_block, merge_block, read_text, safe_dest, sha256_bytes
from emit.platforms import OWNED

EMIT_DIR = Path(STATE_DIR) / "emit"
MANIFEST = EMIT_DIR / "manifest.json5"


class Step(object):
    __slots__ = ("art", "path", "action", "reason", "old", "new")

    def __init__(self, art, path, action, reason, old, new):
        self.art, self.path, self.action, self.reason, self.old, self.new = art, path, action, reason, old, new

    def to_dict(self):
        return {"path": self.path, "action": self.action, "reason": self.reason,
                "platform": self.art.platform if self.art else None,
                "kind": self.art.kind if self.art else None}


def _diff(old, new, path):
    return "".join(difflib.unified_diff((old or "").splitlines(True), new.splitlines(True),
                                        "a/" + path, "b/" + path))


def plan(root, artifacts, platforms, force=False):
    steps = []
    for art in artifacts:
        dest, unsafe = safe_dest(root, art.path)
        if unsafe:
            steps.append(Step(art, art.path, "conflict", unsafe, None, None))
            continue
        old = read_text(dest) if dest.is_file() else None
        if art.mode == OWNED:
            new = art.content
            if old is None:
                steps.append(Step(art, art.path, "create", "novo", None, new))
            elif GEN_TOKEN not in old:
                if force:
                    steps.append(Step(art, art.path, "overwrite", "arquivo humano; --force com backup", old, new))
                else:
                    steps.append(Step(art, art.path, "conflict",
                                      "arquivo existe sem marcador de gerado (conteúdo humano)", old, new))
            elif old == new:
                steps.append(Step(art, art.path, "unchanged", "", old, new))
            else:
                steps.append(Step(art, art.path, "update", "", old, new))
        else:
            try:
                had_block = old is not None and find_block(old) is not None
            except ValueError as exc:
                steps.append(Step(art, art.path, "conflict", str(exc), old, None))
                continue
            new = merge_block(old, art.content)
            if old is None:
                steps.append(Step(art, art.path, "create", "novo (só bloco)", None, new))
            elif not had_block:
                steps.append(Step(art, art.path, "append-block",
                                  "arquivo humano sem marcadores; bloco acrescentado ao fim (backup)", old, new))
            elif old == new:
                steps.append(Step(art, art.path, "unchanged", "", old, new))
            else:
                steps.append(Step(art, art.path, "update", "só o bloco gerenciado", old, new))
    steps.extend(_prune_steps(root, artifacts, platforms))
    return steps


def _load_manifest(root):
    path = Path(root) / MANIFEST
    if not path.is_file():
        return []
    try:
        return j5.loads(read_text(path)).get("files", [])
    except ValueError:
        return []


def _prune_steps(root, artifacts, platforms):
    wanted = {a.path for a in artifacts}
    steps = []
    for entry in _load_manifest(root):
        if entry.get("platform") not in platforms or entry["path"] in wanted:
            continue
        dest, unsafe = safe_dest(root, entry["path"])
        if unsafe or not dest.is_file():
            continue
        old = read_text(dest)
        if entry.get("mode") == OWNED:
            if GEN_TOKEN in old:
                steps.append(Step(None, entry["path"], "delete", "não está mais em team.json5", old, None))
        else:
            try:
                span = find_block(old)
            except ValueError:
                continue
            if span is None:
                continue
            b, e = span
            rest = (old[:b] + old[e:]).strip("\n")
            if rest.strip():
                steps.append(Step(None, entry["path"], "remove-block", "não está mais em team.json5", old,
                                  rest + "\n"))
            else:
                steps.append(Step(None, entry["path"], "delete", "só continha o bloco", old, None))
    return steps


def has_conflict(steps):
    return any(s.action == "conflict" for s in steps)


def apply(root, steps, artifacts, platforms):
    """Escreve. Pré-condição: sem conflitos. Retorna caminhos de backup criados."""
    root = Path(root)
    backups = []
    for s in steps:
        if s.action in ("unchanged",):
            continue
        dest = root / s.path
        if s.action in ("overwrite", "append-block"):
            backups.append(_backup(root, s))
        if s.action == "delete":
            dest.unlink()
            _rmdir_if_empty(root, dest.parent)
            continue
        atomic_write(dest, s.new)
    _write_manifest(root, artifacts, platforms)
    return backups


def _rmdir_if_empty(root, d):
    """Pasta de arquivo gerado que ficou vazia depois da poda sai (ex.: `.claude/skills/<antiga>/`); com qualquer
    arquivo dentro (humano), fica. Só a pasta imediata, nunca a raiz."""
    try:
        if d != root and root in d.parents and d.is_dir() and not d.is_symlink() and not any(d.iterdir()):
            d.rmdir()
    except OSError:
        pass


def _backup(root, step):
    tag = sha256_bytes(step.old.encode("utf-8"))[:12]
    base = root / EMIT_DIR / "backups" / ("%s.%s" % (step.path, tag))
    atomic_write(Path(str(base) + ".bak"), step.old)
    atomic_write(Path(str(base) + ".diff"), _diff(step.old, step.new, step.path))
    return str(base) + ".bak"


def write_conflicts(root, steps):
    out = []
    for s in steps:
        if s.action != "conflict":
            continue
        base = Path(root) / EMIT_DIR / "conflicts" / s.path
        if s.new is not None:
            atomic_write(Path(str(base) + ".proposed"), s.new)
            atomic_write(Path(str(base) + ".diff"), _diff(s.old, s.new, s.path))
        out.append(str(base))
    return out


def _write_manifest(root, artifacts, platforms):
    keep = [e for e in _load_manifest(root) if e.get("platform") not in platforms]
    files = keep + [{"path": a.path, "platform": a.platform, "kind": a.kind, "mode": a.mode,
                     "sha256": sha256_bytes(a.content.encode("utf-8"))} for a in artifacts]
    files.sort(key=lambda e: e["path"])
    data = {"schema_version": 1, "generator": "codebase-specialists/emit", "files": files}
    path = Path(root) / MANIFEST
    text = j5.dumps(data, "manifesto do que `cs.py emit` gerou (caminho, plataforma, sha256); gerado, não edite")
    if not path.is_file() or read_text(path) != text:
        atomic_write(path, text)


def render_plan(steps, show_diff=False):
    lines = []
    width = max([len(s.action) for s in steps] + [6])
    for s in steps:
        lines.append("%-*s  %s%s" % (width, s.action, s.path, ("  (%s)" % s.reason) if s.reason else ""))
        if show_diff and s.action not in ("unchanged",) and s.new is not None:
            d = _diff(s.old, s.new, s.path)
            if d:
                lines.append(d.rstrip("\n"))
    counts = {}
    for s in steps:
        counts[s.action] = counts.get(s.action, 0) + 1
    lines.append("resumo: " + ", ".join("%s=%d" % kv for kv in sorted(counts.items())))
    return "\n".join(lines)


WRITE_ACTIONS = ("create", "update", "overwrite", "append-block", "delete", "remove-block")


def outside(steps):
    """Escritas FORA de .swarm/ (contrato `emit_fora`): o usuário vê a lista antes de --allow-outside."""
    return [s for s in steps if s.action in WRITE_ACTIONS and not s.path.startswith(".swarm/")]


def render_outside(steps):
    if not steps:
        return "outside: nenhuma escrita fora de .swarm/"
    lines = ["outside: %d escrita(s) FORA de .swarm/ (exigem --allow-outside):" % len(steps)]
    for s in steps:
        lines.append("  %-12s %s%s" % (s.action, s.path, ("  (%s)" % s.reason) if s.reason else ""))
    return "\n".join(lines)
