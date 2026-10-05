#!/usr/bin/env bash
# install_feature.sh <feature> <alvo>
#
# Prepara o alvo (já construído por build.sh py-billing e, normalmente, já com o time montado pela
# skill) para um eval de MODO AUTÔNOMO ou de CORREÇÃO DE BUG:
#   - feature (refund-percent | accept-float-amounts): copia spec para docs/specs/<feature>.md e os
#     testes de aceite para tests/acceptance/, confere que eles FALHAM hoje, commita e marca a tag
#     eval-baseline-<feature>.
#   - bug (bug-late-fee): copia só o relato (docs/bugs/<id>.md); o oráculo oculto NUNCA vai para o alvo.
# bash 3.2; sem heredoc em $(...).
set -eu
die() { echo "install_feature.sh: $*" >&2; exit 1; }

HERE=$(cd "$(dirname "$0")" && pwd)
feat=${1:-}; target=${2:-}
[ -n "$feat" ] && [ -n "$target" ] || die "uso: install_feature.sh <refund-percent|accept-float-amounts|bug-late-fee> <alvo>"
src="$HERE/py-billing-features/$feat"
[ -d "$src" ] || die "feature desconhecida: $feat"
[ -d "$target/.git" ] || die "alvo não é repositório git: $target"
target=$(cd "$target" && pwd)

if [ -f "$src/bug.json" ]; then
  mkdir -p "$target/docs/bugs"
  cp "$src/bug.md" "$target/docs/bugs/$feat.md"
  (cd "$target" && git add "docs/bugs/$feat.md" && \
    git -c user.name=eval -c user.email=eval@acme.example commit -q -m "docs(bug): report $feat" && \
    git tag -f "eval-baseline-$feat" >/dev/null)
  echo "ok: relato de bug $feat instalado (tag eval-baseline-$feat)"
  exit 0
fi

mkdir -p "$target/docs/specs" "$target/tests/acceptance"
cp "$src/spec.md" "$target/docs/specs/$feat.md"
cp "$src/tests/acceptance/"*.py "$target/tests/acceptance/"

if (cd "$target" && PYTHONPATH=src python3 -m unittest discover -s tests/acceptance >/dev/null 2>&1); then
  die "testes de aceite de $feat já passam no alvo — DoR exige testes que falham hoje"
fi

(cd "$target" && git add docs/specs tests/acceptance && \
  git -c user.name=eval -c user.email=eval@acme.example commit -q -m "test(acceptance): $feat (red, approved)" && \
  git tag -f "eval-baseline-$feat" >/dev/null)
echo "ok: $feat instalada em $target (testes de aceite vermelhos; tag eval-baseline-$feat)"
