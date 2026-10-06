#!/bin/sh
# guard-privacidade.sh [DIR|ARQ ...] | --staged | --msg ARQ | --git-log | --termos  [--json]
# Grep de termos privados. Termos em local/termos-privados.txt (gitignored; nunca versionado); sem o arquivo, avisa
# e usa só os padrões genéricos (caminho de usuário, e-mail pessoal). Exit 1 = achou algo. Lógica em
# guard_privacidade.py. Chamado pelo pre-commit do harness (tools/pre-commit.sh) e pelo tools/package.sh.
case "${1:-}" in -h|--help) exec python3 "$(dirname "$0")/guard_privacidade.py" --help ;; esac
exec python3 "$(dirname "$0")/guard_privacidade.py" "$@"
