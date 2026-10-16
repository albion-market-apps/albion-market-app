#!/bin/sh
# Entrypoint de produção: roda migração + seed antes de subir a API.
#
# Por quê aqui e não só via `make migrate`/`make seed` manual: no Render
# (free tier), o Web Service não tem Shell disponível pra rodar comandos
# avulsos no container — a única forma de migrar o banco é no boot do
# próprio processo. Migrate+seed são idempotentes (ver
# backend/app/seeds/load.py), então rodar em todo cold start é seguro;
# reavaliar se o catálogo de seed crescer a ponto do tempo de boot incomodar.
set -e

echo "Rodando migrações..."
alembic upgrade head

echo "Rodando seed..."
python -m app.seeds.load

echo "Subindo a API..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
