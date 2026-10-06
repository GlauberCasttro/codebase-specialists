#!/bin/bash
# instalar.sh [--dry-run | --check | --help] — instala a skill NESTA máquina a partir deste projeto (de qualquer cwd).
# A versão instalada É O PACOTE (dist/codebase-specialists), não o projeto inteiro. Sem opção, nesta ordem:
#   a) travas do git: liga pre-commit e commit-msg (→ .claude/tools/pre-commit.sh) que faltarem; trava alheia não mexe;
#   b) pacote: gera e VALIDA com package.sh (fonte `git archive HEAD`), montado fora do lugar; só substitui
#      dist/codebase-specialists se passar. Falha ⇒ exit != 0 e a instalação ($HOME) fica exatamente como estava;
#   c) link: $HOME/.claude/skills/codebase-specialists → <projeto>/dist/codebase-specialists. O que houver lá e não
#      for esse link vai para $HOME/.claude/skills-backup-<data>/codebase-specialists (nunca apaga, nunca sobrescreve);
#   d) conferência: cs.py --help do instalado, VERSION instalada == VERSION do projeto, nada interno instalado.
#   --dry-run  mostra o plano (travas, pacote, link, backup) e não escreve nada
#   --check    não escreve nada; exit 0 só se tudo está em dia (travas, link, cs.py, VERSION, pacote atualizado)
# Idempotente: a 2ª execução não cria backup nem refaz o link certo.
set -u
case "${1:-}" in -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac
MODO="instalar"
case "${1:-}" in
  "") ;; --dry-run) MODO="dry";; --check) MODO="check";;
  *) echo "opção desconhecida: $1 (use --dry-run, --check ou --help)" >&2; exit 2;;
esac
. "$(dirname "$0")/_comum.sh"
export PYTHONDONTWRITEBYTECODE=1
[ -n "$REPO" ] || die "o projeto ($SKILL) não está num repositório git"
SKILLS_DIR="$(dirname "$INST")"

link_certo() { [ -L "$INST" ] && [ "$(realp "$INST")" = "$(realp "$PKDIST")" ]; }
existe_inst() { [ -e "$INST" ] || [ -L "$INST" ]; }

# ---------------------------------------------------------------- --check
if [ "$MODO" = "check" ]; then
  RUIM=0
  while read -r st n a; do
    case "$st" in
      falta) echo "trava do git faltando: $n ($a)"; RUIM=1;;
      alheia) echo "trava do git alheia em $a: o guard de privacidade do harness não roda nela"; RUIM=1;;
    esac
  done < <(travas_status || echo "falta travas (diretório de hooks do git não encontrado)")
  MOT="$(instalado_estado)" || RUIM=1
  [ -n "$MOT" ] && printf '%s\n' "$MOT"
  if [ "$RUIM" -eq 0 ]; then echo "instalação em dia: $INST → dist/$NOME ($(tr -d '[:space:]' < "$PKDIST/VERSION"), origem $(cut -c1-12 "$PKDIST/.origem"))"; exit 0; fi
  echo "instalação NÃO está em dia — rode /install (bash .claude/tools/instalar.sh)"
  exit 1
fi

# ---------------------------------------------------------------- --dry-run
if [ "$MODO" = "dry" ]; then
  echo "plano (dry-run: nada é escrito)"
  while read -r st n a; do
    case "$st" in
      falta) echo "  a) instalaria a trava do git $n em $a";;
      alheia) echo "  a) trava alheia em $a: não mexeria";;
      ok) echo "  a) trava $n já instalada";;
    esac
  done < <(travas_status)
  echo "  b) geraria e validaria o pacote (package.sh, fonte HEAD $(git -C "$SKILL" rev-parse --short HEAD)) fora do lugar; só então substituiria $PKDIST (dist/$NOME)"
  if link_certo; then echo "  c) link já certo: $INST → dist/$NOME (não mexeria)"
  else
    existe_inst && echo "  c) moveria o que existe em $INST para backup em $HOME/.claude/skills-backup-<data>/$NOME (nada é apagado)"
    echo "  c) ligaria $INST → $PKDIST (dist/$NOME)"
  fi
  echo "  d) conferiria: cs.py --help do instalado, VERSION instalada == VERSION do projeto, nada interno"
  exit 0
fi

# ---------------------------------------------------------------- instalar
echo "== a) travas do git"
while read -r st n a; do [ "$st" = "alheia" ] && echo "  trava alheia em $a: não mexi"; done < <(travas_status)
NOVAS="$(instalar_travas)"
if [ -n "$NOVAS" ]; then echo "  instaladas: $(echo $NOVAS)"; else echo "  nada a instalar"; fi

VP="$(tr -d '[:space:]' < "$SKILL/VERSION" 2>/dev/null)"; VH="$(show_head VERSION 2>/dev/null | tr -d '[:space:]')"
[ "$VP" = "$VH" ] || die "VERSION do projeto '$VP' != VERSION do HEAD '$VH' (o pacote sai do HEAD): commite a VERSION antes de instalar"
SUJOS="$(cd "$SKILL" && git status --porcelain -- $PRODUTO 2>/dev/null | grep -c .)"
[ "${SUJOS:-0}" -gt 0 ] && echo "aviso: $SUJOS arquivo(s) de produto não commitados ficam FORA do pacote (fonte = HEAD)"

echo "== b) pacote (gera e valida; só troca dist/$NOME se passar)"
bash "$TOOLS/package.sh" || die "package falhou — instalação NÃO tocada ($INST como estava)"

echo "== c) link"
if link_certo; then echo "  já certo: $INST → dist/$NOME"
else
  mkdir -p "$SKILLS_DIR" || die "não consegui criar $SKILLS_DIR"
  if existe_inst; then
    base="$HOME/.claude/skills-backup-$(date +%Y%m%d-%H%M%S)"; bk="$base"; i=2
    while [ -e "$bk/$NOME" ] || [ -L "$bk/$NOME" ]; do bk="$base-$i"; i=$((i + 1)); done
    mkdir -p "$bk" && mv "$INST" "$bk/$NOME" || die "não consegui mover $INST para o backup $bk"
    echo "  backup do que havia em $INST: $bk/$NOME"
  fi
  ln -s "$PKDIST" "$INST" || die "não consegui criar o link $INST"
  echo "  ligado: $INST → $PKDIST"
fi

echo "== d) conferência"
MOT="$(instalado_estado)"; RC=$?
if [ "$RC" -ne 0 ]; then printf '%s\n' "$MOT"; die "conferência do instalado REPROVADA"; fi
echo "  ok: cs.py --help, VERSION $(tr -d '[:space:]' < "$INST/VERSION"), nada interno, origem $(cut -c1-12 "$PKDIST/.origem")"
echo "instalado: $INST → dist/$NOME"
