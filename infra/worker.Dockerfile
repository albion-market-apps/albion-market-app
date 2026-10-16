FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3

COPY worker/pyproject.toml worker/poetry.lock* /app/
RUN poetry install --no-interaction --no-ansi --no-root

COPY worker /app

CMD ["python", "-m", "worker_app"]
