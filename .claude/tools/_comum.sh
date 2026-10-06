# _comum.sh — variáveis comuns dos tools (fonte: `. "$(dirname "$0")/_comum.sh"`). Não executa nada.
# SKILL = raiz do PROJETO (a skill: SKILL.md na raiz); NOME = codebase-specialists (nome da pasta das cópias);
# REPO = raiz do repo git; PFX = prefixo da skill dentro do repo ("" quando o projeto é o próprio repo);
# CAMP = campanhas/ (oráculos versionados + .auto-correcao/ gitignored); WS = área de trabalho desta máquina
# (local/, gitignored), onde ficam work/<frente>/ e portao-<frente>/ (NUNCA em /tmp: some no reboot);
# AC = motor de campanhas EMBUTIDO (.claude/tools/ac/ac.py).
TOOLS="$(cd "$(dirname "$0")" && pwd)"
SKILL="${CS_DEV_SKILL_DIR:-$(cd "$TOOLS/../.." && pwd)}"
NOME="${CS_DEV_NOME:-codebase-specialists}"
CAMP="${CS_DEV_CAMP:-$SKILL/campanhas}"
WS="${CS_DEV_WS:-$SKILL/local}"
AC="$TOOLS/ac/ac.py"
REPO="$(git -C "$SKILL" rev-parse --show-toplevel 2>/dev/null)"
PFX="$(git -C "$SKILL" rev-parse --show-prefix 2>/dev/null)"
die() { echo "ERRO: $*" >&2; exit 1; }
frente_ok() { case "$1" in ''|*/*|.*|-*) die "nome de frente inválido: '$1' (use ex.: iter17)";; esac; }
# archive_head <destino>: `git archive` do HEAD da skill (só o commitado) extraído em <destino> (sem o prefixo)
archive_head() { mkdir -p "$1" && git -C "$REPO" archive "HEAD:$PFX" | tar -x -C "$1"; }
# show_head <arq>: conteúdo do arquivo (relativo à skill) no HEAD
show_head() { git -C "$REPO" show "HEAD:$PFX$1"; }
