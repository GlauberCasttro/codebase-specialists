#!/usr/bin/env bash
# build.sh <nome> <destino>
#
# Materializa a fixture <nome> em <destino> como repositório git com HISTÓRICO realista.
# Compatível com bash 3.2 (macOS). Sem heredoc dentro de $(...).
#
# Layout de cada fixture (só repo/ é copiado para o alvo):
#   <nome>/repo/            estado FINAL do repositório
#   <nome>/history.plan     roteiro de commits (ops abaixo)
#   <nome>/history/<tag>/   versões alternativas de arquivos, usadas por "variant"
#   <nome>/GROUND_TRUTH.json   verdade conhecida (NUNCA copiada para o alvo)
#
# Ops do history.plan (uma por linha; '#' comenta):
#   put <path>...                     copia do estado final (diretório ou arquivo; "." = tudo)
#   variant <path> <tag>              copia history/<tag>/<path> sobre <path>
#   sed <path> <expressão-sed>        aplica a expressão ao arquivo ATUAL (precisa mudar algo)
#   del <path>                        remove do working tree
#   commit <iso-date> <autor> <msg>   git add -A + commit (msg aceita \n)
#   revert <iso-date> <autor>         git revert HEAD (mensagem padrão do git)
#   tag <nome>                        git tag leve
# Ao final o working tree TEM de ser idêntico a repo/ (o script aborta se não for).
set -eu

die() { echo "build.sh: $*" >&2; exit 1; }

HERE=$(cd "$(dirname "$0")" && pwd)
name=${1:-}
dest=${2:-}
[ -n "$name" ] && [ -n "$dest" ] || die "uso: build.sh <py-billing|ts-shop|go-polyglot> <destino>"
fx="$HERE/$name"
src="$fx/repo"
plan="$fx/history.plan"
hist="$fx/history"
[ -d "$src" ] || die "fixture desconhecida: $name (sem $src)"
[ -f "$plan" ] || die "fixture $name sem history.plan"
command -v git >/dev/null 2>&1 || die "git não encontrado"

if [ -e "$dest" ]; then
  if [ -n "$(ls -A "$dest" 2>/dev/null)" ]; then die "destino não está vazio: $dest"; fi
else
  mkdir -p "$dest"
fi
dest=$(cd "$dest" && pwd)

author_of() {
  case "$1" in
    ana)   echo "Ana Ribeiro|ana.ribeiro@acme.example" ;;
    bruno) echo "Bruno Tavares|bruno.tavares@acme.example" ;;
    carla) echo "Carla Mendes|carla.mendes@acme.example" ;;
    diego) echo "Diego Ramos|diego.ramos@acme.example" ;;
    bot)   echo "release-bot|release-bot@acme.example" ;;
    *) die "autor desconhecido no plano: $1" ;;
  esac
}

set_identity() {
  local who ident
  who=$1; ident=$(author_of "$who")
  GIT_AUTHOR_NAME=${ident%%|*}; GIT_AUTHOR_EMAIL=${ident#*|}
  GIT_COMMITTER_NAME=$GIT_AUTHOR_NAME; GIT_COMMITTER_EMAIL=$GIT_AUTHOR_EMAIL
  GIT_AUTHOR_DATE=$2; GIT_COMMITTER_DATE=$2
  export GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL GIT_AUTHOR_DATE GIT_COMMITTER_DATE
}

copy_path() {
  local p=$1
  if [ "$p" = "." ]; then
    cp -R "$src/." "$dest/"
  elif [ -d "$src/$p" ]; then
    mkdir -p "$dest/$p"
    cp -R "$src/$p/." "$dest/$p/"
  elif [ -f "$src/$p" ]; then
    mkdir -p "$dest/$(dirname "$p")"
    cp "$src/$p" "$dest/$p"
  else
    die "put: $p não existe em $src"
  fi
}

cd "$dest"
git init -q .
git symbolic-ref HEAD refs/heads/main
git config user.name "fixture-builder"
git config user.email "fixture-builder@acme.example"
git config commit.gpgsign false
git config core.autocrlf false

set -f   # sem globbing ao expandir linhas do plano
lineno=0
while IFS= read -r line <&3 || [ -n "$line" ]; do
  lineno=$((lineno + 1))
  case "$line" in ''|'#'*) continue ;; esac
  op=${line%% *}
  rest=""
  [ "$op" != "$line" ] && rest=${line#* }
  case "$op" in
    put)
      for p in $rest; do copy_path "$p"; done ;;
    variant)
      p=${rest%% *}; tag=${rest#* }
      [ -f "$hist/$tag/$p" ] || die "linha $lineno: variante ausente $hist/$tag/$p"
      mkdir -p "$dest/$(dirname "$p")"
      cp "$hist/$tag/$p" "$dest/$p" ;;
    sed)
      p=${rest%% *}; expr=${rest#* }
      [ -f "$dest/$p" ] || die "linha $lineno: sed em arquivo inexistente $p"
      sed -e "$expr" "$dest/$p" > "$dest/$p.tmp.$$"
      if cmp -s "$dest/$p" "$dest/$p.tmp.$$"; then
        rm -f "$dest/$p.tmp.$$"; die "linha $lineno: sed não alterou $p ($expr)"
      fi
      mv "$dest/$p.tmp.$$" "$dest/$p" ;;
    del)
      for p in $rest; do rm -rf "${dest:?}/$p"; done ;;
    commit)
      date=${rest%% *}; r2=${rest#* }; who=${r2%% *}; msg=${r2#* }
      set_identity "$who" "$date"
      git add -A
      git commit -q --allow-empty -m "$(printf '%b' "$msg")" ;;
    revert)
      date=${rest%% *}; who=${rest#* }
      set_identity "$who" "$date"
      git revert --no-edit HEAD >/dev/null ;;
    tag)
      git tag "$rest" ;;
    *)
      die "linha $lineno: op desconhecida '$op'" ;;
  esac
done 3< "$plan"
set +f

if ! diff -r -x .git -x __pycache__ -x .DS_Store "$src" "$dest" >/dev/null 2>&1; then
  diff -r -x .git -x __pycache__ -x .DS_Store "$src" "$dest" >&2 || true
  die "o histórico não termina no estado final de $src"
fi
if [ -n "$(git status --porcelain)" ]; then
  git status --porcelain >&2
  die "working tree sujo ao final do plano"
fi
echo "ok: $name em $dest ($(git rev-list --count HEAD) commits, HEAD $(git rev-parse --short HEAD))"
