"""Utilitários comuns do oráculo da campanha-iter11 (medição real). Python 3.9+, só stdlib.

Caminhos sobrescrevíveis por ambiente (para rodar contra uma cópia congelada da skill):
  CS_SKILL      raiz da skill            (default ~/.claude/skills/codebase-specialists)
  CS_WORKSPACE  workspace das iterações  (default: a pasta campanhas/ do projeto)
  CS_CAMPANHA   diretório da campanha    (default $CS_WORKSPACE/iter11)

Nada aqui escreve fora de diretórios temporários: alvos históricos (iteration-4) são COPIADOS antes de
qualquer comando (L05 — diretório próprio por execução).
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

HOME = os.path.expanduser("~")
SKILL = os.path.realpath(os.environ.get("CS_SKILL", os.path.join(HOME, ".claude", "skills", "codebase-specialists")))
WORKSPACE = os.path.realpath(os.environ.get("CS_WORKSPACE") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CAMPANHA = os.path.realpath(os.environ.get("CS_CAMPANHA", os.path.join(WORKSPACE, "iter11")))
CS = os.path.join(SKILL, "scripts", "cs.py")
EVALS = os.path.join(SKILL, "evals")
FIXTURES = os.path.join(EVALS, "fixtures")
CHECK_RUN = os.path.join(EVALS, "check_run.py")
STATE_DIR = ".swarm"
FIXTURE_NAMES = ("py-billing", "ts-shop", "go-polyglot")
ITER4 = {f: os.path.join(WORKSPACE, "iteration-4", "%s-setup-vague" % f, "with_skill", "target") for f in FIXTURE_NAMES}

if os.path.join(SKILL, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(SKILL, "scripts"))


def load5(path):
    """Lê JSON5 com o leitor da própria skill (o mesmo que o corretor usa)."""
    from cslib import json5io
    return json5io.load(path)


def run(argv, cwd=None, timeout=600, env=None):
    e = dict(os.environ)
    e.pop("CLAUDE_PROJECT_DIR", None)
    if env:
        e.update(env)
    p = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=e)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def cs(target, *args, **kw):
    """`python3 cs.py --target <alvo> <args>` → (rc, out, err)."""
    return run([sys.executable, CS, "--target", target] + list(args), cwd=target, **kw)


def tmpdir(prefix):
    d = tempfile.mkdtemp(prefix="oraculo-iter11-%s-" % prefix)
    return os.path.realpath(d)


def copy_target(src, prefix):
    """Cópia fiel (com .git) de um alvo histórico para um temporário próprio → caminho do alvo copiado."""
    base = tmpdir(prefix)
    dst = os.path.join(base, "target")
    shutil.copytree(src, dst, symlinks=True)
    return dst


def build_fixture(name, prefix=None):
    """`evals/fixtures/build.sh <name> <tmp>/target` → caminho do alvo."""
    base = tmpdir(prefix or name)
    dst = os.path.join(base, "target")
    rc, out, err = run(["bash", os.path.join(FIXTURES, "build.sh"), name, dst], timeout=300)
    if rc != 0:
        raise AssertionError("build.sh %s falhou (exit %d): %s" % (name, rc, (err or out)[-600:]))
    return dst


def upgraded_legacy(fixture):
    """Cópia do alvo da iteração 4 (layout legado `.specialists/`) migrada com `upgrade --apply`.
    → (alvo, rc, saída). Quem chama decide se rc != 0 é falha do requisito."""
    t = copy_target(ITER4[fixture], "iter4-" + fixture)
    rc, out, err = cs(t, "upgrade", "--apply", "--allow-outside", timeout=900)
    return t, rc, out + "\n" + err


def tree_hash(root, skip=(".git",)):
    """sha256 de (caminho relativo, conteúdo) de todo arquivo sob root, pulando os nomes em skip."""
    h = hashlib.sha256()
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in skip)
        for fn in sorted(fns):
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root)
            h.update(rel.encode("utf-8") + b"\0")
            if os.path.islink(p):
                h.update(b"L" + os.readlink(p).encode("utf-8"))
            else:
                with open(p, "rb") as fh:
                    h.update(hashlib.sha256(fh.read()).digest())
    return h.hexdigest()


def dir_size(root):
    total = 0
    for dp, dns, fns in os.walk(root):
        for fn in fns:
            p = os.path.join(dp, fn)
            if not os.path.islink(p):
                total += os.path.getsize(p)
    return total


def nested_git(root, allow_root_git=True):
    """Todo `.git` (dir ou arquivo) sob root, exceto o `.git` da própria raiz."""
    found = []
    for dp, dns, fns in os.walk(root):
        for name in list(dns) + list(fns):
            if name == ".git":
                p = os.path.join(dp, name)
                if allow_root_git and dp == root:
                    continue
                found.append(os.path.relpath(p, root))
        dns[:] = [d for d in dns if d != ".git"]
    return found


def pycaches(root):
    return [os.path.relpath(os.path.join(dp, d), root) for dp, dns, _ in os.walk(root) for d in dns
            if d == "__pycache__"]
