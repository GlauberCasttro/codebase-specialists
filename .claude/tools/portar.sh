#!/bin/bash
# portar.sh <feature> [--dry-run] [--src DIR] [--lista ARQ] -- <arquivo>...
# Leva os arquivos da feature da cópia de trabalho (<local>/work/<feature>/codebase-specialists, ou --src) para a
# skill VIVA (a raiz do projeto).
# Por arquivo: se o vivo == HEAD (ninguém mexeu), copia; se o vivo mudou desde HEAD (outra sessão/feature), faz merge
# de 3 vias (git merge-file; base = HEAD, nosso = vivo, deles = cópia) e PARA em conflito sem escrever aquele
# arquivo. Arquivo ausente na cópia = remoção (só se o vivo == HEAD).
# Depois de um merge, o vivo difere da cópia testada: rode o portão de novo com --src <skill viva>.
# Escreve por Bash (cp): o guard-entrega só cobre Edit/Write — este é o caminho oficial.
set -u
case "${1:-}" in -h|--help|'') sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
. "$(dirname "$0")/_comum.sh"
F="$1"; shift; feature_ok "$F"; SRC="$WS/work/$F/$NOME"; DRY=0; ARQS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift;;
    --src) SRC="$2"; shift 2;;
    --lista) while IFS= read -r l; do [ -n "$l" ] && ARQS+=("$l"); done < "$2"; shift 2;;
    --) shift; while [ $# -gt 0 ]; do ARQS+=("$1"); shift; done;;
    *) die "opção desconhecida: $1";;
  esac
done
[ ${#ARQS[@]} -gt 0 ] || die "nenhum arquivo (passe depois de -- ou com --lista)"
[ -d "$SRC" ] || die "cópia de trabalho inexistente: $SRC"
TMP="$WS/work/.portar-$F"; rm -rf "$TMP"; mkdir -p "$TMP"
CONF=0; MERGES=0
for f in "${ARQS[@]}"; do
  case "$f" in /*|../*|*/../*) echo "INVÁLIDO (precisa ser relativo à skill): $f"; CONF=1; continue;; esac
  w="$SRC/$f"; v="$SKILL/$f"; b="$TMP/base"
  if git -C "$REPO" cat-file -e "HEAD:$PFX$f" 2>/dev/null; then show_head "$f" > "$b"; tem_base=1
  else : > "$b"; tem_base=0; fi
  vivo_igual_head=0
  if [ -e "$v" ]; then [ $tem_base -eq 1 ] && cmp -s "$v" "$b" && vivo_igual_head=1
  else [ $tem_base -eq 0 ] && vivo_igual_head=1; fi
  if [ ! -e "$w" ]; then
    if [ ! -e "$v" ]; then echo "já ausente: $f"
    elif [ $vivo_igual_head -eq 1 ]; then echo "REMOVE: $f"; [ $DRY -eq 1 ] || rm -f "$v"
    else echo "CONFLITO (a feature remove, mas o vivo mudou desde HEAD): $f"; CONF=1; fi
    continue
  fi
  if [ -e "$v" ] && cmp -s "$w" "$v"; then echo "igual: $f"; continue; fi
  if [ $vivo_igual_head -eq 1 ]; then
    echo "COPIA: $f"; [ $DRY -eq 1 ] || { mkdir -p "$(dirname "$v")"; cp -p "$w" "$v"; }
  else
    m="$TMP/merged"
    [ -e "$v" ] && cp "$v" "$m" || : > "$m"
    if git merge-file -p "$m" "$b" "$w" > "$TMP/out" 2>/dev/null; then
      echo "MERGE 3 vias limpo (o vivo mudou desde HEAD): $f"; MERGES=1
      [ $DRY -eq 1 ] || cp "$TMP/out" "$v"
    else
      echo "CONFLITO no merge de 3 vias (não escrevi): $f"; CONF=1
    fi
  fi
done
rm -rf "$TMP"
[ $DRY -eq 1 ] && echo "(dry-run: nada escrito)"
[ $MERGES -eq 1 ] && echo "ATENÇÃO: houve merge — rode o portão de novo com --src $SKILL antes de conferir-commit."
[ $CONF -eq 1 ] && { echo "PARADO: resolva os conflitos (ou devolva à feature) antes de seguir."; exit 1; }
exit 0
