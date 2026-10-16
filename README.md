# Albion Market Tracker

Rastreador de preços do mercado de **Albion Online** em todas as cidades, com
suporte a múltiplos tenants (isolamento via RLS no Postgres) e i18n (pt-BR/en-US).

## Rodando localmente

Pré-requisitos: Docker + Docker Compose.

```bash
cp .env.example .env
make dev        # sobe db, redis, api, worker
make migrate    # aplica as migrações Alembic (cria tabelas + RLS)
make seed       # popula tenant "default", cidades e um seed leve de itens
```

- API: http://localhost:8000/health (deve responder `{"status":"ok"}`) e
  http://localhost:8000/metrics (Prometheus).
- Web: roda fora do Compose por ora — `cd web && pnpm install && pnpm dev` →
  http://localhost:3000.

Outros comandos: `make logs`, `make down`, `make fmt`, `make test`.

## Limites do MVP

- Worker faz *polling* (sem WebSocket real ainda) e o coletor de preços é um
  stub — ver TODOs em [worker/worker_app/collector.py](worker/worker_app/collector.py).
- Apenas o tenant "default" é usado; a arquitetura já suporta múltiplos
  tenants via RLS, mas não há UI de onboarding/gestão de tenant ainda.
- Seed de itens é parcial (3 itens de exemplo) — ver
  [backend/app/seeds/items.json](backend/app/seeds/items.json).
- Endpoints `/items`, `/prices` e `/alerts` estão majoritariamente stubados
  (ver TODOs no código) — próximos passos em [docs/claude.md](docs/claude.md).

## Mais detalhes

Decisões de arquitetura, histórico de setup e próximos passos:
[docs/claude.md](docs/claude.md) e [docs/adr/ADR-0001-arquitetura-inicial.md](docs/adr/ADR-0001-arquitetura-inicial.md).

## Licença

[MIT](LICENSE)
