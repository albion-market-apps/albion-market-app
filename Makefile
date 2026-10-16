.PHONY: dev down logs migrate seed seed-items-cities fmt test test-api

dev:
	docker compose -f infra/docker-compose.yml up -d --build

down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f

migrate:
	docker compose -f infra/docker-compose.yml exec api poetry run alembic upgrade head

seed:
	docker compose -f infra/docker-compose.yml exec api poetry run python -m app.seeds.load

# Alias explícito para o seed de cidades+itens+aliases — hoje é o mesmo script
# de `make seed` (tenant default + cidades + catálogo); existe como alvo
# separado para o caso de `seed` ganhar outros dados (ex.: usuários) depois.
seed-items-cities: seed

fmt:
	cd backend && poetry run ruff format . && poetry run ruff check --fix .
	cd worker && poetry run ruff format . && poetry run ruff check --fix .
	cd web && pnpm lint --fix

test:
	cd backend && poetry run pytest -q
	cd web && pnpm type-check

# Testes de integração do backend (busca de /items, /prices raw+agregado,
# isolamento por RLS) — exigem Postgres+Redis reais, por isso rodam dentro do
# container da API já de pé via `make dev`.
test-api:
	docker compose -f infra/docker-compose.yml exec api poetry run pytest -q tests/
