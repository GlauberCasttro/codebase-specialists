"""Ferramentas exigidas por um comando declarado e diagnóstico de "ferramenta ausente".

Ferramenta ausente no ambiente do scan NÃO é falha do repositório: o comando vira `unavailable`
(com a ferramenta), nunca `failed`. Dois caminhos:
- estático (antes de executar): primeira palavra de cada segmento da receita do make (com variáveis
  do Makefile substituídas e pré-requisitos seguidos) ou do corpo do script npm; procurada no PATH e,
  para scripts npm, em node_modules/.bin do pacote e da raiz;
- dinâmico (depois de executar): saída com "command not found" / "No such file or directory" /
  exit 127 / módulo Python de terceiros ausente.
"""

import os
import re
import shlex
import shutil

BUILTINS = frozenset("""
: . [ [[ alias break case cd command continue declare do done echo elif else esac eval exec exit
export false fi for function getopts hash if in local printf pwd read readonly return set shift
source test then time trap true type ulimit umask unset until wait while { } ! env nohup
""".split())
MAKE_VAR = re.compile(r"^([A-Za-z_][\w.]*)\s*(?::|::|\?|\+)?=\s*(.*)$")
MAKE_REF = re.compile(r"\$[({]([A-Za-z_][\w.]*)[)}]")
NOT_FOUND = (
    re.compile(r"(?:^|\n)(?:[^\n:]*: )?(?:line \d+: )?([\w.+-]+): (?:command not found|not found)\b"),
    re.compile(r"(?:^|\n)make(?:\[\d+\])?: ([\w.+-]+): No such file or directory"),
    re.compile(r"(?:^|\n)env: ['‘`]?([\w.+-]+)['’`]?: No such file or directory"),
    re.compile(r"(?:^|\n)sh: \d+: ([\w.+-]+): not found"),
    re.compile(r"\[Errno 2\] No such file or directory: '([\w.+-]+)'"),
)
PY_MISSING_MODULE = re.compile(r"(?:ModuleNotFoundError|ImportError): No module named '([\w]+)")


OPERATORS = frozenset(["&&", "||", ";", "|", "&", ";;", "(", ")", "|&"])
SKIP_PREFIX = frozenset(["exec", "time", "nohup", "command", "sudo", "!", "then", "do", "else", "if",
                         "while", "until", "elif"])


def first_words(line):
    """Primeira palavra (ferramenta) de cada segmento de uma linha de shell, sem atribuições.

    Tokeniza respeitando aspas; linha que não tokeniza devolve [] (sem conclusão estática).
    """
    text = re.sub(r"\$[({][^)}]*[)}]", "$VAR", line.strip().lstrip("@-+").strip())
    if not text or text.startswith("#"):
        return []
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = "#"
        toks = list(lex)
    except ValueError:
        return []
    out = []
    start = True
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in OPERATORS or set(t) <= set("&|;()<>"):
            start = True
            i += 1
            continue
        if start:
            if re.match(r"^[A-Za-z_]\w*=", t) or t in SKIP_PREFIX:
                i += 1
                continue
            if t == "env":
                i += 1
                while i < len(toks) and (toks[i].startswith("-") or "=" in toks[i]):
                    i += 1
                continue
            start = False
            if not ("$" in t or "`" in t or t in BUILTINS or t.startswith(("(", "{"))):
                out.append(t)
        i += 1
    return out


def make_vars(lines):
    out = {}
    for ln in lines:
        if ln.startswith("\t"):
            continue
        m = MAKE_VAR.match(ln.replace("export ", "", 1) if ln.startswith("export ") else ln)
        if m and ":" not in m.group(1):
            out.setdefault(m.group(1), m.group(2).split("#")[0].strip())
    return out


def subst(text, variables, depth=0):
    if depth > 5:
        return text
    new = MAKE_REF.sub(lambda m: variables.get(m.group(1), m.group(0)), text)
    return subst(new, variables, depth + 1) if new != text else new


def make_targets(lines):
    """{alvo: {"line", "deps", "recipe": [(linha, texto)]}} de um Makefile."""
    out = {}
    cur = None
    for i, ln in enumerate(lines, 1):
        if ln.startswith("\t"):
            if cur is not None:
                out[cur]["recipe"].append((i, ln[1:]))
            continue
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9][\w.-]*(?:\s+[A-Za-z0-9][\w.-]*)*)\s*:(?!=)(.*)$", ln)
        if m and not MAKE_VAR.match(ln):
            deps = m.group(2).split("#")[0].split(";")[0].split()
            names = m.group(1).split()
            cur = names[0]
            for n in names:
                out.setdefault(n, {"line": i, "deps": [], "recipe": []})
                out[n]["deps"].extend(d for d in deps if d not in out[n]["deps"])
            continue
        cur = None
    return out


def make_tools(targets, variables, target, seen=None):
    """[(ferramenta, linha)] da receita do alvo e dos pré-requisitos (recursivo)."""
    seen = seen if seen is not None else set()
    if target in seen or target not in targets:
        return []
    seen.add(target)
    out = []
    for d in targets[target]["deps"]:
        out.extend(make_tools(targets, variables, d, seen))
    for line, text in targets[target]["recipe"]:
        for w in first_words(subst(text, variables)):
            if w in ("make", "$(MAKE)"):
                continue
            out.append((w, line))
    return out


def lookup(target, tool, pkg_dirs=()):
    """True se a ferramenta existe (PATH, caminho do repo, ou node_modules/.bin dos pacotes)."""
    if "/" in tool:
        p = os.path.normpath(os.path.join(target, tool))
        return os.path.exists(p)
    if shutil.which(tool):
        return True
    for d in pkg_dirs:
        if os.path.exists(os.path.join(target, d, "node_modules", ".bin", tool)):
            return True
    return False


def missing_static(target, tools, pkg_dirs=()):
    """Primeira ferramenta ausente (nome, linha) ou None."""
    for tool, line in tools:
        if not lookup(target, tool, pkg_dirs):
            return tool, line
    return None


def diagnose_output(output, exit_code, repo_top_packages=()):
    """Ferramenta ausente a partir da saída de um comando que falhou; None se a falha é do repo."""
    text = output.decode("utf-8", "replace") if isinstance(output, bytes) else (output or "")
    tail = text[-20000:]
    for rx in NOT_FOUND:
        m = rx.search(tail)
        if m:
            return m.group(1)
    m = PY_MISSING_MODULE.search(tail)
    if m and m.group(1) not in repo_top_packages:
        return "python:%s" % m.group(1)
    if exit_code == 127:
        return "?"
    return None

