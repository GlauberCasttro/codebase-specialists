#!/usr/bin/env python3
"""hook_aprovacao.py -- hook PreToolUse (Claude Code) que impede o AGENTE de forjar aprovacao humana.

Nega comandos das ferramentas Bash e PowerShell que executem (AC-13: so quando o script e EXECUTADO e o subcomando
-- 1o argumento posicional depois de `--work W`/`--work=W` -- e aprovador; `front report frase`, texto em printf/echo
para arquivo, mensagem de commit e grep passam; texto entregue a um shell pela stdin, `printf ... | sh` ou heredoc,
e analisado):
  * ac.py ... gate|preauth|frase (auto-correcao: gates humanos, pre-autorizacoes e frase-senha v0.4)
  * co.py ... approve           (construcao-orquestrada: aprovacao humana)
  * scripts aprovar-*.sh        (atalhos de aprovacao que so o humano deve rodar)
incluindo variacoes: caminho absoluto/~/./, `python3 -m ac`, aspas em qualquer token, `sh -c`/`bash -c`,
`;` `&&` `||` `|` `&` e quebra de linha, `$(...)`, variavel nao resolvida (`$AC`, `${AC}`, `AC=...; "$AC"`),
codigo embutido (`python3 -c '...runpy.run_path("ac.py")...'`). Permite o resto, inclusive leitura do ac.py
(cat/grep/head/git ...) e subcomandos nao-aprovadores (`ac.py status|check|done|run record|load ...`).
Windows (as duas ferramentas): interpretadores `python.exe`, `pythonw.exe`, `py [-3]`, caminhos com `\\` e `.\\`
(basename portatil, o veredito nao depende do SO -- DEC-2); `powershell|pwsh -EncodedCommand|-enc|-ec` e NEGADO
sempre, mesmo inocuo (conteudo opaco -- DEC-3). No Bash o `\\` fora de aspas continua escape.
Ferramenta PowerShell: tokenizador proprio (DEC-1: `\\` literal, aspas '...'/"..." e here-strings @'...'@, crase
como escape, `&` de chamada, `;` `|` `&&` `||`, blocos `{ }` e `( )` analisados como codigo, virgula separando
argumentos, caixa ignorada); indirecoes (`iex`, `Invoke-Expression`, `Invoke-Command -ScriptBlock { }`, `& { }`,
`powershell|pwsh -Command`, `cmd /c`) recebem a mesma regua do `eval`/`sh -c` (DEC-4); `Get-Content` e
`Select-String` (e Write-Output/Set-Content/Out-File) sao leitores. Outras ferramentas passam sempre.

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
LIMITES NO POWERSHELL (DEC-5, fora do contrato, documentados): nome ou subcomando montado em tempo de execucao
(concatenacao, `-join`, `[char]`, crase com sequencia especial como `` `a ``), variavel que guarda o SUBCOMANDO ou o
comando inteiro (`$s='gate'; python ac.py $s`, `& $cmd`), `$x ...` no inicio do segmento (tratado como expressao;
`python $ac gate` e `& $ac gate` sao negados), `[scriptblock]::Create('...')`, `Start-Job -FilePath`, `-File x.ps1`
com script escrito antes, caminho montado por `(Join-Path ...)`, `%VAR%` do cmd. A trava real e a frase-senha.

Stdlib apenas, Python 3.9+.
"""
import json
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
# PowerShell (comparados em minusculas, sem .exe): leitores/escritores de texto que nao executam o que leem.
PS_READERS = {"get-content", "gc", "select-string", "sls", "type", "write-output", "write-host", "set-content",
              "add-content", "out-file"}
PS_HOSTS = {"powershell", "pwsh", "powershell_ise"}
PS_IEX = {"iex", "invoke-expression"}
# Aspas e tracos tipograficos que o PowerShell aceita como ASCII (sem isto, `'gate'` com aspa curva escaparia).
PS_CHARS = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'", "“": '"', "”": '"',
                          "„": '"', "–": "-", "—": "-", "―": "-"})

AC_WORDS = {"gate", "preauth", "frase"}
CO_WORDS = {"approve"}
APROVAR_RE = re.compile(r"(^|[/\\])aprovar-[^/\\\s'\"]*\.sh\b")
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


def basename(tok):
    """DEC-2: basename portatil -- `/` e `\\` separam em qualquer SO (nao depende de os.path)."""
    return re.split(r"[\\/]", tok)[-1]


def exe_name(tok):
    """DEC-2: nome de executavel comparavel -- basename sem `.exe`/`.cmd`, em minusculas (o Windows ignora caixa)."""
    return re.sub(r"\.(exe|cmd)$", "", basename(tok), flags=re.IGNORECASE).lower()


def ps_lex(s):
    """DEC-1: lexer do PowerShell. Devolve [(tipo, valor)]: 'w' palavra (aspas removidas, `\\` literal), 'sep'
    separador (`;` `|` `&&` `||` quebra de linha `{` `}` `(` `)`), '&' (chamada ou segundo plano), 'redir'
    (redirecionamento com alvo). Levanta ValueError se aspas, here-string ou comentario de bloco nao fecham."""
    out, buf, i, n = [], None, 0, len(s)

    def flush():
        nonlocal buf
        if buf is not None:
            out.append(("w", buf))
        buf = None

    while i < n:
        c = s[i]
        if c == "\n" or c in ";{}()":
            flush()
            out.append(("sep", c))
            i += 1
        elif c.isspace() or c == ",":  # virgula separa elementos de lista: 'a','b' sao dois argumentos
            flush()
            i += 1
        elif c == "|":
            flush()
            out.append(("sep", "|"))
            i += 2 if s[i + 1:i + 2] == "|" else 1
        elif c == "&":
            flush()
            if s[i + 1:i + 2] == "&":
                out.append(("sep", "&&"))
                i += 2
            else:
                out.append(("&", "&"))
                i += 1
        elif c == "<" and s[i + 1:i + 2] == "#" and buf is None:  # comentario de bloco <# ... #>
            j = s.find("#>", i + 2)
            if j < 0:
                raise ValueError("comentario de bloco sem #>")
            i = j + 2
        elif c == "#" and buf is None:  # comentario ate o fim da linha
            j = s.find("\n", i)
            i = n if j < 0 else j
        elif c in "<>":  # redirecionamento: 2>&1 nao tem alvo; > x consome o alvo
            if buf is not None and re.match(r"^[1-6*]$", buf):
                buf = None
            flush()
            i += 1
            while i < n and s[i] in "<>":
                i += 1
            if s[i:i + 1] == "&" and s[i + 1:i + 2].isdigit():
                i += 2
            else:
                out.append(("redir", c))
        elif c == "`":  # crase: escapa o proximo caractere; crase + quebra de linha continua a linha
            if s[i + 1:i + 2] == "\n":
                flush()
            else:
                buf = (buf or "") + s[i + 1:i + 2]
            i += 2
        elif c == "@" and buf is None and re.match(r"@(['\"])[ \t]*\r?\n", s[i:]):  # here-string @'...'@ / @"..."@
            m = re.match(r"@(['\"])[ \t]*\r?\n", s[i:])
            end = re.compile(r"\r?\n" + m.group(1) + "@").search(s, i + m.end())
            if not end:
                raise ValueError("here-string sem fim")
            buf = s[i + m.end():end.start()]
            i = end.end()
        elif c == "'":  # aspas simples: literal; '' e uma aspa
            val, i = "", i + 1
            while True:
                j = s.find("'", i)
                if j < 0:
                    raise ValueError("aspas simples sem fim")
                val += s[i:j]
                if s[j + 1:j + 2] == "'":
                    val += "'"
                    i = j + 2
                    continue
                i = j + 1
                break
            buf = (buf or "") + val
        elif c == '"':  # aspas duplas: crase escapa, "" e uma aspa ($ fica no texto)
            val, i = "", i + 1
            while True:
                if i >= n:
                    raise ValueError("aspas duplas sem fim")
                ch = s[i]
                if ch == "`":
                    val += s[i + 1:i + 2]
                    i += 2
                elif ch == '"' and s[i + 1:i + 2] == '"':
                    val += '"'
                    i += 2
                elif ch == '"':
                    i += 1
                    break
                else:
                    val += ch
                    i += 1
            buf = (buf or "") + val
        else:
            buf = (buf or "") + c
            i += 1
    flush()
    return out


def ps_segments(cmd):
    """DEC-1: segmentos de um comando PowerShell: [(chamado, tokens)]. `chamado` = o segmento comeca com o
    operador de chamada `&` (ou o `.` de dot-source); `&` depois de um comando e separador. O alvo de
    redirecionamento sai do segmento. None se nao tokenizavel."""
    try:
        lex = ps_lex(cmd)
    except ValueError:
        return None
    segs, seg, called, skip = [], [], False, False
    for kind, val in lex:
        if kind == "sep" or (kind == "&" and seg):
            if seg:
                segs.append((called, strip_prefix(seg)))
            seg, called, skip = [], False, False
        elif kind == "&":
            called = True
        elif kind == "redir":
            skip = True
        elif skip:
            skip = False
        elif not seg and val == "." and not called:
            called = True
        else:
            seg.append(val)
    if seg:
        segs.append((called, strip_prefix(seg)))
    return segs


def strip_prefix(seg):
    """Remove atribuicoes VAR=..., palavras-chave e wrappers; devolve o segmento a partir do executavel."""
    i = 0
    while i < len(seg):
        t = seg[i]
        if re.match(r"^[A-Za-z_]\w*=", t) or t in KEYWORDS:
            i += 1
        elif basename(t) in WRAPPERS:
            i += 1
            while i < len(seg) and seg[i].startswith("-"):
                i += 1
        elif basename(t) in WRAPPERS_WITH_ARG:
            i += 1
            while i < len(seg) and seg[i].startswith("-"):
                i += 1
            i += WRAPPERS_WITH_ARG[basename(t)]
        else:
            break
    return seg[i:]


def script_kind(tok, prev):
    """'ac' | 'co' | 'var' | None -- o que este token referencia como script executavel."""
    if prev == "-m" and tok in ("ac", "co"):
        return tok
    if tok in ("-mac", "-mco"):
        return tok[2:]
    base = basename(tok)
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
    if exe_name(body[0]) not in SHELLS:
        return False
    for t in body[1:]:
        if t.startswith("-"):
            if "c" in t.lstrip("-") and not t.startswith("--"):
                return False
            continue
        return False  # script em arquivo
    return True


# Comparado com exe_name (sem .exe, minusculas): python.exe, pythonw.exe, py/py.exe do Windows contam (DEC-2).
INTERPRETER_RE = re.compile(r"^(python[\d.]*|pythonw|py|pypy[\d.]*|node|ruby|perl|php|osascript)$")


def interpreter_reads_stdin(body):
    """`python3`, `python3 -`, `py -3 -`, `node -` ... sem arquivo nem -c/-e: executa codigo vindo da stdin
    (heredoc/pipe/here-string). Opcoes como `-3`/`-3.12` do `py` sao puladas."""
    if not INTERPRETER_RE.match(exe_name(body[0])):
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


def flag_name(word):
    """Nome de uma flag `-x`/`--x`/`/x` (minusculas, sem valor `:v`), ou None."""
    m = re.match(r"^(?:[-–—―]{1,2}|/)([a-z_]+)(?::.*)?$", word.lower())
    return m.group(1) if m else None


def encoded_command(body):
    """DEC-3: `powershell|pwsh ... -EncodedCommand|-enc|-ec|-e <b64>` (qualquer prefixo de -EncodedCommand, qualquer
    caixa, depois de outras flags, inclusive dentro de `-ArgumentList '...'`) -> motivo. Conteudo opaco a um filtro
    sintatico: nega SEMPRE, sem decodificar (nao existe base64 bom; o mesmo texto vai em claro por -Command).
    Depois de -Command/-File o resto e o comando, nao flag do host."""
    for i, t in enumerate(body):
        if exe_name(t) not in PS_HOSTS:
            continue
        for a in body[i + 1:]:
            for w in a.split():
                name = flag_name(w)
                if not name:
                    continue
                if name == "ec" or "encodedcommand".startswith(name):
                    return "%s -EncodedCommand: comando codificado e opaco ao hook (negado sempre)" % exe_name(t)
                if "command".startswith(name) or "file".startswith(name):
                    return None
    return None


def ps_stdin_executor(body):
    """PowerShell: segmento que executa o texto recebido pelo pipeline -- `iex` sem argumento, `powershell|pwsh|cmd`
    sem argumento ou com `-` (ex.: `-Command -`), e os shells do Bash (`... | bash`)."""
    exe = exe_name(body[0])
    if exe in PS_IEX:
        return len(body) == 1
    if exe in PS_HOSTS or exe == "cmd":
        return len(body) == 1 or "-" in body[1:]
    return shell_reads_stdin(body)


def check(cmd, depth=0, ps=False):
    """Devolve motivo (str) se o comando deve ser negado, senao None. `ps`: sintaxe do PowerShell (DEC-1)."""
    if depth > 6:
        return "aninhamento de shell profundo demais para analisar (falha fechada)"
    if ps:
        # PowerShell e o sistema de arquivos do Windows ignoram caixa; aspas/tracos tipograficos valem como ASCII.
        cmd = cmd.translate(PS_CHARS).lower()
        segs = ps_segments(cmd)
    else:
        tokens = tokenize(cmd)
        segs = None if tokens is None else [(False, strip_prefix(seg)) for seg in segments(tokens)]
    if segs is None:
        # Aspas desbalanceadas etc.: analise textual conservadora.
        if embedded_text_hit(cmd):
            return "comando nao tokenizavel menciona script de aprovacao + gate/preauth/approve (falha fechada)"
        return None
    bodies = [b for _, b in segs if b]
    # Texto entregue a um shell pela stdin (`printf '...' | sh`, `echo ... | bash`, `'...' | iex`): leitor vira executor.
    feeds_shell = any(ps_stdin_executor(b) if ps else shell_reads_stdin(b) for b in bodies)
    # Codigo entregue a interpretador pela stdin (`python3 - <<EOF`, `@'...'@ | python -`): ac.py + gate no texto nega.
    if any(interpreter_reads_stdin(b) for b in bodies) and embedded_text_hit(cmd):
        return "codigo entregue a interpretador pela stdin referencia script de aprovacao + gate/preauth/frase"
    for called, body in segs:
        if not body:
            continue
        exe = basename(body[0])
        is_reader = exe in READERS or (ps and exe_name(body[0]) in PS_READERS)
        if feeds_shell and (is_reader or ps):
            # No PowerShell uma string solta (`'...' | iex`) tambem e texto entregue: inclui o 1o token.
            for t in (body if ps else body[1:]):
                why = check(t, depth + 1, ps) or (ps and check(t, depth + 1))
                if why:
                    return "texto entregue a um shell pela stdin: " + why
        if not is_reader:
            why = encoded_command(body)
            if why:
                return why
        # Strings embutidas (sh -c '...', python -c '...', bash -lc "...", iex "...", -Command "..."): recursao.
        for t in body[1:]:
            if any(c in t for c in " \t\n;&|'\"$") or (ps and any(ch.isspace() or ch in "{}()" for ch in t)):
                if not is_reader:
                    why = check(t, depth + 1, ps)
                    if not why and ps and any(exe_name(x) in SHELLS for x in body):
                        why = check(t, depth + 1)  # texto para sh/bash dentro do PowerShell: a regua do Bash tambem
                    if why:
                        return why
                    if embedded_text_hit(t):
                        return "codigo embutido referencia script de aprovacao + gate/preauth/approve"
                elif ps and "$(" in t:
                    # Subexpressao $(...) dentro de string e EXECUTADA mesmo como argumento de leitor.
                    why = check(t, depth + 1, ps)
                    if why:
                        return "subexpressao $(...) em argumento de leitor: " + why
        if is_reader:
            continue
        if ps and exe_name(body[0]) == "cmd":
            # cmd /c: o `^` do cmd e escape (g^ate = gate); reanalisa o resto sem ele.
            why = check(" ".join(body[1:]).replace("^", ""), depth + 1, ps)
            if why:
                return "cmd: " + why
        # Scripts aprovar-*.sh executados direta ou indiretamente (bash x.sh, source x.sh, ./x.sh, & .\x.sh).
        for t in body:
            if APROVAR_RE.search(t):
                return "execucao de script de aprovacao humana (%s)" % t
        # Referencia a ac.py / co.py / -m ac / variavel, seguida de subcomando aprovador.
        prev = None
        for i, t in enumerate(body):
            kind = script_kind(t, prev)
            prev = t
            if kind == "var" and ps and i == 0 and not called:
                continue  # PowerShell: `$x -match 'gate'` no inicio e expressao; executar exige `& $x` (DEC-5)
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
    """Ferramentas Bash e PowerShell (chave tool_input.command): motivo (str) se negado, None se permitido.
    Outras ferramentas: None."""
    if not isinstance(payload, dict):
        raise ValueError("payload nao e objeto JSON")
    tool = payload.get("tool_name")
    if tool not in ("Bash", "PowerShell"):
        return None
    cmd = (payload.get("tool_input") or {}).get("command")
    if not isinstance(cmd, str):
        return None
    return check(cmd, ps=(tool == "PowerShell"))


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
# Windows (win-hook), ferramenta Bash: interpretadores do Windows, `\` entre aspas, -EncodedCommand (DEC-2/DEC-3).
_ENC_INOCUO = "RwBlAHQALQBDAGgAaQBsAGQASQB0AGUAbQA="  # base64 UTF-16LE de "Get-ChildItem"
SELF_DENY_BASH_WIN = [
    "python.exe - <<'EOF'\nimport ac; ac.main(['gate', 'stop'])\nEOF",
    "py -3 - <<'EOF'\nimport runpy, sys; sys.argv = ['ac.py', '--work', 'c', 'preauth', 'commit']\nEOF",
    "'C:\\Program Files\\Python312\\python.exe' - <<'EOF'\nimport ac; ac.main(['frase', 'conferir'])\nEOF",
    "py -3 'C:\\x\\scripts\\ac.py' --work c preauth commit",
    "bash 'C:\\camp\\x\\aprovar-x.sh' 03",
    "powershell.exe -enc " + _ENC_INOCUO,
    "pwsh -NoProfile -EncodedCommand " + _ENC_INOCUO,
]
SELF_ALLOW_BASH_WIN = [
    "py -3 scripts/ac.py --work c status",
    "cat notas.txt | py -3 -",
    'powershell.exe -c "Get-ChildItem"',
]
# Ferramenta PowerShell (DEC-1..4), checados por decide() com tool_name "PowerShell".
SELF_DENY_PS = [
    r"python scripts\ac.py --work c gate stop --by f --decision approve",
    r"py -3 C:\x\scripts\ac.py --work c preauth commit --by f",
    r"& 'C:\Program Files\Python312\python.exe' scripts\ac.py --work c frase conferir",
    r".\scripts\ac.py --work c gate stop",
    r"python C:\x\scripts\co.py --work o approve entrega",
    r"Start-Process -FilePath python.exe -ArgumentList 'scripts\ac.py','--work','c','gate','stop' -Wait",
    r"Start-Process -FilePath python -ArgumentList 'scripts\ac.py --work c gate stop' -Wait",
    r"& .\campanhas\x\aprovar-x.sh",
    r"Write-Output ok; python ac.py --work c gate stop",
    r'iex "python scripts\ac.py --work c gate stop"',
    r"'python scripts\ac.py --work c gate stop' | Invoke-Expression",
    r"Invoke-Command -ScriptBlock { python scripts\ac.py --work c preauth commit }",
    r"& { python scripts\ac.py --work c frase conferir }",
    r'powershell.exe -NoProfile -Command "py -3 C:\x\scripts\ac.py --work c gate stop"',
    r'cmd /c "python scripts\ac.py --work c gate stop"',
    r"cmd /c python scripts\ac.py --work c g^ate stop",
    "pwsh -enc " + _ENC_INOCUO,
    "@'\nimport ac\nac.main(['gate','stop'])\n'@ | python -",
    r"Get-Content .\ac.py | py -3 - --work c preauth commit",
    r"Write-Output " + '"$(python scripts\\ac.py --work c gate stop)"',
    "python scripts\\ac.py --work c \u2018gate\u2019 stop",
    "python scripts\\ac.py --work c\u00a0gate stop",
    r"python scripts\ac.py --work c <# x #> gate stop",
    r"python scripts\ac.py --work c gate stop 2>&1",
    r"PYTHON.EXE SCRIPTS\AC.PY --work c GATE stop",
    r"& $ac --work c gate stop",
]
SELF_ALLOW_PS = [
    r"python scripts\ac.py --work c status",
    r"py -3 scripts\ac.py --work c check intake.3",
    r"python scripts\ac.py --work c front report frase --file rel.md",
    r"python scripts\ac.py --work c status > out.txt",
    r"Get-Content scripts\ac.py",
    r"Select-String -Path scripts\ac.py -Pattern gate",
    r"Get-Content campanhas\x\aprovar-x.sh",
    "git commit -m 'ac.py: gate e preauth no Windows'",
    r"python -m unittest discover -s scripts\tests",
    "'print(1)' | python -",
    'iex "git status"',
    'powershell -Command "Get-ChildItem"',
    "cmd /c dir",
    "& { git status }",
    "Get-ChildItem | Where-Object { $_.Name -match 'gate' }",
    "Set-Content nota.md 'ac.py gate stop e frase conferir'",
]


def selftest():
    bad = 0
    for c in SELF_DENY + SELF_DENY_BASH_WIN:
        why = check(c)
        if not why:
            bad += 1
            print("FALHA (deveria negar): %r" % c)
    for c in SELF_ALLOW + SELF_ALLOW_BASH_WIN:
        why = check(c)
        if why:
            bad += 1
            print("FALHA (deveria permitir): %r -> %s" % (c, why))
    # PowerShell passa por decide(): o tool_name so existe no payload.
    for c in SELF_DENY_PS:
        if not decide({"tool_name": "PowerShell", "tool_input": {"command": c}}):
            bad += 1
            print("FALHA (PowerShell, deveria negar): %r" % c)
    for c in SELF_ALLOW_PS:
        why = decide({"tool_name": "PowerShell", "tool_input": {"command": c}})
        if why:
            bad += 1
            print("FALHA (PowerShell, deveria permitir): %r -> %s" % (c, why))
    if decide({"tool_name": "Read", "tool_input": {"file_path": "/tmp/ac.py"}}):
        bad += 1
        print("FALHA: ferramenta nao-shell negada")
    # Payload invalido / excecao interna: so falha fechada se o texto bruto cita aprovacao.
    raw_cases = [("{nao json", 0), ("", 0), ("[1,2]", 0), ('{"tool_name": "Bash", "tool_input": 5}', 0),
                 ("{nao json gate", 2), ("{quebrado PREAUTH", 2), ("[\"approve\"]", 2), ("lixo aprovar-x", 2)]
    for raw, want in raw_cases:
        code, _ = run(raw)
        if code != want:
            bad += 1
            print("FALHA (payload bruto %r): exit %d, esperado %d" % (raw, code, want))
    total = (len(SELF_DENY) + len(SELF_ALLOW) + len(SELF_DENY_BASH_WIN) + len(SELF_ALLOW_BASH_WIN)
             + len(SELF_DENY_PS) + len(SELF_ALLOW_PS) + 1 + len(raw_cases))
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
