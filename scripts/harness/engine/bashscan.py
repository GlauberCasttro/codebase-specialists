"""bashscan — análise CONSERVADORA de um comando Bash para o guard PreToolUse.

Não executa nada e não tira snapshot (lição G-01: snapshot apagável pelo próprio comando = guard
aberto). Extrai: alvos de escrita, chamadas ao harness, programas, e motivos de "não analisável".
Qualquer coisa que não dá para analisar vira `unanalyzable` → o guard bloqueia.

Limite honesto: um programa arbitrário (python foo.py, npm, make) pode escrever o que quiser; isso
não é visível aqui. Ver references/harness.md (nível E3-parcial para Bash).
"""
import os
import re
import shlex

SEPARATORS = {";", "&&", "||", "|", "&", "|&", "(", ")", ";;", "{", "}"}
WRAPPERS = {"sudo", "env", "nohup", "time", "command", "exec", "nice", "ionice", "stdbuf", "timeout", "builtin"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish", "csh", "tcsh"}
INTERPRETERS = {"python", "python3", "python2", "node", "ruby", "perl", "php", "deno", "bun", "pwsh", "osascript", "Rscript", "lua"}
INLINE_FLAGS = {"-c", "-e", "-E", "--eval", "-r", "-p", "--command", "-x"}
WRITE_ALL_ARGS = {"rm", "rmdir", "unlink", "touch", "mkdir", "truncate", "shred", "tee", "mkfifo", "mknod"}
WRITE_SKIP_FIRST = {"chmod", "chown", "chgrp", "setfacl", "xattr", "chflags"}
WRITE_DEST = {"cp", "install", "rsync", "scp", "ditto", "ln"}
WRITE_ALL_INCL_SRC = {"mv"}
READONLY = {"ls", "cat", "head", "tail", "grep", "egrep", "fgrep", "rg", "ag", "find", "wc", "sort", "uniq",
            "cut", "tr", "echo", "printf", "pwd", "which", "type", "file", "stat", "du", "df", "diff", "cmp",
            "jq", "awk", "sed", "true", "false", "test", "[", "date", "basename", "dirname", "realpath",
            "readlink", "tree", "less", "more", "column", "nl", "od", "hexdump", "xxd", "shasum", "sha256sum",
            "md5", "md5sum", "whoami", "id", "uname", "hostname", "printenv", "cd", "git"}
GIT_READONLY = {"status", "log", "diff", "show", "rev-parse", "ls-files", "blame", "grep", "describe",
                "branch", "tag", "remote", "config", "shortlog", "cat-file", "ls-tree", "rev-list", "reflog",
                "show-ref", "merge-base", "name-rev", "for-each-ref", "whatchanged", "version", "help",
                "check-ignore", "ls-remote", "count-objects"}
GIT_LEAD_OK = {"add", "commit", "fetch", "push", "notes"}  # não reescrevem a árvore de trabalho
SAFE_DEVICES = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty", "/dev/zero"}
OPT_WITH_VALUE = {"timeout": 1, "nice": 0, "stdbuf": 0}


class Scan(object):
    def __init__(self):
        self.writes = []          # [(token, cwd_or_None)]
        self.unanalyzable = []    # [motivo]
        self.harness_calls = []   # [{"tool": "state"|"validate"|"mem"|"guard", "argv": [...], "cwd": ...}]
        self.programs = []        # [basename]
        self.git = []             # [(subcmd, args)]

    @property
    def ok(self):
        return not self.unanalyzable

    def as_dict(self):
        return {"writes": self.writes, "unanalyzable": self.unanalyzable, "harness_calls": self.harness_calls,
                "programs": self.programs, "git": self.git}


_FD_RE = re.compile(r"(?<![\w/.\-=])(\d+)(?=[<>])")


def _tokenize(cmd):
    pre = cmd.replace("\r", "")
    pre = _FD_RE.sub(lambda m: " __FD%s__ " % m.group(1), pre)
    pre = pre.replace("\n", " ; ")
    lx = shlex.shlex(pre, posix=True, punctuation_chars=True)
    lx.whitespace_split = True
    lx.commenters = ""
    return list(lx)


def _is_op(tok):
    return bool(tok) and all(c in ";&|()<>" for c in tok)


def _expandable(tok):
    return any(c in tok for c in "$`*?[]{}~") or tok.startswith("~")


def scan(command, cwd, root, harness_paths):
    """harness_paths: {"state": realpath, "validate": ..., "mem": ..., "guard": ..., "bin_state": ..., "bin_mem": ...}"""
    s = Scan()
    if not isinstance(command, str) or not command.strip():
        s.unanalyzable.append("comando vazio/ausente")
        return s
    for pat, why in (("$(", "substituição de comando $(...)"), ("`", "substituição de comando com crase"),
                     ("<(", "process substitution"), (">(", "process substitution"),
                     ("<<", "heredoc/herestring"), ("${", "expansão ${...}")):
        if pat in command:
            s.unanalyzable.append(why)
    if s.unanalyzable:
        return s
    try:
        toks = _tokenize(command)
    except ValueError as e:
        s.unanalyzable.append("tokenização falhou (%s)" % e)
        return s
    # segmenta
    segs, cur = [], []
    for t in toks:
        if _is_op(t) and t in SEPARATORS or (_is_op(t) and not any(c in t for c in "<>")):
            if cur:
                segs.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        segs.append(cur)
    state = {"cwd": cwd}
    for seg in segs:
        _scan_segment(seg, state, s, root, harness_paths)
    return s


def _resolve(state, tok):
    if os.path.isabs(tok):
        return os.path.normpath(tok)
    if state["cwd"] is None:
        return None
    return os.path.normpath(os.path.join(state["cwd"], tok))


def _add_write(s, state, tok, why):
    if tok in SAFE_DEVICES:
        return
    if tok.startswith("__FD") or tok == "-":
        return
    if _expandable(tok):
        s.unanalyzable.append("alvo de escrita com expansão/curinga em %s: %r" % (why, tok))
        return
    if not os.path.isabs(tok) and state["cwd"] is None:
        s.unanalyzable.append("alvo relativo após 'cd' não analisável: %r" % tok)
        return
    s.writes.append((tok, state["cwd"]))


def _scan_segment(seg, state, s, root, hp):
    # 1) redirecionamentos (em qualquer posição) e remoção de marcadores de fd
    words, i = [], 0
    while i < len(seg):
        t = seg[i]
        if t.startswith("__FD") and t.endswith("__"):
            i += 1
            continue
        if _is_op(t) and any(c in t for c in "<>"):
            nxt = seg[i + 1] if i + 1 < len(seg) else None
            if ">" in t:
                if t.endswith("&") and t not in ("&>", "&>>") and nxt is not None and (nxt.isdigit() or nxt == "-"):
                    i += 2  # dup de fd (2>&1)
                    continue
                if nxt is None:
                    s.unanalyzable.append("redirecionamento sem alvo")
                    return
                _add_write(s, state, nxt, "redirecionamento %s" % t)
            i += 2
            continue
        words.append(t)
        i += 1
    if not words:
        return
    # 2) atribuições de ambiente e wrappers
    while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
        words = words[1:]
    while words and os.path.basename(words[0]) in WRAPPERS:
        w = os.path.basename(words[0])
        words = words[1:]
        while words and (words[0].startswith("-") or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])):
            words = words[1:]
        if w == "timeout" and words:
            words = words[1:]  # duração
    if not words:
        return
    prog_tok = words[0]
    if "$" in prog_tok or "`" in prog_tok:
        s.unanalyzable.append("programa via variável: %r" % prog_tok)
        return
    prog = os.path.basename(prog_tok)
    args = words[1:]
    s.programs.append(prog)
    nonopt = [a for a in args if not a.startswith("-") or a == "-"]

    # chamadas ao harness pelo binário instalado
    real_prog = _resolve(state, prog_tok) if "/" in prog_tok else None
    if real_prog:
        rp = os.path.realpath(real_prog)
        for key, path in hp.items():
            tool = key.replace("bin_", "")
            if path and rp == path:
                s.harness_calls.append({"tool": tool, "argv": args, "cwd": state["cwd"]})
                return

    if prog in ("cs-state", "cs-mem", "cs-session", "cs-route"):
        s.harness_calls.append({"tool": {"cs-state": "state", "cs-mem": "mem", "cs-session": "session", "cs-route": "route"}[prog],
                                "argv": args, "cwd": state["cwd"]})
        return
    if prog == "cd":
        if not args:
            state["cwd"] = os.path.expanduser("~")
        elif _expandable(args[0]) or args[0] == "-":
            state["cwd"] = None
        else:
            state["cwd"] = _resolve(state, args[0])
        return
    if prog in ("eval", "source", ".", "xargs", "parallel", "watch", "script", "expect"):
        s.unanalyzable.append("%s executa conteúdo não analisável" % prog)
        return
    if prog in SHELLS:
        if any(a in ("-c",) or (a.startswith("-") and "c" in a[1:] and not a.startswith("--")) for a in args):
            s.unanalyzable.append("%s -c (código inline)" % prog)
        elif not nonopt:
            s.unanalyzable.append("%s lendo comandos do stdin" % prog)
        return
    if prog in INTERPRETERS or re.match(r"^python\d+(\.\d+)?$", prog):
        if any(a in INLINE_FLAGS or (prog == "perl" and a.startswith("-") and ("e" in a or "i" in a)) for a in args):
            s.unanalyzable.append("%s com código inline/in-place (escreva um script em arquivo)" % prog)
            return
        if not nonopt:
            s.unanalyzable.append("%s lendo código do stdin" % prog)
            return
        if prog.startswith("python") and args and args[0] == "-m":
            return
        script = nonopt[0]
        sp = _resolve(state, script)
        if sp:
            rp = os.path.realpath(sp)
            for key, path in hp.items():
                tool = key.replace("bin_", "")
                if path and rp == path and not key.startswith("bin_"):
                    rest = args[args.index(script) + 1:]
                    s.harness_calls.append({"tool": tool, "argv": rest, "cwd": state["cwd"]})
                    return
        return
    if prog == "git":
        sub_i = 0
        while sub_i < len(args) and args[sub_i].startswith("-"):
            sub_i += 2 if args[sub_i] in ("-C", "-c", "--git-dir", "--work-tree") else 1
        sub = args[sub_i] if sub_i < len(args) else ""
        if any(a in ("-C", "--git-dir", "--work-tree") for a in args[:sub_i]):
            s.unanalyzable.append("git com -C/--git-dir/--work-tree")
            return
        s.git.append((sub, args[sub_i + 1:]))
        if sub in ("branch", "tag", "remote", "config") and len(args) > sub_i + 1 and sub != "config":
            # branch/tag/remote com argumentos alteram refs (não a árvore) — tratados como git de lead
            pass
        return
    if prog == "sed":
        inplace = any(a.startswith("--in-place") or (a.startswith("-") and not a.startswith("--") and "i" in a[1:])
                      for a in args)
        has_e = any(a in ("-e", "-f") or a.startswith("--expression") for a in args)
        script_args = [a for a in nonopt]
        script = None if has_e else (script_args[0] if script_args else None)
        texts = [script] if script else []
        for j, a in enumerate(args):
            if a == "-e" and j + 1 < len(args):
                texts.append(args[j + 1])
        if any(re.search(r"(^|[;}\s/])w\s*\S", t or "") or re.search(r"(^|[;}\s])[wW]\b", t or "") for t in texts):
            s.unanalyzable.append("sed com comando w (escrita em arquivo)")
            return
        if inplace:
            files = script_args[1:] if not has_e else [a for a in script_args if a not in texts]
            if not files:
                s.unanalyzable.append("sed -i sem arquivo identificável")
            for f in files:
                _add_write(s, state, f, "sed -i")
        return
    if prog in ("awk", "gawk", "mawk", "nawk"):
        if any("inplace" in a for a in args) or any(">" in a or "system(" in a for a in args):
            s.unanalyzable.append("awk com escrita/inplace/system()")
        return
    if prog == "find":
        if any(a in ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls") for a in args):
            s.unanalyzable.append("find com -delete/-exec/-fprint")
        return
    if prog == "sort":
        for j, a in enumerate(args):
            if a == "-o" and j + 1 < len(args):
                _add_write(s, state, args[j + 1], "sort -o")
            elif a.startswith("-o") and len(a) > 2:
                _add_write(s, state, a[2:], "sort -o")
            elif a.startswith("--output="):
                _add_write(s, state, a.split("=", 1)[1], "sort --output")
        return
    if prog == "dd":
        for a in args:
            if a.startswith("of="):
                _add_write(s, state, a[3:], "dd of=")
        return
    if prog in WRITE_ALL_ARGS:
        if not nonopt and prog not in ("tee",):
            s.unanalyzable.append("%s sem alvo identificável" % prog)
        for a in nonopt:
            _add_write(s, state, a, prog)
        return
    if prog in WRITE_SKIP_FIRST:
        for a in nonopt[1:]:
            _add_write(s, state, a, prog)
        return
    if prog in WRITE_ALL_INCL_SRC:
        if len(nonopt) < 2:
            s.unanalyzable.append("mv sem origem/destino")
        for a in nonopt:
            _add_write(s, state, a, prog)
        return
    if prog in WRITE_DEST:
        tdir = None
        for j, a in enumerate(args):
            if a in ("-t", "--target-directory") and j + 1 < len(args):
                tdir = args[j + 1]
            elif a.startswith("--target-directory="):
                tdir = a.split("=", 1)[1]
        if tdir:
            _add_write(s, state, tdir, prog)
        elif nonopt:
            dest = nonopt[-1]
            if ":" in dest and prog in ("rsync", "scp"):
                return  # destino remoto
            _add_write(s, state, dest, prog)
        else:
            s.unanalyzable.append("%s sem destino" % prog)
        return
    if prog in ("patch",):
        s.unanalyzable.append("patch altera arquivos listados no próprio diff")
        return
    # demais programas: sem alvo de escrita visível (limite documentado)
    return


def git_effect(sub):
    """'read' | 'lead' | 'tree' (reescreve árvore de trabalho)."""
    if sub in GIT_READONLY or sub == "":
        return "read"
    if sub in GIT_LEAD_OK:
        return "lead"
    return "tree"
