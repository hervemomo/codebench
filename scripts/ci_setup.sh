#!/usr/bin/env bash
set -euo pipefail
docker compose build --pull
docker compose up -d db redis
docker compose run --rm api python -c "import fastapi, pandas, sklearn; print('deps OK')"
