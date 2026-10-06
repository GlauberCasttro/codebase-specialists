#!/bin/sh
# guard-git.sh — hook PreToolUse Bash do harness de desenvolvimento da codebase-specialists.
# Nega reset --hard, checkout --/restore, clean -f, stash, push (sempre), add -A/--all/., commit -a.
# A lógica (e os limites honestos) estão em guard_git.py; este arquivo só a chama.
# uso: echo '<payload JSON>' | sh guard-git.sh      ·  sh guard-git.sh --help
case "$1" in -h|--help) exec python3 "$(dirname "$0")/guard_git.py" --help ;; esac
command -v python3 >/dev/null 2>&1 || {
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"guard-git: python3 ausente; confirme o comando à mão"}}'
  exit 0; }
exec python3 "$(dirname "$0")/guard_git.py"
