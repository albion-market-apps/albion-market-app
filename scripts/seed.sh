#!/usr/bin/env bash
# Roda o seed (tenant default + cidades oficiais + catálogo de itens + aliases
# — ver backend/app/seeds/load.py). Idempotente: pode rodar várias vezes.
# RUN_LOCAL=1 roda via Poetry direto no host em vez de via container.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ "${RUN_LOCAL:-0}" = "1" ]; then
  (cd backend && poetry run python -m app.seeds.load)
else
  docker compose -f infra/docker-compose.yml exec api poetry run python -m app.seeds.load
fi
