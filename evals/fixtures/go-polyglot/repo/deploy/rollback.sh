#!/usr/bin/env bash
# rollback.sh <previous-tag>: rolls the service back. NEVER runs down migrations in production;
# schema stays expanded and the previous image must still work with it.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
require_env REGISTRY SERVICE_NAME
prev=${1:?usage: rollback.sh <previous-tag>}
gcloud run deploy "$SERVICE_NAME" --image "$REGISTRY/fleetd:$prev" --region southamerica-east1 --quiet
log "rolled back to $prev"
