"""git via subprocess com lista de args (nunca shell). Ambiente estável (LC_ALL=C, sem prompt).

Toda chamada roda com `-C <target>` e `-c core.quotepath=off`.
"""

import os
import shutil
import subprocess

from .errors import CsError

FIELD = "\x1f"
RECORD = "\x1e"
END_HDR = "\x1d"


def _env():
    env = dict(os.environ)
    env.update({"LC_ALL": "C", "LANG": "C", "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat",
                "GIT_OPTIONAL_LOCKS": "0"})
    return env


def git_bin():
    exe = shutil.which("git")
    if not exe:
        raise CsError("git não encontrado no PATH", "instale o git (a skill precisa dele para ler o repo)")
    return exe


def run(target, args, check=True, timeout=300):
    """Executa git e retorna (exit, stdout_bytes, stderr_bytes)."""
    argv = [git_bin(), "-C", target, "-c", "core.quotepath=off"] + list(args)
    try:
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           stdin=subprocess.DEVNULL, env=_env(), timeout=timeout)
    except subprocess.TimeoutExpired:
        raise CsError("git %s excedeu %ss" % (" ".join(args[:2]), timeout),
                      "repositório muito grande? reduza --max-commits")
    if check and p.returncode != 0:
        raise CsError("git %s falhou (exit %d): %s" % (" ".join(args[:3]), p.returncode,
                                                      p.stderr.decode("utf-8", "replace").strip()[:300]),
                      "confira se o alvo é um repositório git íntegro")
    return p.returncode, p.stdout, p.stderr


def out(target, args, check=True):
    return run(target, args, check=check)[1].decode("utf-8", "replace")


def is_repo(target):
    try:
        code, so, _ = run(target, ["rev-parse", "--show-toplevel"], check=False)
    except CsError:
        return False
    return code == 0


def require_repo(target):
    """Falha alta se o alvo não for (a raiz de) um repositório git."""
    git_bin()
    code, so, se = run(target, ["rev-parse", "--show-toplevel"], check=False)
    if code != 0:
        raise CsError("o alvo não é um repositório git: %s" % target,
                      "rode `git init && git add -A && git commit -m init` no alvo, "
                      "ou passe --target apontando para a raiz de um repo git")
    top = os.path.realpath(so.decode("utf-8", "replace").strip())
    if top != os.path.realpath(target):
        raise CsError("o alvo está dentro de um repo git mas não é a raiz (%s)" % top,
                      "passe --target %s" % top)
    return top


def head(target):
    """sha do HEAD ou None se não há commits."""
    code, so, _ = run(target, ["rev-parse", "--verify", "-q", "HEAD"], check=False)
    return so.decode().strip() if code == 0 else None


def ls_files(target):
    """Arquivos rastreados + não-rastreados não-ignorados, relativos POSIX, ordenados e únicos.

    Retorna (lista, bytes_brutos_da_saída) — os bytes servem de evidência (out_sha256).
    """
    _, so, _ = run(target, ["ls-files", "-z", "--cached", "--others", "--exclude-standard"])
    items = sorted(set(x for x in so.decode("utf-8", "replace").split("\0") if x))
    return items, so


def log_commits(target, max_commits=2000, paths=None):
    """Histórico em UMA chamada. Lista de dicts (mais recente primeiro):

    {sha, author, ts, subject, body, files: [{path, added, deleted}]}
    Merges excluídos; renames desligados (--no-renames) para numstat estável.
    """
    fmt = RECORD + "%H" + FIELD + "%an" + FIELD + "%at" + FIELD + "%s" + FIELD + "%b" + END_HDR
    args = ["log", "--no-merges", "--no-renames", "--numstat", "--format=" + fmt,
            "-n", str(int(max_commits))]
    if head(target) is None:
        return []
    if paths:
        args += ["--"] + list(paths)
    text = out(target, args)
    commits = []
    for rec in text.split(RECORD):
        if not rec.strip():
            continue
        hdr, _, rest = rec.partition(END_HDR)
        fields = hdr.split(FIELD)
        if len(fields) < 5:
            continue
        sha, author, ts, subject = fields[0], fields[1], fields[2], fields[3]
        body = FIELD.join(fields[4:])
        files = []
        for line in rest.splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            a, d, p = parts
            files.append({"path": p, "added": int(a) if a.isdigit() else 0,
                          "deleted": int(d) if d.isdigit() else 0})
        commits.append({"sha": sha, "author": author, "ts": int(ts or 0), "subject": subject,
                        "body": body.strip(), "files": files})
    return commits
