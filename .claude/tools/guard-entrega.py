#!/usr/bin/env python3
"""guard-entrega.py — hook PreToolUse (Edit|Write|MultiEdit|NotebookEdit) do harness de desenvolvimento.

Nega Edit/Write em arquivos do PRODUTO da skill codebase-specialists (tudo dentro do projeto, inclusive o próprio
.claude/ e o motor embutido .claude/tools/ac/), EXCETO: `.claude/state/**` (estado), `campanhas/**` (oráculos e
relatórios das campanhas), `local/**` (cópias de trabalho, portões, notas privadas — gitignored) e `dist/**` (pacote
gerado). Fora do projeto é permitido. Mudança no produto entra só pelo fluxo de entrega:
  frente (campanha) → cópia de trabalho (tools/copia.sh) → portão (tools/portao.sh) → tools/portar.sh → commit.

Contrato (Claude Code): payload JSON pela stdin (tool_name, tool_input.file_path|notebook_path, cwd).
Negar = stdout {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",
"permissionDecisionReason":...}} e exit 0. Permitir = exit 0 sem saída.
Payload inválido ou sem caminho numa ferramenta de escrita = NEGA com motivo (falha fechada).

LIMITE HONESTO: só vê as ferramentas Edit/Write/MultiEdit/NotebookEdit. Escrita por Bash (sed -i, cp, >, python)
NÃO passa por aqui — é por isso que portar.sh funciona e é também por isso que a regra continua valendo por escrito.

Uso direto:  echo '<payload>' | python3 guard-entrega.py      ·  python3 guard-entrega.py --help
Variável de teste: CS_DEV_SKILL_DIR (raiz do projeto; padrão: dois níveis acima deste arquivo).
"""
import json
import os
import sys

FERRAMENTAS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
LIVRES = (".claude/state", "campanhas", "local", "dist")


def skill_dir():
    d = os.environ.get("CS_DEV_SKILL_DIR")
    if d:
        return os.path.realpath(d)
    return os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def negar(motivo):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": motivo}}, ensure_ascii=False))
    return 0


def dentro(p, base):
    return p == base or p.startswith(base + os.sep)


FLUXO = ("Mudança no produto da skill só pelo fluxo de entrega (.claude/CLAUDE.md): abra/retome a frente "
         "(skill criar-frente; execução pela skill tech-lead), trabalhe na cópia de trabalho (`bash .claude/tools/copia.sh <frente>`), rode "
         "`.claude/tools/portao.sh`, depois `.claude/tools/portar.sh` e `.claude/tools/conferir-commit.sh`. "
         "Editável direto: `.claude/state/**`, `campanhas/**`, `local/**`, `dist/**`.")


def decidir(raw):
    try:
        d = json.loads(raw)
        if not isinstance(d, dict):
            raise ValueError("payload não é objeto")
    except Exception as e:  # noqa: BLE001
        return negar("guard-entrega: payload inválido (%s) — falha fechada." % e)
    tool = d.get("tool_name") or ""
    if tool not in FERRAMENTAS:
        return 0
    ti = d.get("tool_input") or {}
    if not isinstance(ti, dict):
        return negar("guard-entrega: tool_input inválido — falha fechada.")
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    if not isinstance(path, str) or not path.strip():
        return negar("guard-entrega: %s sem file_path — falha fechada." % tool)
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        cwd = d.get("cwd") or os.getcwd()
        path = os.path.join(cwd, path)
    real = os.path.realpath(path)
    sk = skill_dir()
    if not dentro(real, sk):
        return 0
    for livre in LIVRES:
        if dentro(real, os.path.join(sk, *livre.split("/"))):
            return 0
    rel = os.path.relpath(real, sk)
    return negar("guard-entrega: %s em `%s` NEGADO — é produto da skill. %s" % (tool, rel, FLUXO))


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    return decidir(sys.stdin.read())


if __name__ == "__main__":
    sys.exit(main())
