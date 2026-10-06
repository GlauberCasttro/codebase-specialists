#!/bin/sh
# instalar-hooks-git.sh [--dry-run] — liga o pre-commit.sh do harness como hooks git `pre-commit` e `commit-msg`
# deste repositório (.git/hooks/, que não é versionado). Hook já existente e diferente ⇒ não sobrescreve.
case "${1:-}" in -h|--help) sed -n '2,3p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
R="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" || exit 1
H="$(git -C "$R" rev-parse --git-path hooks)"; case "$H" in /*) ;; *) H="$R/$H";; esac
mkdir -p "$H"
for n in pre-commit commit-msg; do
  alvo="$H/$n"; linha='exec sh "$(git rev-parse --show-toplevel)/.claude/tools/pre-commit.sh" "$@"'
  if [ -e "$alvo" ] && ! grep -qF "$linha" "$alvo"; then echo "já existe outro $n em $alvo — não mexi"; continue; fi
  if [ "${1:-}" = "--dry-run" ]; then echo "faria: $alvo"; continue; fi
  printf '#!/bin/sh\n%s\n' "$linha" > "$alvo"; chmod +x "$alvo"; echo "instalado: $alvo"
done
