"""Saneamento da pasta da skill ao fim de todo init (approve.4, DEC-SANITIZE de 2026-10-03).

Evidência (repositório-piloto (projeto-legado), 2026-10-03): 91 MB de lixo em `<pasta>/tmp/` — 15 cópias de exame com `.git`
próprio, pacotes de entrada, rascunhos, 4 scripts de contorno do executor — e `harness/__pycache__`, sem
`.gitignore`: um `git add .` commitaria tudo e 15 repositórios aninhados.

- `plan(target)`   → o que seria apagado (com tamanhos) e o que seria gravado; não escreve nada.
- `apply(target)`  → lista os scripts deixados em `tmp/` como DEFEITO (contorno manual), apaga `tmp/` inteiro e
                     todo `__pycache__` sob a pasta, grava `<pasta>/.gitignore` e `<pasta>/sanitize.json5`.
- `check(target)`  → efeito (check de approve.4): `tmp/` ausente ou vazio, `.gitignore` com as 4 entradas, nenhum
                     `.git` aninhado fora de `tmp/`. `__pycache__` recriado depois (ignorado) e produto alterado
                     viram aviso: o repo pode ter trabalho do dono não commitado.
"""
import os
import shutil
import stat

from cslib import gitx, json5io, jsonio, log, paths
from cslib.errors import CsError

# Nome da pasta da skill num lugar só (o rename para .swarm/ troca a constante em cslib.paths).
DIRNAME = paths.STATE_DIR
GITIGNORE_ENTRIES = ("tmp/", "memory/index/", "__pycache__/", "backups/")
SCRIPT_EXT = frozenset([".py", ".sh", ".bash", ".zsh", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl", ".ps1"])
# Escritas gerenciadas fora da pasta além do manifesto do emit: Makefile/CLAUDE.md (blocos gerenciados) e o
# que `harness install` grava (settings, hook do guard, specialists.mk).
MANAGED_OUTSIDE = ("Makefile", "CLAUDE.md", "specialists.mk", ".claude/settings.json", ".claude/hooks/cs-guard.sh")
RECORD = "sanitize.json5"


def skill_dir(target):
    return os.path.join(os.path.realpath(target), DIRNAME)


def _require(target):
    sp = skill_dir(target)
    if not os.path.isdir(sp):
        raise CsError("nada a sanear: %s/ não existe em %s" % (DIRNAME, target),
                      "rode o init da skill antes (`cs.py init`)")
    return sp


def size_of(path):
    """Bytes de um arquivo/árvore (lstat: symlink conta o link, nunca o destino)."""
    try:
        st = os.lstat(path)
    except OSError:
        return 0
    if not stat.S_ISDIR(st.st_mode):
        return st.st_size
    total = 0
    for dp, dn, fn in os.walk(path, followlinks=False):
        for n in fn + [d for d in dn if os.path.islink(os.path.join(dp, d))]:
            try:
                total += os.lstat(os.path.join(dp, n)).st_size
            except OSError:
                pass
    return total


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0
    return "%d B" % n


def _rel(target, path):
    return os.path.relpath(path, os.path.realpath(target)).replace(os.sep, "/")


def _is_script(path):
    if os.path.splitext(path)[1].lower() in SCRIPT_EXT:
        return True
    try:
        if os.lstat(path).st_mode & 0o111:
            return True
        with open(path, "rb") as fh:
            return fh.read(2) == b"#!"
    except OSError:
        return False


def workarounds(target):
    """Scripts deixados em `tmp/` = contorno manual do executor (DEFEITO da execução). Cópias de repositório
    (diretório com `.git`, `<exame>/repo/`) são do produto examinado, não do executor: não entram."""
    tmp = os.path.join(skill_dir(target), "tmp")
    out = []
    if not os.path.isdir(tmp) or os.path.islink(tmp):
        return out
    for dp, dn, fn in os.walk(tmp, followlinks=False):
        if ".git" in dn or ".git" in fn or (os.path.basename(dp) == "repo"
                                            and os.path.isfile(os.path.join(os.path.dirname(dp), "exam.json5"))):
            dn[:] = []
            continue
        dn.sort()
        for n in sorted(fn):
            p = os.path.join(dp, n)
            if not os.path.islink(p) and _is_script(p):
                out.append({"path": _rel(target, p), "bytes": size_of(p)})
    return out


def _walk_skill(target):
    """(dirpath, dirnames) sob a pasta da skill, sem descer em `tmp/` (apagada inteira) nem em symlinks."""
    sp = skill_dir(target)
    tmp = os.path.join(sp, "tmp")
    for dp, dn, fn in os.walk(sp, followlinks=False):
        if dp == sp:
            dn[:] = [d for d in dn if os.path.join(sp, d) != tmp]
        dn.sort()
        yield dp, dn, fn


def pycaches(target):
    out = []
    for dp, dn, _ in _walk_skill(target):
        for d in list(dn):
            if d == "__pycache__":
                p = os.path.join(dp, d)
                out.append({"path": _rel(target, p) + "/", "bytes": size_of(p)})
                dn.remove(d)
    return out


def nested_git(target, status=None):
    """`.git` aninhado fora de `tmp/`: sob a pasta da skill e repositório embutido não rastreado no git status."""
    out = []
    for dp, dn, fn in _walk_skill(target):
        if ".git" in dn or ".git" in fn:
            out.append(_rel(target, os.path.join(dp, ".git")))
            if ".git" in dn:
                dn.remove(".git")
    tmp_rel = DIRNAME + "/tmp/"
    for code, rel in status or []:
        if code == "??" and rel.endswith("/") and not rel.startswith(tmp_rel):
            if os.path.exists(os.path.join(target, rel, ".git")):
                g = rel + ".git"
                if g not in out:
                    out.append(g)
    return sorted(out)


def gitignore_state(target):
    p = os.path.join(skill_dir(target), ".gitignore")
    if not os.path.isfile(p) or os.path.islink(p):
        return p, None, list(GITIGNORE_ENTRIES)
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    have = set(ln.strip() for ln in text.splitlines())
    missing = [e for e in GITIGNORE_ENTRIES if e not in have and e.rstrip("/") not in have
               and "/" + e not in have]
    return p, text, missing


def git_status(target):
    """[(XY, path)] de `git status --porcelain -uall` (o que `git add .` levaria). None se não é repo git."""
    try:
        code, out, _ = gitx.run(target, ["status", "--porcelain=v1", "-z", "-uall"], check=False)
    except CsError:
        return None
    if code != 0:
        return None
    parts = out.decode("utf-8", "replace").split("\0")
    res, i = [], 0
    while i < len(parts):
        e = parts[i]
        i += 1
        if len(e) < 4:
            continue
        xy, rel = e[:2], e[3:]
        if "R" in xy or "C" in xy:
            i += 1  # origem do rename/cópia
        res.append((xy, rel))
    return res


def _emit_paths(target):
    p = os.path.join(skill_dir(target), "emit", "manifest.json5")
    try:
        data = json5io.load(p) if os.path.isfile(p) else {}
    except (ValueError, OSError):
        data = {}
    return set(e.get("path") for e in (data.get("files") or []) if isinstance(e, dict) and e.get("path"))


def _ignored_after(rel):
    """Caminho que o `<pasta>/.gitignore` gravado pelo sanitize exclui do commit."""
    if not rel.startswith(DIRNAME + "/"):
        return False
    inner = rel[len(DIRNAME) + 1:]
    parts = inner.split("/")
    return (inner.startswith(("tmp/", "memory/index/", "backups/")) or inner in ("tmp", "backups")
            or "__pycache__" in parts[:-1] or parts[-1] == "__pycache__")


def classify_status(target, status):
    """→ (esperados, inesperados): esperado = pasta da skill, manifesto do emit, escritas gerenciadas."""
    managed = _emit_paths(target) | set(MANAGED_OUTSIDE)
    exp, unexp = [], []
    for xy, rel in status or []:
        r = rel.rstrip("/")
        ok = (r == DIRNAME or rel.startswith(DIRNAME + "/") or r in managed
              or (rel.endswith("/") and any(m.startswith(rel) for m in managed)))
        (exp if ok else unexp).append({"status": xy, "path": rel})
    return exp, unexp


def _commit_preview(target, status):
    rows = []
    for xy, rel in status or []:
        if _ignored_after(rel):
            continue
        rows.append({"status": xy, "path": rel, "bytes": size_of(os.path.join(target, rel))})
    return rows


def plan(target):
    """Inventário sem escrever nada."""
    target = os.path.realpath(target)
    sp = _require(target)
    tmp = os.path.join(sp, "tmp")
    tmp_items = []
    if os.path.islink(tmp):
        tmp_items.append({"path": _rel(target, tmp), "bytes": size_of(tmp), "symlink": True})
    elif os.path.isdir(tmp):
        for n in sorted(os.listdir(tmp)):
            p = os.path.join(tmp, n)
            tmp_items.append({"path": _rel(target, p) + ("/" if os.path.isdir(p) and not os.path.islink(p) else ""),
                              "bytes": size_of(p)})
    caches = pycaches(target)
    status = git_status(target)
    gi_path, gi_text, gi_missing = gitignore_state(target)
    expected, unexpected = classify_status(target, status)
    before = size_of(sp)
    freed = size_of(tmp) + sum(c["bytes"] for c in caches)
    return {"schema_version": 1, "dir": DIRNAME, "applied": False,
            "delete": {"tmp": {"path": DIRNAME + "/tmp/", "exists": os.path.lexists(tmp), "bytes": size_of(tmp),
                               "items": tmp_items},
                       "pycache": caches},
            "gitignore": {"path": _rel(target, gi_path), "exists": gi_text is not None, "missing": gi_missing},
            "defects": {"workaround_scripts": workarounds(target), "nested_git": nested_git(target, status)},
            "product_changes": unexpected, "managed_changes": expected,
            "size": {"before": before, "after": max(before - freed, 0)},
            "commit": _commit_preview(target, status), "git": status is not None}


def _write_gitignore(target, path, text, missing):
    if not missing:
        return False
    body = text if text is not None else ("# gerado por codebase-specialists (sanitize): rascunho, índices e "
                                          "backups locais não entram no commit\n")
    if body and not body.endswith("\n"):
        body += "\n"
    body += "".join(e + "\n" for e in missing)
    jsonio.write_text_atomic(path, body, target=target)
    return True


def apply(target):
    """Lista contornos (antes de apagar), apaga `tmp/` e `__pycache__`, grava `.gitignore` e o registro."""
    target = os.path.realpath(target)
    pl = plan(target)
    sp = skill_dir(target)
    tmp = os.path.join(sp, "tmp")
    deleted = []
    if os.path.islink(tmp):
        os.unlink(tmp)
        deleted.append(DIRNAME + "/tmp")
    elif os.path.isdir(tmp):
        shutil.rmtree(tmp)
        deleted.append(DIRNAME + "/tmp/")
    for c in pl["delete"]["pycache"]:
        p = os.path.join(target, c["path"].rstrip("/"))
        if paths.is_within(sp, p) and os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p)
            deleted.append(c["path"])
    gi_path, gi_text, gi_missing = gitignore_state(target)
    wrote = _write_gitignore(target, gi_path, gi_text, gi_missing)
    status = git_status(target)
    expected, unexpected = classify_status(target, status)
    rep = dict(pl)
    rep.update({"applied": True, "at": log.now_iso(), "deleted": deleted,
                "gitignore": {"path": _rel(target, gi_path), "written": wrote, "missing": []},
                "product_changes": unexpected, "managed_changes": expected,
                "commit": _commit_preview(target, status)})
    rep["defects"] = {"workaround_scripts": pl["defects"]["workaround_scripts"],
                      "nested_git": nested_git(target, status)}
    rep["size"] = {"before": pl["size"]["before"], "after": size_of(sp)}
    json5io.dump(rep, os.path.join(sp, RECORD), "registro do último `cs.py sanitize --apply` (approve.4); gerado",
                 target=target)
    rep["size"]["after"] = size_of(sp)
    log.ledger(target, "sanitize", actor="cs.py sanitize", deleted=deleted,
               freed=pl["size"]["before"] - rep["size"]["after"],
               workaround_scripts=[w["path"] for w in rep["defects"]["workaround_scripts"]],
               nested_git=rep["defects"]["nested_git"])
    return rep


def check(target):
    """→ (ok, problemas[], avisos[]). Prova o EFEITO do sanitize, não que o comando rodou."""
    target = os.path.realpath(target)
    sp = _require(target)
    problems, warnings = [], []
    tmp = os.path.join(sp, "tmp")
    if os.path.islink(tmp) or (os.path.isdir(tmp) and os.listdir(tmp)) or os.path.isfile(tmp):
        problems.append("%s/tmp/ não está vazio (%s)" % (DIRNAME, human(size_of(tmp))))
    _, gi_text, gi_missing = gitignore_state(target)
    if gi_text is None:
        problems.append("%s/.gitignore ausente" % DIRNAME)
    elif gi_missing:
        problems.append("%s/.gitignore sem %s" % (DIRNAME, ", ".join(gi_missing)))
    status = git_status(target)
    for g in nested_git(target, status):
        problems.append(".git aninhado fora de tmp/: %s" % g)
    caches = pycaches(target)
    if caches:
        warnings.append("__pycache__ recriado depois do sanitize (ignorado pelo .gitignore): %s"
                        % ", ".join(c["path"] for c in caches[:3]))
    _, unexpected = classify_status(target, status)
    if unexpected:
        warnings.append("alterado fora do esperado (produto? confira antes do commit): %s"
                        % ", ".join("%s %s" % (u["status"], u["path"]) for u in unexpected[:5]))
    return not problems, problems, warnings


def render(rep):
    lines = []
    head = "sanitize --apply (feito)" if rep["applied"] else \
        "sanitize (plano — nada foi apagado; aplique com `cs.py sanitize --apply`)"
    lines.append(head)
    t = rep["delete"]["tmp"]
    verb = "apagado" if rep["applied"] else "apagar"
    if t["exists"]:
        lines.append("%s: %s (%s)" % (verb, t["path"], human(t["bytes"])))
        for it in t["items"][:20]:
            lines.append("  - %s (%s)" % (it["path"], human(it["bytes"])))
        if len(t["items"]) > 20:
            lines.append("  … +%d item(ns)" % (len(t["items"]) - 20))
    else:
        lines.append("%s/tmp/: já ausente" % rep["dir"])
    for c in rep["delete"]["pycache"]:
        lines.append("%s: %s (%s)" % (verb, c["path"], human(c["bytes"])))
    gi = rep["gitignore"]
    if rep["applied"]:
        lines.append(".gitignore: %s (%s)" % (gi["path"], "gravado" if gi.get("written") else "já completo"))
    else:
        lines.append(".gitignore: %s — %s" % (gi["path"], ("gravar + " + ", ".join(gi["missing"])) if gi["missing"]
                                               else "já completo"))
    for w in rep["defects"]["workaround_scripts"]:
        lines.append("DEFEITO (contorno manual do executor, script deixado em tmp/): %s (%s)"
                     % (w["path"], human(w["bytes"])))
    for g in rep["defects"]["nested_git"]:
        lines.append("DEFEITO: .git aninhado fora de tmp/: %s" % g)
    for u in rep["product_changes"]:
        lines.append("aviso: alterado fora do esperado (produto?): %s %s" % (u["status"], u["path"]))
    lines.append("tamanho de %s/: antes %s; %s %s" % (rep["dir"], human(rep["size"]["before"]),
                                                    "fica" if rep["applied"] else "depois",
                                                    human(rep["size"]["after"])))
    if not rep.get("git"):
        lines.append("entra no commit: (alvo sem git)")
    else:
        com = rep["commit"]
        lines.append("entra no commit (`git add .`): %d caminho(s), %s"
                     % (len(com), human(sum(c["bytes"] for c in com))))
        for c in com[:30]:
            lines.append("  %s %s" % (c["status"], c["path"]))
        if len(com) > 30:
            lines.append("  … +%d caminho(s)" % (len(com) - 30))
    return lines
