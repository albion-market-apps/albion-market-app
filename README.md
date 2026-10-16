# Albion Market Tracker

Rastreador de preços do mercado de **Albion Online** em todas as cidades, com
suporte a múltiplos tenants (isolamento via RLS no Postgres) e i18n (pt-BR/en-US).

## Rodando localmente

Pré-requisitos: Docker + Docker Compose. Passo a passo detalhado (Windows/
macOS/Linux) com solução de erros comuns: [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md).

```bash
cp env/.env.example.dev .env   # preencha TENANT_DEFAULT_ID com um UUID v4 novo
make verify-env                # valida o .env antes de subir a stack
make dev                       # sobe db, redis, api, worker
make migrate                   # aplica as migrações Alembic (cria tabelas + RLS)
make seed                      # tenant default + 7 cidades oficiais + catálogo de itens + aliases
```

- API: http://localhost:8000/health (deve responder `{"status":"ok"}`) e
  http://localhost:8000/metrics (Prometheus).
- Web: roda fora do Compose por ora — `cd web && pnpm install && pnpm dev` →
  http://localhost:3000.
- Testes de integração (precisa da stack de pé): `make test-api`.

Outros comandos: `make logs`, `make down`, `make fmt`, `make test`.

## Deploy (free tiers)

Guia completo (Neon + Upstash + Render + Vercel): [docs/DEPLOY_FREE_TIERS.md](docs/DEPLOY_FREE_TIERS.md).
Lista de variáveis/segredos por ambiente: [docs/SECRETS.md](docs/SECRETS.md).
CI/CD condicional (só faz deploy se os secrets estiverem configurados):
[.github/workflows/cd.yml](.github/workflows/cd.yml).

## Limites do MVP

- Worker faz *polling* (sem WebSocket real ainda) e o coletor de preços é um
  stub — ver TODOs em [worker/worker_app/collector.py](worker/worker_app/collector.py).
- Apenas o tenant "default" é usado; a arquitetura já suporta múltiplos
  tenants via RLS, mas não há UI de onboarding/gestão de tenant ainda.
- Catálogo de itens é parcial (~20 itens de exemplo) — ver
  [backend/app/seeds/items.json](backend/app/seeds/items.json).
- `/alerts` está stubado (ver TODOs no código) — próximos passos em
  [docs/claude.md](docs/claude.md).

## Mais detalhes

Decisões de arquitetura, histórico de setup (changelog por turno) e
próximos passos: [docs/claude.md](docs/claude.md) e
[docs/adr/ADR-0001-arquitetura-inicial.md](docs/adr/ADR-0001-arquitetura-inicial.md).

## Licença

[MIT](LICENSE)
