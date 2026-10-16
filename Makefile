.PHONY: dev down logs docker-up docker-down migrate seed seed-items-cities fmt test test-api verify-env verify-separation

dev: docker-up

docker-up:
	docker compose -f infra/docker-compose.yml up -d --build

down: docker-down

docker-down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f

migrate:
	./scripts/migrate.sh

seed:
	./scripts/seed.sh

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

# Valida o .env antes de subir a stack (dev) ou configurar um deploy (prod).
# Uso: make verify-env  |  make verify-env ENV_FILE=env/.env.example.prod
ENV_FILE ?= .env
verify-env:
	python3 scripts/check_env.py $(ENV_FILE)

# Mostra o checklist de separação (docs/SEPARATION.md) — NÃO verifica nada
# automaticamente: confirmar org/billing/2FA separados exige estar logado
# no GitHub/Vercel, o que este Makefile (e o Claude) não faz por você.
verify-separation:
	@cat docs/SEPARATION.md
