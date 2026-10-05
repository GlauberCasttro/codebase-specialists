"""envfail — classifica a falha de um verify: AMBIENTE (ferramenta/módulo ausente) × CÓDIGO.

Mesma heurística do scan (`scripts/scan/toolcheck.py`, status `unavailable`): "command not found", "No such file or
directory" do make/env/sh, exit 127, módulo Python de terceiros ausente (ModuleNotFoundError/ImportError de pacote que
NÃO é do repo). Copiada aqui porque o motor é instalado sozinho no alvo (.swarm/harness/) sem o scan; o teste
tests/test_escalada_saidas.py confere que os padrões não divergem dos do scan.

Regra dura: qualquer sinal de falha de teste/asserção na saída ⇒ CÓDIGO, mesmo com ferramenta ausente junto.
"""
import os
import re

NOT_FOUND = (
    re.compile(r"(?:^|\n)(?:[^\n:]*: )?(?:line \d+: )?([\w.+-]+): (?:command not found|not found)\b"),
    re.compile(r"(?:^|\n)make(?:\[\d+\])?: ([\w.+-]+): No such file or directory"),
    re.compile(r"(?:^|\n)env: ['‘`]?([\w.+-]+)['’`]?: No such file or directory"),
    re.compile(r"(?:^|\n)sh: \d+: ([\w.+-]+): not found"),
    re.compile(r"\[Errno 2\] No such file or directory: '([\w.+-]+)'"),
)
PY_MISSING_MODULE = re.compile(r"(?:ModuleNotFoundError|ImportError): No module named '([\w]+)")
# falha de teste/asserção (unittest, pytest, jest/mocha, go, cargo) — nunca é ambiente
ASSERTION = re.compile(
    r"AssertionError|\bassert(?:ion)? failed|FAILED \([^)]*failures=\d+|^FAIL: |^FAILED |\b\d+ failed\b|"
    r"^--- FAIL|test result: FAILED|Expected:|expect\(", re.M)

ENVIRONMENT = "environment"
CODE = "code"


def repo_packages(root):
    """Nomes de pacote/módulo do próprio repo (raiz e src/): import ausente deles é falha de CÓDIGO."""
    out = set()
    for base in (root, os.path.join(root, "src")):
        try:
            names = os.listdir(base)
        except OSError:
            continue
        for n in names:
            p = os.path.join(base, n)
            if os.path.isdir(p) and not n.startswith("."):
                out.add(n)
            elif n.endswith(".py"):
                out.add(n[:-3])
    return out


def diagnose(output, exit_code, repo_pkgs=()):
    """Ferramenta ausente (str) a partir da saída de um comando que falhou; None se a falha não é de ambiente."""
    text = output.decode("utf-8", "replace") if isinstance(output, bytes) else (output or "")
    tail = text[-20000:]
    if ASSERTION.search(tail):
        return None
    for rx in NOT_FOUND:
        m = rx.search(tail)
        if m:
            return m.group(1)
    m = PY_MISSING_MODULE.search(tail)
    if m and m.group(1) not in set(repo_pkgs):
        return "python:%s" % m.group(1)
    if exit_code == 127:
        return "?"
    return None


def classify(root, runs, other_problems=()):
    """runs: [{"exit_code", "tail"}]. (failure_kind, [ferramentas]) — None se nada falhou.
    AMBIENTE só quando TODA execução que falhou é ferramenta ausente e não há outro problema (diff fora do território,
    lição violada): qualquer coisa além disso é CÓDIGO e não aceita exceção."""
    failed = [r for r in runs if r and r.get("exit_code") not in (0, None)]
    if not failed and not other_problems:
        return None, []
    if other_problems or not failed:
        return CODE, []
    pkgs = repo_packages(root)
    tools = []
    for r in failed:
        if r.get("timed_out"):
            return CODE, []
        tool = diagnose(r.get("tail") or "", r.get("exit_code"), pkgs)
        if not tool:
            return CODE, []
        tools.append(tool)
    return ENVIRONMENT, sorted(set(tools))


def tool_name(tool):
    """'python:httpx' → 'httpx' (o que deve aparecer na evidência)."""
    return (tool or "").split(":", 1)[-1]
