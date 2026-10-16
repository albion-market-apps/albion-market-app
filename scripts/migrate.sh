#!/usr/bin/env bash
# Roda as migrações Alembic. Por padrão assume a stack do Compose rodando
# (`make dev` / `docker compose up -d`); com RUN_LOCAL=1, roda via Poetry
# direto no host (exige `cd backend && poetry install` antes).
set -euo pipefail

cd "$(dirname "$0")/.."
./scripts/wait_for_db.sh

if [ "${RUN_LOCAL:-0}" = "1" ]; then
  (cd backend && poetry run alembic upgrade head)
else
  docker compose -f infra/docker-compose.yml exec api poetry run alembic upgrade head
fi

echo "Migrações aplicadas."
