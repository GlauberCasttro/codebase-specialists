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


STDIN_NAMES = {"-", "/dev/stdin", "/dev/fd/0", "/proc/self/fd/0"}
MODULE_TOOLS = {"state": "state", "validate": "validate", "mem": "mem", "guard": "guard", "session": "session",
                "router": "route"}


def _parse_interp(prog, args):
    """{"inline", "module", "script", "rest"} de um interpretador, entendendo flags com valor (python -W/-X)
    e flags curtas combinadas (-Sc, -Ic, -uc, -ne, -pe)."""
    info = {"inline": False, "module": None, "script": None, "rest": []}
    py = prog.startswith("python")
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-" or not a.startswith("-"):
            info["script"], info["rest"] = a, args[i + 1:]
            return info
        if a == "--":
            if i + 1 < len(args):
                info["script"], info["rest"] = args[i + 1], args[i + 2:]
            return info
        if a.startswith("--"):
            if a in INLINE_FLAGS:
                info["inline"] = True
            elif a in ("--eval", "--print") or a.startswith("--eval="):
                info["inline"] = True
            i += 1
            continue
        if py:
            consumed = 1
            for k, ch in enumerate(a[1:], 1):
                if ch == "c":
                    info["inline"] = True
                    break
                if ch in "WXQ":
                    consumed = 1 if k < len(a) - 1 else 2
                    break
                if ch == "m":
                    if k < len(a) - 1:
                        info["module"], info["rest"] = a[k + 1:], args[i + 1:]
                    elif i + 1 < len(args):
                        info["module"], info["rest"] = args[i + 1], args[i + 2:]
                    else:
                        info["inline"] = True  # -m sem módulo: fail-closed
                    return info
            if info["inline"]:
                return info
            i += consumed
            continue
        if a in INLINE_FLAGS or any(ch in "ceEp" for ch in a[1:]) or (prog == "perl" and "i" in a[1:]):
            info["inline"] = True
            return info
        i += 1
    return info


def _harness_script(s, state, hp, script, rest):
    """Script de arquivo (sh|bash <script>, python3 [-W v] <script>): se for do harness vira harness_call."""
    if _expandable(script):
        norm = os.path.normpath(script)  # fail-closed: '.swarm//harness', '.swarm/./bin', 'x/../harness' casam
        m = re.search(r"(?:^|/)\.swarm/((?:harness|bin)/.*)$", norm)
        if not m:
            if ".swarm" in norm.split("/"):
                s.unanalyzable.append("script sob .swarm por variável/~ não resolvido: %r" % script)
            return  # script comum com variável: segue como antes
        suf = os.path.normpath(m.group(1))
        base = hp.get("state") and os.path.dirname(os.path.dirname(hp["state"]))
        cand = os.path.realpath(os.path.join(base, suf)) if base and not _expandable(suf) else None
        for key, path in hp.items():
            if cand and path and cand == path:
                s.harness_calls.append({"tool": key.replace("bin_", ""), "argv": rest, "cwd": state["cwd"]})
                return
        s.unanalyzable.append("script do harness por variável/~ não resolvido: %r" % script)
        return
    sp = _resolve(state, script)
    if not sp:
        return
    rp = os.path.realpath(sp)
    for key, path in hp.items():
        if path and rp == path:
            s.harness_calls.append({"tool": key.replace("bin_", ""), "argv": rest, "cwd": state["cwd"]})
            return


WRITER_FLAGS = {  # programa → (flags longas com valor, flags curtas com valor): destino que o programa grava
    "curl": (("--output", "--output-dir", "--dump-header"), ("-o", "-D")),
    "wget": (("--output-document", "--directory-prefix", "--output-file"), ("-O", "-P", "-o")),
    "tar": (("--directory",), ("-C",)),
    "unzip": ((), ("-d",)),
    "dotnet": (("--output",), ("-o",)),
}


def _flag_dests(s, state, args, longs, shorts, why):
    """Destinos de escrita dados por flags: `--output=X`, `--output X`, `-o X`, `-oX`, `-o:X`, `-sSo X`."""
    for j, a in enumerate(args):
        if a == "--":
            break
        nxt = args[j + 1] if j + 1 < len(args) else None
        for lf in longs:
            if a == lf and nxt is not None:
                _add_write(s, state, nxt, why)
            elif a.startswith(lf + "="):
                _add_write(s, state, a.split("=", 1)[1], why)
        if not a.startswith("-") or a.startswith("--") or len(a) < 2:
            continue
        for sf in shorts:
            c = sf[1]
            k = a.find(c, 1)
            if k < 0:
                continue
            if k == len(a) - 1:
                if nxt is not None:
                    _add_write(s, state, nxt, why)
            elif k == 1:
                v = a[2:]
                _add_write(s, state, v[1:] if v[:1] in ":=" else v, why)
            elif a[1:k].isalpha():
                if nxt is not None:  # cluster com valor no meio (ex.: tar -xCf dir): o valor é o próximo argumento
                    _add_write(s, state, nxt, why)


def _is_hardlink(prog, args):
    if prog == "ln":
        sym = any(a == "--symbolic" or (a.startswith("-") and not a.startswith("--") and "s" in a[1:]) for a in args)
        return not sym
    if prog == "cp":
        return any(a == "--link" or (a.startswith("-") and not a.startswith("--") and "l" in a[1:]) for a in args)
    return False


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
            return
        files = [a for a in nonopt if a != "-"]
        if not files or any(a in STDIN_NAMES for a in nonopt[:1]) or (nonopt and nonopt[0] == "-"):
            s.unanalyzable.append("%s lendo comandos do stdin" % prog)
            return
        _harness_script(s, state, hp, files[0], args[args.index(files[0]) + 1:])
        return
    if prog in INTERPRETERS or re.match(r"^python\d+(\.\d+)?$", prog):
        info = _parse_interp(prog, args)
        if info["inline"]:
            s.unanalyzable.append("%s com código inline/in-place (escreva um script em arquivo)" % prog)
            return
        if info["module"]:
            tool = MODULE_TOOLS.get(info["module"])
            if tool:
                s.harness_calls.append({"tool": tool, "argv": info["rest"], "cwd": state["cwd"]})
            return
        script = info["script"]
        if script is None or script in STDIN_NAMES:
            s.unanalyzable.append("%s lendo código do stdin" % prog)
            return
        _harness_script(s, state, hp, script, info["rest"])
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
        for j in range(sub_i):  # git -c core.hooksPath=... <sub>
            if args[j] == "-c" and j + 1 < len(args) and re.match(r"(?i)^core\.hookspath(=|$)", args[j + 1]):
                s.unanalyzable.append("git -c core.hooksPath (desliga os hooks)")
                return
        _flag_dests(s, state, args[sub_i + 1:], ("--output",), (), "git --output")
        if sub == "format-patch":
            _flag_dests(s, state, args[sub_i + 1:], ("--output-directory",), ("-o",), "git format-patch")
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
    if prog in WRITER_FLAGS:
        longs, shorts = WRITER_FLAGS[prog]
        _flag_dests(s, state, args, longs, shorts, prog)
        return
    if prog in WRITE_DEST:
        if _is_hardlink(prog, args):  # ln / cp -l: a ORIGEM também é conferida (o destino vira o mesmo inode)
            tdirs = [a for j, a in enumerate(args) if j and args[j - 1] in ("-t", "--target-directory")]
            srcs = nonopt if tdirs else nonopt[:-1]
            for a in srcs:
                _add_write(s, state, a, "%s (hardlink da origem)" % prog)
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


def _short_has(args, ch):
    return any(a.startswith("-") and not a.startswith("--") and ch in a[1:] for a in args)


def _is_listing(sub, args):
    """branch/remote/config/reflog/tag sem alterar nada (só listar/consultar)."""
    pos = [a for a in args if not a.startswith("-")]
    flags = [a for a in args if a.startswith("-")]
    if sub == "branch":
        mut = ("-d", "-D", "-m", "-M", "-c", "-C", "-f", "-u", "--delete", "--move", "--copy", "--force",
               "--set-upstream-to", "--unset-upstream", "--edit-description", "--track", "--no-track")
        if any(f in mut or f.startswith("--set-upstream-to=") for f in flags):
            return False
        listing = any(f in ("-l", "--list", "-a", "-r", "--all", "--remotes", "--show-current", "--merged", "--no-merged",
                            "--contains", "--no-contains", "--points-at") for f in flags)
        return not pos or listing
    if sub == "remote":
        return not pos or pos[0] in ("show", "get-url")
    if sub == "reflog":
        return not pos or pos[0] not in ("expire", "delete")
    if sub == "config":
        if any(f in ("--get", "--get-all", "--get-regexp", "--list", "-l", "--show-origin", "--show-scope", "--get-urlmatch")
               for f in flags):
            return True
        if any(f in ("--unset", "--unset-all", "--add", "--replace-all", "--edit", "-e", "--rename-section",
                     "--remove-section") for f in flags):
            return False
        return len(pos) <= 1
    return True


def git_effect(sub, args=None):
    """'read' | 'lead' | 'tree' (reescreve árvore de trabalho). Com `args`, branch/remote/config/reflog que
    alteram refs/config contam como 'lead' (o subagente não roda)."""
    if sub in GIT_READONLY or sub == "":
        if args is not None and sub in ("branch", "remote", "config", "reflog") and not _is_listing(sub, args):
            return "lead"
        return "read"
    if sub in GIT_LEAD_OK:
        return "lead"
    return "tree"


def _cluster_has_n(a):
    """`-n`/`-nm`/`-anm` (git commit): flags curtas até a primeira que leva valor (m, F, C, c, S, u)."""
    if not a.startswith("-") or a.startswith("--"):
        return False
    for ch in a[1:]:
        if ch == "n":
            return True
        if ch in "mFCcSu":
            return False
    return False


def _long_abbrev(a, full, minimum):
    """Abreviação de opção longa que o git aceita (`--no-veri` = `--no-verify`): prefixo de `full` com ao menos
    `minimum` caracteres (o mínimo que a torna única entre as opções do git)."""
    a = a.split("=", 1)[0]
    return len(a) >= len(minimum) and full.startswith(a)


def git_problem(sub, args, protected_branches):
    """Motivo para recusar um git que desliga proteção ou reescreve remoto/ref protegido (qualquer ator); None = ok."""
    args = list(args or [])
    prot = set(protected_branches or [])
    low = [a.lower() for a in args]
    if sub == "config" and not _is_listing(sub, args) and any(
            re.match(r"^(core\.hookspath|remote\.[^=]*\.(url|pushurl))(=|$)", a) for a in low):
        return "git config de core.hooksPath/remote.*.url desliga os hooks ou reaponta o remoto: ato humano"
    if sub in ("commit", "merge", "push", "am", "cherry-pick", "rebase", "revert"):
        skip = False
        for a in args:
            if skip:
                skip = False
                continue
            if a == "--":
                break  # depois de '--' é pathspec, não opção
            if a in ("-m", "-F", "-C", "-c", "--message", "--file"):
                skip = True
                continue
            if _long_abbrev(a, "--no-verify", "--no-veri") or (sub == "commit" and _cluster_has_n(a)):
                return "git %s --no-verify/-n pula os hooks (pre-commit do harness): recusado" % sub
    if sub == "push":
        refs = []
        for a in args:
            if a in ("-f", "--force", "--delete", "--mirror", "-d") or a.startswith("--force") or a.startswith("--delete") \
                    or _long_abbrev(a, "--force", "--forc") or _long_abbrev(a, "--mirror", "--mi") \
                    or _long_abbrev(a, "--delete", "--de"):
                return "git push %s reescreve/apaga ref remota: ato humano" % a
            if a.startswith("-") and not a.startswith("--") and ("f" in a[1:] or "d" in a[1:]):
                return "git push %s reescreve/apaga ref remota: ato humano" % a
            if not a.startswith("-"):
                if a.startswith("+"):
                    return "git push %s: refspec com '+' força a atualização (= --force): ato humano" % a
                refs.append(a)
        for a in refs:
            dst = a.lstrip("+").split(":")[-1]
            dst = dst[len("refs/heads/"):] if dst.startswith("refs/heads/") else dst
            if dst in prot:
                return "push em branch protegida %s" % dst
    if sub == "branch":
        names = [a for a in args if not a.startswith("-")]
        destructive = any(a in ("-d", "-D", "-m", "-M", "-f", "--force", "--delete", "--move") or
                          (a.startswith("-") and not a.startswith("--") and any(c in a[1:] for c in "dDmMf"))
                          for a in args)
        if destructive and any(n in prot for n in names):
            return "git branch apaga/move/força branch protegida"
    if sub == "remote":
        pos = [a for a in args if not a.startswith("-")]
        if pos and pos[0] in ("set-url", "add", "remove", "rm", "rename", "set-branches", "set-head"):
            return "git remote %s reaponta/altera o remoto: ato humano" % pos[0]
    if sub == "reflog":
        pos = [a for a in args if not a.startswith("-")]
        if pos and pos[0] in ("expire", "delete"):
            return "git reflog %s apaga o histórico de recuperação: recusado" % pos[0]
    return None
