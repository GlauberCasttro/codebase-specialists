#!/bin/bash
# conferir-commit.sh <frente> [--lista ARQ] -- <arquivo>...
# Regra: só entra no commit o que o portão testou. Confere, para cada arquivo (relativo à skill):
#   - o portão da frente terminou (FIM) e VERDE (<local>/portao-<frente>/portao.out);
#   - o arquivo está na lista testada (arquivos.txt) e a lista testada inteira foi passada;
#   - o arquivo VIVO é byte a byte igual à cópia testada (cmp); removido lá ⇒ removido aqui.
# Qualquer diferença ⇒ exit 1 e a lista. Só lê; não escreve nada.
set -u
case "${1:-}" in -h|--help|'') sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
. "$(dirname "$0")/_comum.sh"
F="$1"; shift; frente_ok "$F"; ARQS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --lista) while IFS= read -r l; do [ -n "$l" ] && ARQS+=("$l"); done < "$2"; shift 2;;
    --) shift; while [ $# -gt 0 ]; do ARQS+=("$1"); shift; done;;
    *) die "opção desconhecida: $1";;
  esac
done
[ ${#ARQS[@]} -gt 0 ] || die "nenhum arquivo (passe depois de -- ou com --lista)"
G="$WS/portao-$F"; OUT="$G/portao.out"; ERR=0
[ -f "$OUT" ] || die "portão da frente $F não existe: $OUT"
tail -1 "$OUT" | grep -qx FIM || { echo "PORTÃO INCOMPLETO: $OUT não termina em FIM"; ERR=1; }
grep -qx "RESULTADO: VERDE" "$OUT" || { echo "PORTÃO NÃO VERDE: $(grep '^RESULTADO' "$OUT" || echo 'sem RESULTADO')"; ERR=1; }
for f in "${ARQS[@]}"; do
  grep -qxF "$f" "$G/arquivos.txt" || { echo "FORA DO PORTÃO: $f"; ERR=1; continue; }
  vivo="$SKILL/$f"; testado="$G/$NOME/$f"
  if [ ! -e "$testado" ]; then
    [ -e "$vivo" ] && { echo "DIFERE (removido no portão, existe vivo): $f"; ERR=1; }
  elif [ ! -e "$vivo" ]; then echo "DIFERE (ausente na skill viva): $f"; ERR=1
  elif ! cmp -s "$vivo" "$testado"; then echo "DIFERE: $f"; ERR=1
  fi
done
while IFS= read -r t; do
  achou=0; for f in "${ARQS[@]}"; do [ "$f" = "$t" ] && achou=1; done
  [ $achou -eq 1 ] || { echo "TESTADO MAS NÃO PASSADO (o commit ficaria diferente do portão): $t"; ERR=1; }
done < "$G/arquivos.txt"
if [ $ERR -eq 0 ]; then echo "OK: ${#ARQS[@]} arquivo(s) idênticos ao portão VERDE da frente $F"; fi
exit $ERR
