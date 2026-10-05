#!/usr/bin/env bash
# deploy.sh <image-tag>: migrate first, then roll the service. Migrations must be backward
# compatible with the previous image (expand/contract), because old pods keep running.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
require_env DATABASE_URL REGISTRY SERVICE_NAME

tag=${1:?usage: deploy.sh <image-tag>}
image="$REGISTRY/fleetd:$tag"

log "migrating database"
"$(dirname "$0")/migrate.sh"

log "rolling $SERVICE_NAME to $image"
gcloud run deploy "$SERVICE_NAME" --image "$image" --region southamerica-east1 --quiet
echo "$tag" > .last_deployed_tag
