#!/bin/bash
# package.sh [--dry-run] [--worktree] [--sem-validar] [--manter]
# Gera o PACOTE da skill (só o que roda) em dist/codebase-specialists/ + dist/codebase-specialists-<VERSION>.zip,
# por LISTA DE INCLUSÃO (nada entra por omissão):
#   SKILL.md, MODO-DE-USO.md, VERSION, LICENSE, README.md (de .claude/package/README.md),
#   scripts/** sem tests/ e sem __pycache__/*.pyc, assets/**, references/**, docs/ de usuário (docs/*.md,
#   docs/fases/, docs/exemplos/) EXCETO os internos: PONTOS-DO-FOUNDER, ROADMAP-*, PENDENTE, AUTONOMIA-DESENHO,
#   defeitos-abertos, 12-rodada-*.
# Depois: limpezas de privacidade + referências internas (publicar_regras.py aplicar --pacote), guard-privacidade
# no pacote (tem de voltar vazio), e VALIDAÇÃO (package_validar.py): instala o pacote num HOME temporário e roda
# init + harness install + emit + emit validate + harness selftest num repositório git temporário; confere que nada
# de .claude/, campanhas/, local/, tests/, evals/ vazou. Só então gera o .zip.
#   --dry-run     lista o que entraria (e o que fica de fora) e não escreve nada
#   --worktree    empacota a árvore de trabalho (padrão: `git archive HEAD` — só o commitado)
#   --sem-validar pula a validação (o .zip NÃO é gerado nesse caso)
#   --manter      mantém o HOME/alvo temporários da validação (para inspeção)
# Publicar o pacote (release, outro repositório) fica FORA: decisão do founder.
set -u
case "${1:-}" in -h|--help) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
. "$(dirname "$0")/_comum.sh"
DRY=0; WT=0; VALIDA=1; MANTER=""
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1;; --worktree) WT=1;; --sem-validar) VALIDA=0;; --manter) MANTER="--manter";;
    *) die "opção desconhecida: $a";;
  esac
done
INTERNOS='^docs/(PONTOS-DO-FOUNDER\.md|ROADMAP-[^/]*\.md|PENDENTE\.md|AUTONOMIA-DESENHO\.md|defeitos-abertos\.json5|12-rodada-[^/]*)$'

# fonte: HEAD (padrão) ou árvore de trabalho; lista de arquivos candidatos, relativa à raiz da skill
SRC="$SKILL"; TMPSRC=""
if [ "$WT" -eq 0 ]; then
  [ -n "$REPO" ] || die "a skill não está num repositório git (use --worktree)"
  TMPSRC="$(mktemp -d "${TMPDIR:-/tmp}/cs-package-src.XXXXXX")"; trap 'rm -rf "$TMPSRC"' EXIT
  archive_head "$TMPSRC" || die "git archive falhou"; SRC="$TMPSRC"
fi
[ -f "$SRC/VERSION" ] || die "VERSION ausente em $SRC"
VER="$(tr -d '[:space:]' < "$SRC/VERSION")"

incluir() {  # lê caminhos relativos na stdin, imprime os que entram no pacote
  while IFS= read -r f; do
    case "$f" in
      SKILL.md|MODO-DE-USO.md|VERSION|LICENSE) echo "$f";;
      scripts/*)
        case "/$f/" in */tests/*|*/__pycache__/*) continue;; esac
        case "$f" in *.pyc) continue;; esac; echo "$f";;
      assets/*|references/*) case "$f" in */__pycache__/*|*.pyc|*.DS_Store) ;; *) echo "$f";; esac;;
      docs/*)
        printf '%s\n' "$f" | grep -qE "$INTERNOS" && continue
        case "$f" in docs/*.md|docs/fases/*|docs/exemplos/*) echo "$f";; esac;;
    esac
  done
}
TODOS="$(cd "$SRC" && find . \( -name .git -o -name local -o -name dist -o -name __pycache__ \) -prune -o -type f \
  ! -name .DS_Store ! -name '*.pyc' -print | sed 's#^\./##' | LC_ALL=C sort)"
LISTA="$(printf '%s\n' "$TODOS" | incluir)"
N="$(printf '%s\n' "$LISTA" | grep -c .)"
[ -f "$SKILL/.claude/package/README.md" ] || die "README do pacote ausente: .claude/package/README.md"

if [ "$DRY" -eq 1 ]; then
  echo "pacote codebase-specialists $VER (fonte: $([ $WT -eq 1 ] && echo 'árvore de trabalho' || echo "HEAD $(git -C "$REPO" rev-parse --short HEAD)"))"
  echo "ENTRA ($N arquivos + README.md do pacote):"
  printf '%s\n' "$LISTA" | awk -F/ '{ k = (NF > 2 ? $1"/"$2"/" : (NF == 2 ? $1"/" : $0)); c[k]++ } END { for (k in c) printf "  %4d  %s\n", c[k], k }' | LC_ALL=C sort -k2
  echo "FICA DE FORA (por topo):"
  printf '%s\n' "$TODOS" | grep -vxF -f <(printf '%s\n' "$LISTA") | awk -F/ '{ k = (NF > 1 ? $1"/" : $0); if ($0 ~ /\/tests\//) k = "scripts/*/tests/"; c[k]++ } END { for (k in c) printf "  %4d  %s\n", c[k], k }' | LC_ALL=C sort -k2
  echo "saída seria: dist/codebase-specialists/ e dist/codebase-specialists-$VER.zip (nada escrito: dry-run)"
  exit 0
fi

DIST="$SKILL/dist"; PK="$DIST/codebase-specialists"; ZIP="$DIST/codebase-specialists-$VER.zip"
rm -rf "$PK" "$ZIP"; mkdir -p "$PK"
printf '%s\n' "$LISTA" | while IFS= read -r f; do
  mkdir -p "$PK/$(dirname "$f")"; cp -p "$SRC/$f" "$PK/$f"
done
sed "s/{{VERSION}}/$VER/g" "$SKILL/.claude/package/README.md" > "$PK/README.md"
echo "== pacote $VER montado em dist/codebase-specialists ($((N + 1)) arquivos)"

echo "== limpeza (privacidade + referências internas)"
python3 "$TOOLS/publicar_regras.py" aplicar "$PK" --pacote || die "limpeza reprovou (achados acima) — pacote inválido"
echo "== guard-privacidade no pacote"
python3 "$TOOLS/guard_privacidade.py" "$PK" || die "guard-privacidade achou termo privado no pacote"
grep -rIl '{{VERSION}}' "$PK" >/dev/null 2>&1 && die "placeholder {{VERSION}} sobrou no pacote"

if [ "$VALIDA" -eq 0 ]; then echo "validação PULADA (--sem-validar): .zip não gerado"; exit 0; fi
echo "== validação (skill instalada num HOME temporário)"
python3 "$TOOLS/package_validar.py" "$PK" $MANTER || die "validação do pacote REPROVADA — .zip não gerado"

( cd "$DIST" && python3 - "codebase-specialists" "$(basename "$ZIP")" <<'PY'
import os, sys, zipfile
raiz, saida = sys.argv[1], sys.argv[2]
arqs = sorted(os.path.join(d, f) for d, _, fs in os.walk(raiz) for f in fs)
with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
    for p in arqs:
        zi = zipfile.ZipInfo(p, date_time=(2026, 1, 1, 0, 0, 0))
        zi.external_attr = (os.stat(p).st_mode & 0o777) << 16
        zi.compress_type = zipfile.ZIP_DEFLATED
        with open(p, "rb") as fh:
            z.writestr(zi, fh.read())
print("zip: %d arquivos" % len(arqs))
PY
) || die "falha ao gerar o zip"
echo "== pronto: dist/codebase-specialists/ ($(du -sh "$PK" | cut -f1)) · $(basename "$ZIP") ($(du -h "$ZIP" | cut -f1)) · sha256 $(shasum -a 256 "$ZIP" | cut -c1-16)…"
echo "publicar o pacote fica fora deste script (decisão do founder)."
