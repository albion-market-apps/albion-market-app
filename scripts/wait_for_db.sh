#!/usr/bin/env bash
# Espera o Postgres aceitar conexões antes de rodar migração/seed.
# Uso padrão (dentro do Compose): ./scripts/wait_for_db.sh
# Fora do Docker: PGHOST=localhost PGPORT=5432 ./scripts/wait_for_db.sh
set -euo pipefail

TIMEOUT_SECONDS="${WAIT_FOR_DB_TIMEOUT:-60}"
COMPOSE_FILE="infra/docker-compose.yml"

elapsed=0
echo "Aguardando Postgres ficar pronto (timeout: ${TIMEOUT_SECONDS}s)..."

is_ready() {
  if [ -n "${PGHOST:-}" ]; then
    pg_isready -h "${PGHOST}" -p "${PGPORT:-5432}" -U "${PGUSER:-albion}" >/dev/null 2>&1
  else
    docker compose -f "$COMPOSE_FILE" exec -T db pg_isready -U albion -d albion >/dev/null 2>&1
  fi
}

until is_ready; do
  if [ "$elapsed" -ge "$TIMEOUT_SECONDS" ]; then
    echo "ERRO: Postgres não ficou pronto em ${TIMEOUT_SECONDS}s." >&2
    echo "Rode 'docker compose -f ${COMPOSE_FILE} logs db' (ou 'make logs') para investigar." >&2
    exit 1
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done

echo "Postgres pronto."
