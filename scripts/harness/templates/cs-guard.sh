#!/bin/sh
# cs-guard.sh — wrapper FAIL-CLOSED dos hooks do harness codebase-specialists (gerado por `cs.py harness install`).
# Compatível com sh/bash 3.2. Não editar: reinstale. Raiz do projeto = $CLAUDE_PROJECT_DIR (lido pelo motor).
HERE=$(cd "$(dirname "$0")" 2>/dev/null && pwd -P)
ENGINE="$HERE/../../.swarm/harness/guard.py"
MODE="$1"
PY=$(command -v python3 2>/dev/null)
if [ -z "$PY" ] || [ ! -f "$ENGINE" ]; then
  case "$MODE" in
    pre-*) echo "cs-guard: python3 ou motor ausente ($ENGINE) — bloqueado (fail-closed)" >&2; exit 2 ;;
    *) exit 0 ;;
  esac
fi
exec "$PY" "$ENGINE" "$@"
