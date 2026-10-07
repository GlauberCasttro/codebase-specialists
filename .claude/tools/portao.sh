#!/bin/bash
# portao.sh <feature> [opções] -- <arquivo> [<arquivo>...]
# Portão em CÓPIA LIMPA: `git archive HEAD` da skill + SÓ os arquivos da feature (vindos de --src; padrão: a cópia de
# trabalho <local>/work/<feature>/codebase-specialists); roda as suítes da skill
# (scripts/*/tests e evals/tests) e a suíte do próprio harness (`harness-dev` = .claude/tools/tests) nos 2 Pythons,
# os oráculos pedidos, e confere que nenhum `def` sumiu vs HEAD nos arquivos da feature. Arquivo listado que não existe em --src = arquivo REMOVIDO pela feature.
# Saída incremental em <local>/portao-<feature>/portao.out; termina em "RESULTADO: VERDE|VERMELHO" e "FIM".
# Também grava arquivos.txt (a lista testada) e a cópia testada (lida por conferir-commit.sh).
# Opções:
#   --src DIR            de onde vêm os arquivos da feature (ex.: a skill viva, depois de portar.sh com merge)
#   --oraculo DIR:MOD    oráculo extra (repetível): roda `python3 -m unittest MOD` dentro de DIR
#                        (ex.: campanhas/iter17/oraculo:test_x — relativo à raiz do projeto ou absoluto)
#   --lista ARQ          lê os arquivos da feature de ARQ (um por linha) — evita o word-split que o zsh não faz
#   --suites a,b         só estas suítes (nomes de scripts/<x>; "evals" = evals/tests; "harness-dev" =
#                        .claude/tools/tests). Padrão: todas (a régua: python3 .claude/tools/e2e.py regua)
#   --pythons "p1 p2"    padrão: "python3 /usr/bin/python3"
#   --dry-run            mostra o plano (arquivos, suítes, oráculos) e não roda nada
# Demora (dezenas de minutos): rode em background e acompanhe o portao.out.
# Arquivos SEMPRE explícitos e relativos à pasta da skill (zsh não faz word-split de $VAR: use --lista).
set -u
case "${1:-}" in -h|--help|'') sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
. "$(dirname "$0")/_comum.sh"
F="$1"; shift; feature_ok "$F"
SRC="$WS/work/$F/$NOME"; ORACULOS=(); SUITES=""; PYS="python3 /usr/bin/python3"; DRY=0; ARQS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --src) SRC="$2"; shift 2;;
    --oraculo) ORACULOS+=("$2"); shift 2;;
    --lista) while IFS= read -r l; do [ -n "$l" ] && ARQS+=("$l"); done < "$2"; shift 2;;
    --suites) SUITES="$2"; shift 2;;
    --pythons) PYS="$2"; shift 2;;
    --dry-run) DRY=1; shift;;
    --) shift; while [ $# -gt 0 ]; do ARQS+=("$1"); shift; done;;
    *) die "opção desconhecida: $1 (arquivos vão depois de --)";;
  esac
done
[ ${#ARQS[@]} -gt 0 ] || die "nenhum arquivo da feature (passe depois de -- ou com --lista)"
[ -d "$SRC" ] || die "--src inexistente: $SRC"
[ -n "$REPO" ] || die "a skill não está num repositório git: $SKILL"
for f in "${ARQS[@]}"; do case "$f" in /*|../*|*/../*) die "arquivo deve ser relativo à skill: $f";; esac; done

G="$WS/portao-$F"; D="$G/$NOME"; OUT="$G/portao.out"
suite_ok() { [ -z "$SUITES" ] && return 0; case ",$SUITES," in *",$1,"*) return 0;; esac; return 1; }

if [ "$DRY" -eq 1 ]; then
  echo "portão $F (dry-run) · src: $SRC · saída: $OUT"
  for f in "${ARQS[@]}"; do if [ -e "$SRC/$f" ]; then echo "  arquivo: $f"; else echo "  REMOVE: $f"; fi; done
  echo "  pythons: $PYS · suítes: ${SUITES:-todas (scripts/*/tests, evals/tests e harness-dev)} · oráculos: ${ORACULOS[*]:-nenhum}"
  suite_ok harness-dev && echo "  harness-dev: .claude/tools/tests nos 2 Pythons"
  exit 0
fi

rm -rf "$G"; mkdir -p "$G"
archive_head "$D" || die "git archive falhou"
: > "$G/arquivos.txt"
for f in "${ARQS[@]}"; do
  mkdir -p "$(dirname "$D/$f")"
  if [ -e "$SRC/$f" ]; then cp -Rp "$SRC/$f" "$D/$f"; else rm -rf "$D/$f"; fi
  echo "$f" >> "$G/arquivos.txt"
done
: > "$OUT"
echo "portão $F · $(date '+%Y-%m-%d %H:%M %Z') · HEAD $(git -C "$REPO" rev-parse --short HEAD) · src $SRC · ${#ARQS[@]} arquivo(s)" >> "$OUT"

RUIM=0
roda() {  # <rótulo> <dir> <python> <args...>
  local rot="$1" dir="$2" py="$3"; shift 3
  local r; r="$(cd "$dir" && PYTHONDONTWRITEBYTECODE=1 CS_SKILL_DIR="$D" CS_SKILL="$D" "$py" -m unittest "$@" 2>&1 \
               | grep -E '^(Ran|OK|FAILED)' | tr '\n' ' ')"
  [ -n "$r" ] || r="SEM RESULTADO (suíte quebrou antes de rodar)"
  case "$r" in *OK*) ;; *) RUIM=1;; esac
  case "$r" in *FAILED*) RUIM=1;; esac
  echo "$("$py" --version 2>&1) $rot: $r" >> "$OUT"
}
for py in $PYS; do
  for d in "$D"/scripts/*/tests "$D"/evals/tests; do
    [ -d "$d" ] || continue
    p="$(dirname "$d")"; n="$(basename "$p")"
    suite_ok "$n" || continue
    roda "$n" "$p" "$py" discover -s tests
  done
  if suite_ok harness-dev && [ -d "$D/.claude/tools/tests" ]; then
    roda "harness-dev" "$D/.claude/tools" "$py" discover -s tests
  fi
  for o in "${ORACULOS[@]+"${ORACULOS[@]}"}"; do
    od="${o%%:*}"; case "$od" in /*) ;; *) od="$SKILL/$od";; esac
    roda "ORACULO ${o##*:}" "$od" "$py" "${o##*:}"
  done
done

# nenhum def removido vs HEAD nos arquivos .py da feature (testes inclusive: enfraquecer teste também é remoção)
for f in "${ARQS[@]}"; do
  case "$f" in *.py) ;; *) continue;; esac
  antes="$(show_head "$f" 2>/dev/null | grep -oE '^ *def [A-Za-z_0-9]+' | sed 's/^ *//' | sort -u)"
  [ -n "$antes" ] || continue
  depois="$( [ -f "$D/$f" ] && grep -oE '^ *def [A-Za-z_0-9]+' "$D/$f" | sed 's/^ *//' | sort -u)"
  r="$(comm -23 <(printf '%s\n' "$antes") <(printf '%s\n' "$depois") | tr '\n' ',' | sed 's/,$//; s/,/, /g')"
  if [ -n "$r" ]; then echo "REMOVIDA $f: $r" >> "$OUT"; RUIM=1; fi
done
grep -E 'skipped=' "$OUT" | sed 's/^/SKIP /' >> "$OUT"
if [ "$RUIM" -eq 0 ]; then echo "RESULTADO: VERDE" >> "$OUT"; else echo "RESULTADO: VERMELHO" >> "$OUT"; fi
echo "FIM" >> "$OUT"
tail -3 "$OUT"
[ "$RUIM" -eq 0 ]
