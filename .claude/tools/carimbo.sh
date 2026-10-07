#!/bin/bash
# carimbo.sh — âncora da sessão de desenvolvimento da codebase-specialists. LÊ estado real (git, VERSION,
# status das campanhas pelo motor embutido .claude/tools/ac/ac.py); nunca inventa data, contagem ou commit.
# uso: carimbo.sh            imprime a âncora completa
#      carimbo.sh --brief    versão curta (hook SessionStart: vai para o contexto); instala as travas do git que
#                            faltarem e avisa se a skill instalada não é o pacote em dia (sugere /install)
#      carimbo.sh --write    regrava o carimbo comparável (resume-stamp) do RESUME.md — fórmula em sessao.py
#      carimbo.sh --json     a âncora em JSON
#      carimbo.sh --help
# Âncora INFORMATIVA (SessionStart). O carimbo COMPARÁVEL e o frescor têm um dono só: .claude/tools/sessao.py
# (skill carregar-sessao: `python3 .claude/tools/sessao.py briefing`).
set -u
case "${1:-}" in -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
MODO="${1:-full}"
[ "$MODO" = "--write" ] && exec python3 "$(dirname "$0")/sessao.py" carimbo --write
. "$(dirname "$0")/_comum.sh"
TRAVAS_NOVAS=""; INST_MOT=""
if [ "$MODO" = "--brief" ] && [ -n "$REPO" ]; then
  TRAVAS_NOVAS="$(instalar_travas 2>/dev/null)"   # só as que faltam; trava alheia nunca é tocada
  INST_MOT="$(instalado_estado --rapido 2>/dev/null)"
fi
[ -n "$REPO" ] || REPO="?"

DATA="$(date '+%Y-%m-%d %H:%M %Z')"
BRANCH="$(git -C "$SKILL" branch --show-current 2>/dev/null || echo '?')"
HEAD="$(git -C "$SKILL" log -1 --format='%h %s' 2>/dev/null || echo '?')"
ULT="$(git -C "$SKILL" log -1 --format='%h %ad %s' --date=short -- . 2>/dev/null || echo '?')"
VER="$(cat "$SKILL/VERSION" 2>/dev/null | tr -d '[:space:]' || echo '?')"
VERHEAD="$(show_head VERSION 2>/dev/null | tr -d '[:space:]')"
SUJOS="$(git -C "$SKILL" status --porcelain -- . 2>/dev/null)"
NSUJOS="$(printf '%s' "$SUJOS" | grep -c . )"

ATIVAS=""; ANTIGAS=""
for c in "$CAMP"/*/; do
  c="${c%/}"
  [ -d "$c/.auto-correcao" ] || continue
  st="$(python3 "$AC" --work "$c" status 2>/dev/null)" || continue
  etapa="$(printf '%s\n' "$st" | sed -n 's/^rodada: \([0-9]*\) · etapa: \(.*\)$/\2/p' | head -1)"
  [ "$etapa" = "concluida" ] && continue
  feitas="$(printf '%s\n' "$st" | grep -c '^ ✓')"
  total="$(printf '%s\n' "$st" | grep -cE '^ (✓| ) [a-z]')"
  if [ "$total" -gt 0 ] && [ "$feitas" -eq "$total" ]; then   # ac.py antigo: tudo ✓ mas etapa não virou concluida
    ANTIGAS="${ANTIGAS}$(basename "$c") "; continue
  fi
  ATIVAS="${ATIVAS}$(basename "$c"): etapa ${etapa:-?} (${feitas}/${total} etapas)"$'\n'
done
NATIVAS="$(printf '%s' "$ATIVAS" | grep -c .)"

if [ "$MODO" = "--json" ]; then
  CS_D="$DATA" CS_B="$BRANCH" CS_H="$HEAD" CS_U="$ULT" CS_V="$VER" CS_VH="$VERHEAD" CS_S="$SUJOS" CS_A="$ATIVAS" \
  python3 -c 'import json,os;e=os.environ;print(json.dumps({"data":e["CS_D"],"branch":e["CS_B"],"head":e["CS_H"],
"ultimo_commit_da_skill":e["CS_U"],"version":e["CS_V"],"version_head":e["CS_VH"],
"campanhas_ativas":[x for x in e["CS_A"].splitlines() if x],"sujos":[x for x in e["CS_S"].splitlines() if x]},
ensure_ascii=False,indent=1))'
  exit 0
fi

bloco() {
  echo "carimbo: $DATA · branch $BRANCH · HEAD $HEAD"
  echo "skill: $NOME · VERSION viva $VER (HEAD: ${VERHEAD:-?}) · último commit da skill: $ULT"
  if [ "$NATIVAS" -gt 0 ]; then
    echo "campanhas ativas ($NATIVAS):"; printf '%s' "$ATIVAS" | sed 's/^/  - /'
  else
    echo "campanhas ativas: nenhuma"
  fi
  [ -n "$ANTIGAS" ] && [ "$MODO" != "--brief" ] && echo "campanhas com todas as etapas ✓ mas etapa != concluida (ac.py antigo): $ANTIGAS"
  echo "arquivos sujos da skill: $NSUJOS"
  if [ "$NSUJOS" -gt 0 ] && [ "${SEM_LISTA:-0}" -eq 0 ]; then   # --write não lista caminhos (só a contagem)
    lim=15; [ "$MODO" = "--brief" ] && lim=8
    printf '%s\n' "$SUJOS" | head -$lim | sed 's/^/  /'
    [ "$NSUJOS" -gt "$lim" ] && echo "  ... (+$((NSUJOS - lim)))"
  fi
}

if [ "$MODO" = "--brief" ]; then
  echo "[harness de desenvolvimento: $NOME] regras em .claude/CLAUDE.md; retomar com a skill carregar-sessao."
  bloco
  FR="$(python3 "$TOOLS/sessao.py" frescor 2>/dev/null | head -1)"
  [ -n "$FR" ] && echo "$FR (carregar-sessao: python3 .claude/tools/sessao.py briefing)"
  echo "estado: .claude/state/RESUME.md, WORKFLOW.md, BACKLOG.md, DECISIONS.md"
  [ -n "$TRAVAS_NOVAS" ] && echo "travas do git faltavam ($(echo $TRAVAS_NOVAS)) — instaladas agora"
  if [ -n "$INST_MOT" ]; then
    printf '%s\n' "$INST_MOT" | sed 's/^/skill instalada: /'
    echo "sugestão: rode /install (atualiza a skill instalada a partir deste projeto)"
  fi
  exit 0
fi

bloco
exit 0
