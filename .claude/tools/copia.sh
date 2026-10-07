#!/bin/bash
# copia.sh <feature> [--force] [--dry-run] — cria a cópia de trabalho da feature: `git archive HEAD` da skill em
# <local>/work/<feature>/codebase-specialists/ e imprime o caminho. O corretor (agente) só escreve ali.
# Já existe ⇒ recusa (não apaga trabalho); --force recria do zero. --dry-run: só mostra o que faria.
set -eu
case "${1:-}" in -h|--help|'') sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
. "$(dirname "$0")/_comum.sh"
F="$1"; shift; feature_ok "$F"
FORCE=0; DRY=0
for a in "$@"; do case "$a" in --force) FORCE=1;; --dry-run) DRY=1;; *) die "opção desconhecida: $a";; esac; done
[ -n "$REPO" ] || die "a skill não está num repositório git: $SKILL"
DEST="$WS/work/$F"
if [ -e "$DEST/$NOME" ] && [ "$FORCE" -ne 1 ]; then
  echo "já existe: $DEST/$NOME (não mexi; use --force para recriar do HEAD, apagando o trabalho de lá)"; exit 1
fi
if [ "$DRY" -eq 1 ]; then
  echo "faria: rm -rf $DEST; git -C $REPO archive HEAD:$PFX | tar -x -C $DEST/$NOME"; exit 0
fi
rm -rf "$DEST"; mkdir -p "$DEST"
archive_head "$DEST/$NOME"
echo "cópia de trabalho (HEAD $(git -C "$REPO" rev-parse --short HEAD)): $DEST/$NOME"
