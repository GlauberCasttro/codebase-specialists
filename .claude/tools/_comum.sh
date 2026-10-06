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

# ---- instalação nesta máquina (instalar.sh, carimbo.sh --brief) ----
# INST = onde o Claude Code procura a skill; PKDIST = o pacote gerado (a versão instalada É o pacote, não o projeto).
# PRODUTO = o que entra no pacote: commit que muda algo daqui depois da `.origem` do pacote o desatualiza
# (commit só de .claude/state/ etc. não).
INST="$HOME/.claude/skills/$NOME"
PKDIST="$SKILL/dist/$NOME"
PRODUTO="SKILL.md MODO-DE-USO.md VERSION LICENSE scripts assets references docs .claude/package"
LINHA_TRAVA='exec sh "$(git rev-parse --show-toplevel)/.claude/tools/pre-commit.sh" "$@"'
realp() { python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$1"; }
# travas_dir: diretório de hooks do git do repo (o de `git rev-parse --git-path hooks`), absoluto
travas_dir() {
  [ -n "$REPO" ] && [ -d "$REPO" ] || return 1
  _h="$(git -C "$REPO" rev-parse --git-path hooks 2>/dev/null)" || return 1
  case "$_h" in /*) echo "$_h";; *) echo "$REPO/$_h";; esac
}
# travas_status: uma linha por trava "<ok|falta|alheia> <nome> <caminho>" (alheia = hook que não chama pre-commit.sh)
travas_status() {
  _H="$(travas_dir)" || return 1
  for _n in pre-commit commit-msg; do
    _a="$_H/$_n"
    if [ ! -e "$_a" ] && [ ! -L "$_a" ]; then echo "falta $_n $_a"
    elif ! grep -qF "$LINHA_TRAVA" "$_a" 2>/dev/null; then echo "alheia $_n $_a"
    elif [ -x "$_a" ]; then echo "ok $_n $_a"
    else echo "falta $_n $_a"; fi
  done
}
# instalar_travas: grava só as travas que faltam (nunca a alheia); imprime os nomes instalados (vazio = nada a fazer)
instalar_travas() {
  travas_status | while read -r _st _n _a; do
    [ "$_st" = "falta" ] || continue
    mkdir -p "$(dirname "$_a")" && printf '#!/bin/sh\n%s\n' "$LINHA_TRAVA" > "$_a" && chmod +x "$_a" && echo "$_n"
  done
}
# instalado_estado [--rapido]: um motivo por linha do que NÃO está em dia na skill instalada; exit 0 = em dia.
# --rapido (SessionStart) pula `cs.py --help` e a varredura de pastas internas.
instalado_estado() {
  _r=0
  if [ ! -e "$INST" ] && [ ! -L "$INST" ]; then echo "skill não instalada nesta máquina ($INST ausente)"; return 1; fi
  if [ ! -L "$INST" ] || [ "$(realp "$INST")" != "$(realp "$PKDIST")" ]; then
    echo "o instalado ($INST) não é o link para dist/$NOME deste projeto (hoje: $( [ -L "$INST" ] && readlink "$INST" || echo 'pasta/arquivo'))"
    return 1
  fi
  [ -f "$PKDIST/SKILL.md" ] || { echo "pacote ausente em dist/$NOME"; return 1; }
  _o="$(grep -oE '[0-9a-f]{40}' "$PKDIST/.origem" 2>/dev/null | head -1)"
  if [ -z "$_o" ]; then echo "pacote desatualizado: sem .origem (origem desconhecida)"; _r=1
  elif grep -q worktree "$PKDIST/.origem" 2>/dev/null; then echo "pacote desatualizado: veio da árvore de trabalho, não de um commit"; _r=1
  elif ! git -C "$SKILL" cat-file -e "$_o^{commit}" 2>/dev/null; then echo "pacote desatualizado: origem ${_o:0:12} desconhecida neste repositório"; _r=1
  else
    # shellcheck disable=SC2086
    _m="$(cd "$SKILL" && git diff --name-only "$_o" HEAD -- $PRODUTO 2>/dev/null | grep -c .)"
    [ "${_m:-0}" -gt 0 ] && { echo "pacote desatualizado: $_m arquivo(s) de produto mudaram desde ${_o:0:12}"; _r=1; }
  fi
  _vi="$(tr -d '[:space:]' < "$PKDIST/VERSION" 2>/dev/null)"; _vp="$(tr -d '[:space:]' < "$SKILL/VERSION" 2>/dev/null)"
  [ "$_vi" = "$_vp" ] || { echo "VERSION instalada '${_vi:-?}' != VERSION do projeto '${_vp:-?}'"; _r=1; }
  [ "${1:-}" = "--rapido" ] && return $_r
  PYTHONDONTWRITEBYTECODE=1 python3 "$INST/scripts/cs.py" --help >/dev/null 2>&1 \
    || { echo "o instalado não roda: python3 scripts/cs.py --help falhou"; _r=1; }
  _int="$(cd "$PKDIST" && find . \( -name .claude -o -name campanhas -o -name local -o -name tests -o -name evals \) -print | head -5)"
  [ -z "$_int" ] || { echo "o instalado contém pasta interna: $(echo $_int)"; _r=1; }
  return $_r
}
