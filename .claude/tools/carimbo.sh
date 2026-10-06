#!/bin/bash
# carimbo.sh — âncora da sessão de desenvolvimento da codebase-specialists. Só LÊ estado real (git, VERSION,
# status das campanhas pelo motor embutido .claude/tools/ac/ac.py); nunca inventa data, contagem ou commit.
# uso: carimbo.sh            imprime a âncora completa
#      carimbo.sh --brief    versão curta (hook SessionStart: vai para o contexto)
#      carimbo.sh --write    imprime e regrava o bloco de carimbo no topo de .claude/state/RESUME.md
#      carimbo.sh --json     a âncora em JSON
#      carimbo.sh --help
set -u
case "${1:-}" in -h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
MODO="${1:-full}"
. "$(dirname "$0")/_comum.sh"
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
  echo "[harness de desenvolvimento: $NOME] regras em .claude/CLAUDE.md; retomar com a skill load-session."
  bloco
  echo "estado: .claude/state/RESUME.md, WORKFLOW.md, BACKLOG.md, DECISIONS.md"
  exit 0
fi

bloco
if [ "$MODO" = "--write" ]; then
  R="$SKILL/.claude/state/RESUME.md"
  [ -f "$R" ] || { echo "carimbo: $R ausente" >&2; exit 1; }
  CS_BLOCO="$(SEM_LISTA=1 bloco; echo "  (lista: git status --porcelain)")" python3 - "$R" <<'PY'
import os, re, sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
ini, fim = "<!-- carimbo:inicio (gerado por tools/carimbo.sh --write; não edite à mão) -->", "<!-- carimbo:fim -->"
novo = ini + "\n```\n" + os.environ["CS_BLOCO"].rstrip() + "\n```\n" + fim
if ini in s and fim in s:
    s = s[:s.index(ini)] + novo + s[s.index(fim) + len(fim):]
else:
    s = novo + "\n\n" + s
open(p, "w", encoding="utf-8").write(s)
print("RESUME.md: bloco de carimbo regravado")
PY
fi
