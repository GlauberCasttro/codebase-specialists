#!/usr/bin/env bash
# Shared helpers for deploy scripts. bash 3.2 compatible (ops laptops run macOS).
set -euo pipefail

log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

require_env() {
  local name
  for name in "$@"; do
    [ -n "${!name:-}" ] || die "missing env var $name"
  done
}
