#!/usr/bin/env bash
# apply.sh <alvo> — saída BOA de referência do eval de accept-float-amounts (calibração L01 do check_run.py).
# Pré-condição: build.sh py-billing <alvo> + install_feature.sh accept-float-amounts <alvo>. Determinístico, sem LLM e sem rede.
# Detalhes (o que roda e por quê) em ../reference_run.py. bash 3.2.
set -eu
[ $# -eq 1 ] || { echo "uso: apply.sh <alvo>" >&2; exit 2; }
HERE=$(cd "$(dirname "$0")" && pwd)
exec python3 "$HERE/../reference_run.py" accept-float-amounts "$1"
