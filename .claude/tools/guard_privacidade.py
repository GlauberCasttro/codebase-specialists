#!/usr/bin/env python3
"""guard_privacidade.py — grep de termos privados (lógica do `guard-privacidade.sh`).

Uso:
  guard_privacidade.py [DIR|ARQ ...]     varre arquivos de texto (padrão: a raiz do projeto); ignora .git/, local/,
                                         dist/, __pycache__ (passe dist/ explicitamente para varrê-lo)
  guard_privacidade.py --staged          varre o que está no índice do git (nomes + conteúdo staged)
  guard_privacidade.py --msg ARQ         varre uma mensagem de commit
  guard_privacidade.py --git-log         varre `git log -p --all` do projeto (autor, mensagens e diffs)
  guard_privacidade.py --termos          só lista QUANTOS termos/padrões estão ativos (nunca os imprime)
  opções: --json · --help
Exit: 0 = vazio; 1 = achou termo privado (lista arquivo:linha); 2 = uso inválido.

Termos: a lista literal NÃO fica no repositório. Vem de `local/termos-privados.txt` (gitignored; caminho alternativo
em $CS_TERMOS_PRIVADOS): um termo por linha, comparação case-insensitive; linha `re:<regex>` = expressão regular;
`#` comenta. Sem o arquivo: AVISO no stderr e só os padrões genéricos abaixo (caminho de usuário e e-mail pessoal).
O achado é impresso com o trecho da linha — rode no seu terminal; não cole a saída em lugar público.
Stdlib apenas, Python 3.9+.
"""
import json
import os
import re
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
PROJETO = os.path.realpath(os.environ.get("CS_DEV_SKILL_DIR") or os.path.join(TOOLS, "..", ".."))

# Padrões genéricos (não são privados por si): caminho absoluto de usuário macOS/Linux com nome real, scratch do
# Claude Code e e-mail em provedor pessoal. Placeholders de exemplo (/Users/x/, /home/user/) passam.
GENERICOS = [
    r"/Users/(?!(x|you|user|usuario|nome|name|<[^>]*>|\$\w+|\.\.\.)/)[A-Za-z0-9._-]{2,}/",
    r"/home/(?!(x|you|user|usuario|nome|name|runner|<[^>]*>|\$\w+|\.\.\.)/)[a-z][a-z0-9._-]{2,}/",
    r"/private/tmp/" r"claude-",           # scratch do Claude Code (montado em partes de propósito)
    r"[A-Za-z0-9._%+-]+@(gmail|hotmail|outlook|yahoo|icloud|live|proton(mail)?|bol|uol)\.(com|com\.br|me)\b",
]
IGNORAR_DIRS = {".git", "local", "dist", "__pycache__", ".auto-correcao"}


def arquivo_termos():
    return os.environ.get("CS_TERMOS_PRIVADOS") or os.path.join(PROJETO, "local", "termos-privados.txt")


def carregar(avisar=True):
    pats = list(GENERICOS)
    p = arquivo_termos()
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            for ln in fh:
                t = ln.strip()
                if not t or t.startswith("#"):
                    continue
                pats.append(t[3:] if t.startswith("re:") else re.escape(t))
        fonte = "local"
    else:
        fonte = "genericos"
        if avisar:
            print("AVISO guard-privacidade: %s ausente — só padrões genéricos (caminho de usuário, e-mail pessoal). "
                  "Crie o arquivo nesta máquina (ver README, seção Privacidade)." % p, file=sys.stderr)
    return re.compile("|".join("(?:%s)" % x for x in pats), re.I), len(pats), fonte


def eh_texto(path):
    try:
        with open(path, "rb") as fh:
            return b"\0" not in fh.read(4096)
    except OSError:
        return False


def arquivos(alvos):
    for a in alvos:
        if os.path.isfile(a):
            yield a
            continue
        for d, dirs, files in os.walk(a):
            dirs[:] = sorted(x for x in dirs if x not in IGNORAR_DIRS)
            for f in sorted(files):
                p = os.path.join(d, f)
                if not os.path.islink(p):
                    yield p


def varrer_texto(rx, nome, texto, achados):
    for n, linha in enumerate(texto.splitlines(), 1):
        if rx.search(linha):
            achados.append("%s:%d: %s" % (nome, n, linha.strip()[:160]))


def varrer_arquivos(rx, alvos):
    achados = []
    for p in arquivos(alvos):
        base = alvos[0] if len(alvos) == 1 and os.path.isdir(alvos[0]) else PROJETO
        rel = os.path.relpath(p, base)
        if rx.search(rel):
            achados.append("%s: (nome do arquivo)" % rel)
        if not eh_texto(p):
            continue
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                varrer_texto(rx, rel, fh.read(), achados)
        except OSError:
            continue
    return achados


def git(*a):
    return subprocess.run(["git", "-C", PROJETO] + list(a), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=False).stdout.decode("utf-8", "replace")


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    js = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    rx, n, fonte = carregar()
    if argv and argv[0] == "--termos":
        print("padrões ativos: %d (fonte: %s; arquivo: %s)" % (n, fonte, "presente" if fonte == "local" else "ausente"))
        return 0
    achados = []
    if argv and argv[0] == "--staged":
        nomes = [x for x in git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines() if x]
        for nm in nomes:
            if rx.search(nm):
                achados.append("%s: (nome do arquivo)" % nm)
            varrer_texto(rx, nm, git("show", ":" + nm), achados)
    elif argv and argv[0] == "--msg":
        if len(argv) < 2:
            print("uso: --msg ARQ", file=sys.stderr)
            return 2
        with open(argv[1], encoding="utf-8", errors="replace") as fh:
            varrer_texto(rx, "mensagem", fh.read(), achados)
    elif argv and argv[0] == "--git-log":
        varrer_texto(rx, "git-log", git("log", "-p", "--all", "--format=commit %H%nAuthor: %an <%ae>%n%n%B"),
                     achados)
    else:
        alvos = [os.path.realpath(a) for a in argv] or [PROJETO]
        for a in alvos:
            if not os.path.exists(a):
                print("inexistente: %s" % a, file=sys.stderr)
                return 2
        achados = varrer_arquivos(rx, alvos)
    if js:
        print(json.dumps({"padroes": n, "fonte": fonte, "achados": len(achados), "linhas": achados},
                         ensure_ascii=False, indent=1))
    else:
        for a in achados:
            print("PRIVADO " + a)
        print("guard-privacidade: %d achado(s) · %d padrão(ões) · fonte %s" % (len(achados), n, fonte),
              file=sys.stderr)
    return 1 if achados else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
