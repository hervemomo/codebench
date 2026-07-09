#!/usr/bin/env bash
set -euo pipefail
docker compose build --pull
docker compose up -d db redis minio
docker compose run --rm api python -c "import fastapi, pandas, sklearn; print('deps OK')"

# Bootstrap the MinIO bucket used for uploaded/exported files. Retries the
# alias set until MinIO is actually accepting connections.
docker compose run --rm mc "
  until mc alias set local http://minio:9000 minioadmin minioadmin; do sleep 1; done &&
  mc mb -p local/codebench
"
