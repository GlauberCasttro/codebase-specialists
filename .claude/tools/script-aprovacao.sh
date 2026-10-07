#!/bin/bash
# script-aprovacao.sh <frente> [--por NOME] [--criterio TXT] [--oraculo TXT] [--requires "s1 s2"] [--dry-run]
# GERA (não roda) o script de aprovação humana da frente em local/aprovar-<frente>.sh — gitignored, porque leva os
# caminhos absolutos desta máquina. O FOUNDER roda o script gerado no terminal dele, com a senha (o motor pede pelo
# tty): gate stop, gate oracle:requisito e a pré-autorização de commit condicionada às sub-etapas de integração.
# A IA só gera e avisa; nunca roda o script, nunca pede a senha no chat (o hook de aprovação nega de qualquer jeito).
# Recusa se a campanha não existe (criar-frente) ou se o oráculo não está congelado (oracle freeze).
# Padrões: --por = `git config user.name` (ou "founder"); --requires "integracao.1 integracao.2".
# --dry-run imprime o script em vez de gravar.
set -eu
case "${1:-}" in -h|--help|'') sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
. "$(dirname "$0")/_comum.sh"
F="$1"; shift; frente_ok "$F"
POR="$(git -C "$SKILL" config user.name 2>/dev/null || true)"; POR="${POR:-founder}"
CRIT="critério de parada da frente $F"; ORAC="oráculo da frente $F confere com o requisito"
REQ="integracao.1 integracao.2"; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --por) POR="$2"; shift 2;;
    --criterio) CRIT="$2"; shift 2;;
    --oraculo) ORAC="$2"; shift 2;;
    --requires) REQ="$2"; shift 2;;
    --dry-run) DRY=1; shift;;
    *) die "opção desconhecida: $1";;
  esac
done
W="$CAMP/$F"
[ -d "$W/.auto-correcao" ] || die "campanha $F não foi aberta (falta $W/.auto-correcao — skill criar-frente)"
# quem testa não constrói: o founder só aprova depois do oráculo escrito por agente separado e congelado por hash
VER="$(python3 "$AC" --work "$W" oracle verify 2>&1)" || die "oráculo da frente $F não está congelado/intacto ($VER) — congele com \`python3 .claude/tools/ac/ac.py --work campanhas/$F oracle freeze --file …\` (todos os arquivos) antes de gerar a aprovação"
q() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }
CORPO="#!/bin/sh
# Aprovações humanas da frente $F (gerado por .claude/tools/script-aprovacao.sh em $(date '+%Y-%m-%d %H:%M %Z')).
# Rode VOCÊ, no seu terminal; o motor pede a senha pelo tty. Não cole a senha em lugar nenhum.
set -e
M=$(q "$AC")
W=$(q "$W")
python3 \"\$M\" --work \"\$W\" gate stop --by $(q "$POR") --decision approve --note $(q "$CRIT")
python3 \"\$M\" --work \"\$W\" gate oracle:requisito --by $(q "$POR") --decision approve --note $(q "$ORAC")
python3 \"\$M\" --work \"\$W\" preauth commit --by $(q "$POR") --requires $REQ --note $(q "commit se o portão estiver verde e o oráculo intacto")
echo \"OK — frente $F aprovada. Pode avisar o Claude.\"
"
if [ "$DRY" -eq 1 ]; then printf '%s' "$CORPO"; exit 0; fi
mkdir -p "$WS"
OUT="$WS/aprovar-$F.sh"
printf '%s' "$CORPO" > "$OUT"; chmod +x "$OUT"
echo "gerado: $OUT"
echo "o founder roda no terminal dele: sh $OUT"
