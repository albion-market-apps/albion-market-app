FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3

COPY backend/pyproject.toml backend/poetry.lock* /app/
RUN poetry install --no-interaction --no-ansi --no-root

COPY backend /app
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

# Roda migração + seed antes de subir (ver backend/entrypoint.sh — necessário
# no Render free tier, que não tem Shell pra `alembic upgrade head` manual).
# Usa $PORT se definido (Render injeta essa env var), senão 8000 (Compose local).
CMD ["/app/entrypoint.sh"]
