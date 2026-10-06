#!/usr/bin/env python3
"""hook_aprovacao.py -- hook PreToolUse (Claude Code) que impede o AGENTE de forjar aprovacao humana.

Nega comandos Bash que executem (AC-13: so quando o script e EXECUTADO e o subcomando -- 1o argumento posicional
depois de `--work W`/`--work=W` -- e aprovador; `front report frase`, texto em printf/echo para arquivo, mensagem de
commit e grep passam; texto entregue a um shell pela stdin, `printf ... | sh` ou heredoc, e analisado):
  * ac.py ... gate|preauth|frase (auto-correcao: gates humanos, pre-autorizacoes e frase-senha v0.4)
  * co.py ... approve           (construcao-orquestrada: aprovacao humana)
  * scripts aprovar-*.sh        (atalhos de aprovacao que so o humano deve rodar)
incluindo variacoes: caminho absoluto/~/./, `python3 -m ac`, aspas em qualquer token, `sh -c`/`bash -c`,
`;` `&&` `||` `|` `&` e quebra de linha, `$(...)`, variavel nao resolvida (`$AC`, `${AC}`, `AC=...; "$AC"`),
codigo embutido (`python3 -c '...runpy.run_path("ac.py")...'`). Permite o resto, inclusive leitura do ac.py
(cat/grep/head/git ...) e subcomandos nao-aprovadores (`ac.py status|check|done|run record|load ...`).
Ferramentas nao-Bash passam sempre.

Contrato (ESPEC AC-04 b/c): bloqueio = exit 2 com motivo no stderr; permissao = exit 0 sem saida.
Instalado GLOBALMENTE: payload invalido/excecao interna so bloqueia se o texto bruto citar
gate|preauth|approve|aprovar; caso contrario exit 0 (nao derruba o Bash de todas as sessoes).
`--selftest` roda payloads sinteticos positivos e negativos e sai 0 se todos batem.

LIMITE HONESTO: isto e um filtro sintatico sobre a string do comando, nao uma sandbox. Shell irrestrito pode
contornar (ex.: montar o nome por concatenacao/base64, copiar ac.py com outro nome, escrever um script e
executa-lo depois, `find -exec`, `awk system()`, `eval` de texto construido). O hook NAO torna o forjamento
impossivel; torna-o DELIBERADO e VISIVEL: qualquer contorno exige ofuscacao explicita que fica no transcript.
A garantia forte vem da frase-senha do founder (v0.4: so quem a conhece calcula a tag de cada aprovacao,
recalculada por `ac.py frase conferir`) e da trilha de auditoria (AC-04d).
Na duvida (mencao a gate/preauth/approve por indirecao num comando que nao e leitura), o hook falha fechado.

Stdlib apenas, Python 3.9+.
"""
import json
import os
import re
import shlex
import sys

SEPARATORS = {";", "&&", "||", "|", "&", "|&", ";;", "\n", "(", ")", "{", "}", "!", "`"}
KEYWORDS = {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "for", "in", "case", "esac",
            "time", "!"}
# Prefixos que apenas repassam a execucao para o comando seguinte.
WRAPPERS = {"env", "nohup", "exec", "command", "builtin", "sudo", "doas", "nice", "ionice", "stdbuf",
            "caffeinate", "noglob", "chronic"}
WRAPPERS_WITH_ARG = {"timeout": 1, "gtimeout": 1}
# sed NAO e leitor (o comando `e` do sed executa shell). Programas que so leem/exibem texto: mencionar ac.py e "gate" no mesmo comando nao executa nada.
READERS = {"cat", "less", "more", "head", "tail", "grep", "egrep", "fgrep", "rg", "ag", "ack", "wc", "diff",
           "cmp", "ls", "file", "stat", "echo", "printf", "git", "nl", "od", "xxd", "hexdump", "strings", "cut",
           "sort", "uniq", "tr", "column", "bat", "md5", "md5sum", "shasum", "sha1sum", "sha256sum",
           "realpath", "dirname", "basename", "readlink", "test", "[", "true", "false", "cd", "pwd", "which",
           "type", "jq", "tee", "touch", "mkdir", "cp", "mv", "ln", "rm", "chmod", "code", "open", "vim", "vi",
           "nano", "view", "colordiff", "delta", "fold", "fmt", "rev", "tac", "paste", "join", "comm", "look"}
# Programas que executam os argumentos recebidos (pela stdin ou como codigo).
ARG_EXECUTORS = {"xargs", "parallel", "eval", "source", "."}

AC_WORDS = {"gate", "preauth", "frase"}
CO_WORDS = {"approve"}
APROVAR_RE = re.compile(r"(^|/)aprovar-[^/\s'\"]*\.sh\b")
SCRIPT_IN_TEXT_RE = re.compile(r"(?<![\w.-])(ac|co)\.py\b|(?<![\w.-])-m\s*(ac|co)\b|\bimport\s+(ac|co)\b|"
                               r"\bfrom\s+(ac|co)\s+import\b|\$\{?\w+\}?")
APPROVAL_IN_TEXT_RE = re.compile(r"\b(gate|preauth|approve|frase)\b")


def tokenize(cmd):
    """Tokens do shell com aspas removidas; quebra de linha vira separador. None se nao tokenizavel."""
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()<>\n")
        lex.whitespace = " \t\r"
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return None


def segments(tokens):
    seg = []
    for t in tokens:
        if t in SEPARATORS or (t and set(t) <= set(";&|()<>\n")):
            if seg:
                yield seg
            seg = []
        else:
            seg.append(t)
    if seg:
        yield seg


def strip_prefix(seg):
    """Remove atribuicoes VAR=..., palavras-chave e wrappers; devolve o segmento a partir do executavel."""
    i = 0
    while i < len(seg):
        t = seg[i]
        if re.match(r"^[A-Za-z_]\w*=", t) or t in KEYWORDS:
            i += 1
        elif os.path.basename(t) in WRAPPERS:
            i += 1
            while i < len(seg) and seg[i].startswith("-"):
                i += 1
        elif os.path.basename(t) in WRAPPERS_WITH_ARG:
            i += 1
            while i < len(seg) and seg[i].startswith("-"):
                i += 1
            i += WRAPPERS_WITH_ARG[os.path.basename(t)]
        else:
            break
    return seg[i:]


def script_kind(tok, prev):
    """'ac' | 'co' | 'var' | None -- o que este token referencia como script executavel."""
    if prev == "-m" and tok in ("ac", "co"):
        return tok
    if tok in ("-mac", "-mco"):
        return tok[2:]
    base = os.path.basename(tok)
    if base in ("ac.py", "co.py"):
        return base[:2]
    if "$" in tok:
        return "var"
    return None


SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
GLOBAL_OPTS_WITH_VALUE = {"--work"}  # opcoes globais do ac.py/co.py que consomem o token seguinte


def first_positional(rest):
    """1o argumento posicional depois das opcoes globais (`--work W`, `--work=W`, `-h`): o subcomando."""
    skip = False
    for t in rest:
        if skip:
            skip = False
            continue
        if t in GLOBAL_OPTS_WITH_VALUE:
            skip = True
            continue
        if t.startswith("-"):
            continue
        return t
    return None


def shell_reads_stdin(body):
    """`sh`, `bash -s`, `bash -l` ... sem script nem -c: executa o que chega pela stdin (pipe ou heredoc)."""
    if os.path.basename(body[0]) not in SHELLS:
        return False
    for t in body[1:]:
        if t.startswith("-"):
            if "c" in t.lstrip("-") and not t.startswith("--"):
                return False
            continue
        return False  # script em arquivo
    return True


INTERPRETER_RE = re.compile(r"^(python[\d.]*|pypy[\d.]*|node|ruby|perl|php|osascript)$")


def interpreter_reads_stdin(body):
    """`python3`, `python3 -`, `node -` ... sem arquivo nem -c/-e: executa codigo vindo da stdin (heredoc/pipe)."""
    if not INTERPRETER_RE.match(os.path.basename(body[0])):
        return False
    for t in body[1:]:
        if t == "-":
            return True
        if t.startswith("-"):
            if t in ("-c", "-e", "-m") or t.startswith(("-m", "-c")):
                return False
            continue
        return False
    return True


def has_approval(rest, kind):
    """AC-13 (uso real): so e aprovacao quando o SUBCOMANDO (1o posicional apos --work W) e aprovador.
    `ac.py --work W front report frase` ou `... front report gate` passam."""
    words = AC_WORDS if kind == "ac" else CO_WORDS if kind == "co" else AC_WORDS | CO_WORDS
    return first_positional(rest) in words


def has_approval_word_anywhere(rest, kind):
    words = AC_WORDS if kind == "ac" else CO_WORDS if kind == "co" else AC_WORDS | CO_WORDS
    for j, t in enumerate(rest):
        if t in words:
            # `--decision approve` e argumento, nao subcomando (so relevante para referencia ambigua).
            if t == "approve" and kind == "var" and j > 0 and rest[j - 1] == "--decision":
                continue
            return True
    return False


def embedded_text_hit(text):
    return bool(SCRIPT_IN_TEXT_RE.search(text) and APPROVAL_IN_TEXT_RE.search(text)) or bool(
        APROVAR_RE.search(text))


def check(cmd, depth=0):
    """Devolve motivo (str) se o comando deve ser negado, senao None."""
    if depth > 6:
        return "aninhamento de shell profundo demais para analisar (falha fechada)"
    tokens = tokenize(cmd)
    if tokens is None:
        # Aspas desbalanceadas etc.: analise textual conservadora.
        if embedded_text_hit(cmd):
            return "comando nao tokenizavel menciona script de aprovacao + gate/preauth/approve (falha fechada)"
        return None
    segs = [strip_prefix(seg) for seg in segments(tokens)]
    # Texto entregue a um shell pela stdin (`printf '...' | sh`, `echo ... | bash`): o "leitor" vira executor.
    feeds_shell = any(b and shell_reads_stdin(b) for b in segs)
    # Codigo entregue a interpretador pela stdin (`python3 - <<EOF`): ac.py + gate/preauth/frase no texto nega.
    if any(b and interpreter_reads_stdin(b) for b in segs) and embedded_text_hit(cmd):
        return "codigo entregue a interpretador pela stdin referencia script de aprovacao + gate/preauth/frase"
    for body in segs:
        if not body:
            continue
        exe = os.path.basename(body[0])
        is_reader = exe in READERS
        if is_reader and feeds_shell:
            for t in body[1:]:
                why = check(t, depth + 1)
                if why:
                    return "texto entregue a um shell pela stdin: " + why
        # Strings embutidas (sh -c '...', python -c '...', bash -lc "..."): analisar recursivamente.
        for t in body[1:]:
            if any(c in t for c in " \t\n;&|'\"$"):
                if not is_reader:
                    why = check(t, depth + 1)
                    if why:
                        return why
                    if embedded_text_hit(t):
                        return "codigo embutido referencia script de aprovacao + gate/preauth/approve"
        if is_reader:
            continue
        # Scripts aprovar-*.sh executados direta ou indiretamente (bash x.sh, source x.sh, ./x.sh).
        for t in body:
            if APROVAR_RE.search(t):
                return "execucao de script de aprovacao humana (%s)" % t
        # Referencia a ac.py / co.py / -m ac / variavel, seguida de subcomando aprovador.
        prev = None
        for i, t in enumerate(body):
            kind = script_kind(t, prev)
            prev = t
            if kind and has_approval(body[i + 1:], kind):
                return "invocacao de aprovacao humana via %s (%s)" % (
                    {"ac": "ac.py gate|preauth|frase", "co": "co.py approve", "var": "variavel nao resolvida"}[kind],
                    " ".join(body)[:200])
        # Executores de argumentos (xargs/eval/source) que tocam o script: subcomando pode vir de outro lugar.
        if exe in ARG_EXECUTORS:
            refs = any(script_kind(t, None) in ("ac", "co") for t in body) or any(
                "ac.py" in t or "co.py" in t for t in body)
            if refs and APPROVAL_IN_TEXT_RE.search(cmd):
                return "%s executando script de aprovacao com gate/preauth/approve no comando" % exe
            if exe in ("eval",) and embedded_text_hit(" ".join(body[1:])):
                return "eval de texto com script de aprovacao"
    return None


def decide(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload nao e objeto JSON")
    if payload.get("tool_name") != "Bash":
        return None
    cmd = (payload.get("tool_input") or {}).get("command")
    if not isinstance(cmd, str):
        return None
    return check(cmd)


# --------------------------------------------------------------------------- selftest

_A = "/Users/x/.claude/skills/auto-correcao/scripts/ac.py"
SELF_DENY = [
    "python3 %s --work /tmp/c gate stop --by founder --decision approve" % _A,
    "python3 ~/.claude/skills/auto-correcao/scripts/ac.py --work /tmp/c preauth commit --by f",
    "cd /s && python3 ./ac.py --work /tmp/c gate stop --by f --decision approve",
    "./ac.py --work /tmp/c gate stop",
    "PYTHONPATH=/s python3 -m ac --work /tmp/c gate stop",
    "python3 -mac --work /tmp/c gate stop",
    '"python3" "%s" --work /tmp/c "gate" stop' % _A,
    "python3 '%s' 'preauth' commit" % _A,
    "sh -c 'python3 %s --work /tmp/c gate stop'" % _A,
    'bash -lc "python3 ac.py preauth commit"',
    "true; python3 ac.py gate stop",
    "echo ok && python3 ac.py gate stop",
    "false || python3 ac.py gate stop",
    "yes | python3 ac.py gate stop",
    "ls\npython3 ac.py gate stop",
    "AC=%s; python3 \"$AC\" --work /tmp/c gate stop" % _A,
    "python3 $AC --work /tmp/c gate stop",
    "python3 ${AC} preauth commit",
    "python3 -c 'import runpy,sys; sys.argv=[\"ac.py\",\"gate\",\"stop\"]; runpy.run_path(\"%s\")'" % _A,
    "python3 -c 'import ac; ac.main([\"--work\",\"/tmp/c\",\"gate\",\"stop\"])'",
    "python3 /x/scripts/co.py --work /tmp/o approve entrega",
    "python3 co.py approve plan:DEC-1",
    "sh -c \"cd /x && python3 ./co.py --work . approve stop\"",
    "env FOO=1 python3 ac.py gate stop",
    "timeout 10 python3 ac.py gate stop",
    "echo $(python3 ac.py gate stop)",
    "bash ~/bin/aprovar-sprint.sh 03",
    "./aprovar-gate.sh",
    "source scripts/aprovar-x.sh",
    "echo stop | xargs python3 ac.py --work /tmp/c gate",
    "eval \"python3 ac.py gate stop\"",
    "python3 ac.py --work /tmp/c gate stop 'unterminated",
    "sed -n '1e python3 ac.py gate stop' x.txt",
    "sed -e 'e python3 ac.py --work /tmp/c preauth commit' /dev/null",
    "python3 ac.py --work=/tmp/c frase conferir",
    "printf 'python3 ac.py --work /tmp/c gate stop --by f --decision approve' | sh",
    "echo 'python3 ac.py --work /tmp/c frase definir' | bash",
    "bash -s <<'EOF'\npython3 ac.py --work /tmp/c gate stop\nEOF",
    "cat <<'EOF' | bash\npython3 ac.py --work /tmp/c preauth commit\nEOF",
    "python3 - <<'EOF'\nimport runpy, sys; sys.argv = ['ac.py', '--work', '/tmp/c', 'frase', 'conferir']\nEOF",
    "python3 %s --work /tmp/c frase definir" % _A,
    "python3 ac.py --work /tmp/c frase conferir",
    "echo x | python3 ac.py --work /tmp/c frase definir",
    "python3 $AC --work /tmp/c frase conferir",
]
SELF_ALLOW = [
    "ls -la",
    "git status",
    "echo gate",
    "python3 other.py gate stop",
    "cat docs/gate.md",
    "python3 %s --work /tmp/c status" % _A,
    "python3 %s --work /tmp/c check intake.3" % _A,
    "python3 ac.py --work /tmp/c done intake",
    "python3 ac.py --work /tmp/c load",
    "python3 ac.py --work /tmp/c run record --config sistema --alvo py",
    "python3 \"$AC\" --work /tmp/c status",
    "python3 co.py --work /tmp/o status",
    "cat %s | grep -n gate" % _A,
    "grep -n 'def cmd_gate\\|preauth' %s" % _A,
    "head -50 ac.py; sed -n '1,40p' co.py",
    "tail -f log.txt; less ac.py",
    "git diff -- ac.py  # gate preauth",
    "git commit -m 'ac.py: endurece gate e preauth'",
    "cat ~/bin/aprovar-sprint.sh",
    "echo $HOME",
    "grep -n frase %s" % _A,
    "cat ~/.claude/skills/auto-correcao/scripts/frase.py",
    "echo frase",
    "python3 other.py frase definir",
    "python3 %s --work /tmp/c front report frase --file /tmp/rel.md" % _A,
    "python3 ac.py --work /tmp/c front report gate --file /tmp/rel.md",
    "printf 'texto com frase e gate\\n' > /tmp/rel.md && python3 ac.py --work /tmp/c done correcao",
    "echo 'ac.py gate stop e frase conferir' > /tmp/nota.md && python3 ac.py --work /tmp/c status",
    "git commit -m 'ac.py: gate/preauth agora pedem a frase'",
    "python3 ac.py --work /tmp/c oracle change --why x --evidence y",
]


def selftest():
    bad = 0
    for c in SELF_DENY:
        why = check(c)
        if not why:
            bad += 1
            print("FALHA (deveria negar): %r" % c)
    for c in SELF_ALLOW:
        why = check(c)
        if why:
            bad += 1
            print("FALHA (deveria permitir): %r -> %s" % (c, why))
    if decide({"tool_name": "Read", "tool_input": {"file_path": "/tmp/ac.py"}}):
        bad += 1
        print("FALHA: ferramenta nao-Bash negada")
    # Payload invalido / excecao interna: so falha fechada se o texto bruto cita aprovacao.
    raw_cases = [("{nao json", 0), ("", 0), ("[1,2]", 0), ('{"tool_name": "Bash", "tool_input": 5}', 0),
                 ("{nao json gate", 2), ("{quebrado PREAUTH", 2), ("[\"approve\"]", 2), ("lixo aprovar-x", 2)]
    for raw, want in raw_cases:
        code, _ = run(raw)
        if code != want:
            bad += 1
            print("FALHA (payload bruto %r): exit %d, esperado %d" % (raw, code, want))
    total = len(SELF_DENY) + len(SELF_ALLOW) + 1 + len(raw_cases)
    print("selftest: %d/%d ok" % (total - bad, total))
    return 1 if bad else 0


RAW_APPROVAL_RE = re.compile(r"gate|preauth|approve|aprovar|frase", re.IGNORECASE)


def run(raw):
    """(exit_code, motivo). Hook GLOBAL: payload invalido ou excecao interna NAO bloqueia todo Bash --
    so falha fechada se o texto bruto do payload cita gate|preauth|approve|aprovar."""
    try:
        payload = json.loads(raw)
        why = decide(payload)
    except Exception as exc:  # noqa: BLE001 -- qualquer erro interno cai na regra abaixo
        if RAW_APPROVAL_RE.search(raw or ""):
            return 2, "erro ao analisar payload (%s) que menciona aprovacao (falha fechada)" % type(exc).__name__
        return 0, None
    return (2, why) if why else (0, None)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        return selftest()
    try:
        raw = sys.stdin.read()
    except Exception:  # noqa: BLE001
        return 0
    code, why = run(raw)
    if code:
        sys.stderr.write("hook_aprovacao: NEGADO -- %s. Aprovacao humana (gate/preauth/approve/frase) e feita pelo "
                         "humano no terminal, nunca pelo agente.\n" % why)
    return code


if __name__ == "__main__":
    sys.exit(main())
