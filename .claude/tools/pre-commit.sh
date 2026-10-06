#!/bin/sh
# pre-commit.sh — hook git do harness (pre-commit e commit-msg). Instale com tools/instalar-hooks-git.sh.
#   como pre-commit: guard-privacidade --staged (nomes e conteúdo do índice);
#   como commit-msg (recebe o arquivo da mensagem): guard-privacidade --msg <arquivo>.
# Termo privado ⇒ exit 1 e o commit não acontece. --help mostra isto.
case "${1:-}" in -h|--help) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
D="$(git rev-parse --show-toplevel)/.claude/tools"
if [ -n "${1:-}" ] && [ -f "$1" ]; then
  exec python3 "$D/guard_privacidade.py" --msg "$1"
fi
exec python3 "$D/guard_privacidade.py" --staged
