#!/usr/bin/env python3
"""guard_git.py — lógica do hook PreToolUse Bash `guard-git.sh` (harness de desenvolvimento da codebase-specialists).

NEGA, quando o comando chama git (inclusive `git -C x`, `/usr/bin/git`, dentro de `sh -c '...'`, após `;` `&&` `|`):
  a) reset --hard                     (apaga trabalho não commitado de outras frentes/sessões)
  b) checkout ... -- <path>  e  restore sem --staged   (descarta alteração do worktree)
  c) clean -f / --force (qualquer combinação)
  d) stash (exceto `stash list` / `stash show`)
  e) push (SEMPRE — push só pelo humano, no terminal dele)
  f) add -A / --all / `add .` / `add :/`  (só entram os arquivos da frente; adicione arquivo por arquivo)
  g) commit -a / --all / -am          (mesmo motivo: só entram os arquivos da frente)
Permite todo o resto (status, log, diff, show, archive, add <arquivo>, commit -F <arquivo>, merge-file...).

Contrato: payload JSON pela stdin; negar = stdout hookSpecificOutput/deny + exit 0; permitir = exit 0 sem saída.
Payload inválido: nega só se o texto bruto citar git + verbo perigoso; senão permite (não trava o Bash à toa).
LIMITE HONESTO: filtro sintático sobre a string do comando, não sandbox (eval de texto montado, script escrito e
executado depois etc. escapam). Torna o erro DELIBERADO e visível, não impossível.
"""
import json
import os
import re
import shlex
import sys

SEP = re.compile(r"\|\||&&|;|\||\n|&|\$\(|`|\(|\)")
WRAPPERS = {"env", "nohup", "exec", "command", "builtin", "sudo", "nice", "time", "noglob", "caffeinate", "xargs"}
SHELLS = {"sh", "bash", "zsh", "dash"}
GIT_OPTS_COM_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix"}
PERIGO_RAW = re.compile(r"\bgit\b.*\b(reset|clean|stash|push|checkout|restore|add|commit)\b", re.S)


def negar(motivo):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": "guard-git: " + motivo +
                                             " (regras em .claude/CLAUDE.md § Git)"}}, ensure_ascii=False))
    return 0


def tokens(seg):
    try:
        return shlex.split(seg, posix=True)
    except ValueError:
        return [x.strip("'\"") for x in seg.split()]


def segmentos(cmd):
    """Segmentos de comando simples. Primeiro tenta o shlex (respeita aspas: `sh -c 'a && b'` fica inteiro);
    se as aspas não fecham, cai no corte por regex (pior, mas não deixa passar)."""
    texto = cmd.replace("\n", " ; ").replace("$(", " ; ").replace("`", " ; ")
    try:
        lx = shlex.shlex(texto, posix=True, punctuation_chars=";&|()")
        lx.whitespace_split = True
        toks = list(lx)
    except ValueError:
        for seg in SEP.split(cmd):
            yield tokens(seg)
        return
    atual = []
    for t in toks:
        if t and all(c in ";&|()" for c in t):
            if atual:
                yield atual
            atual = []
        else:
            atual.append(t)
    if atual:
        yield atual


def git_calls(cmd, depth=0):
    """Gera (args_depois_do_subcomando, subcomando, globais) para cada chamada de git no texto."""
    if depth > 3:
        return
    for t in segmentos(cmd):
        i = 0
        while i < len(t) and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t[i]) or t[i] in WRAPPERS):
            i += 1
        if i >= len(t):
            continue
        prog = os.path.basename(t[i])
        if prog in SHELLS:
            for j in range(i + 1, len(t) - 1):
                if t[j] in ("-c", "-lc", "-ic"):
                    for x in git_calls(t[j + 1], depth + 1):
                        yield x
            continue
        if prog != "git":
            continue
        j = i + 1
        glob_opts = []
        while j < len(t) and t[j].startswith("-"):
            o = t[j]
            glob_opts.append(o)
            if o in GIT_OPTS_COM_ARG:
                j += 1
                if j < len(t):
                    glob_opts.append(t[j])
            j += 1
        if j >= len(t):
            continue
        yield t[j], t[j + 1:], glob_opts


def curtas(args):
    """Flags curtas agrupadas: -fdx → {'f','d','x'}; -am → {'a','m'}."""
    s = set()
    for a in args:
        if re.match(r"^-[A-Za-z]+$", a):
            s.update(a[1:])
    return s


def avaliar(cmd):
    for sub, args, _glob in git_calls(cmd):
        if sub == "reset" and "--hard" in args:
            return "`git reset --hard` apaga trabalho não commitado (de outras frentes também)."
        if sub == "checkout" and "--" in args:
            return "`git checkout -- <path>` descarta alteração do worktree sem cópia."
        if sub == "restore" and "--staged" not in args and "-S" not in args:
            return "`git restore` (worktree) descarta alteração sem cópia; use `--staged` para só tirar do índice."
        if sub == "clean" and ("--force" in args or "f" in curtas(args)):
            return "`git clean -f` apaga arquivo não rastreado, irreversível."
        if sub == "stash" and not (args and args[0] in ("list", "show")):
            return "`git stash` tira trabalho da vista (já foi dado como perdido)."
        if sub == "push":
            return "`git push` é só do humano, no terminal dele."
        if sub == "add" and ("-A" in args or "--all" in args or "." in args or ":/" in args or "A" in curtas(args)):
            return "`git add -A/--all/.` pega frentes alheias; adicione os arquivos da frente um a um."
        if sub == "commit" and ("--all" in args or "a" in curtas(args)):
            return "`git commit -a` pega alterações de outras frentes; faça `git add <arquivos>` + `commit -F`."
    return None


def decidir(raw):
    try:
        d = json.loads(raw)
        cmd = (d.get("tool_input") or {}).get("command") or ""
        if not isinstance(cmd, str):
            raise ValueError("command não é texto")
    except Exception as e:  # noqa: BLE001
        if PERIGO_RAW.search(raw or ""):
            return negar("payload inválido (%s) citando git + verbo perigoso — falha fechada." % e)
        return 0
    if (d.get("tool_name") or "Bash") != "Bash" or not cmd.strip():
        return 0
    motivo = avaliar(cmd)
    return negar(motivo) if motivo else 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    return decidir(sys.stdin.read())


if __name__ == "__main__":
    sys.exit(main())
