# Variáveis e segredos

Onde cada valor vive, por ambiente. Regra geral: **nada de segredo real vai
pro git** — `.env` está no `.gitignore`; só `.env.example`,
`env/.env.example.dev` e `env/.env.example.prod` (sem valores reais) são
versionados.

## Desenvolvimento local

| Variável             | Onde setar                          | Exemplo / formato |
|-----------------------|--------------------------------------|--------------------|
| `DATABASE_URL`        | `.env` (raiz, copiado de `env/.env.example.dev`) | `postgresql+psycopg://albion:albion@localhost:5432/albion` |
| `REDIS_URL`           | `.env`                               | `redis://localhost:6379/0` |
| `TENANT_DEFAULT_ID`   | `.env`                               | UUID v4 — gerar com `python3 -c "import uuid; print(uuid.uuid4())"` |
| `API_RATE_LIMIT`      | `.env`                               | inteiro, ex. `120` (NÃO `"60/m"`) |
| `SENTRY_DSN`          | `.env`                               | vazio = desabilitado |
| `ALBION_BASE_URL`     | `.env`                               | `https://www.albion-online-data.com/api/v2/stats` (sem `/prices` no final) |

Validar: `make verify-env` (roda `scripts/check_env.py .env`).

Dentro dos containers `api`/`worker` do Compose, `DATABASE_URL`/`REDIS_URL`
vêm direto de `infra/docker-compose.yml` (`environment:` do serviço), não
do `.env` — ver nota em `docs/claude.md` (turno 3).

## Produção (Render + Vercel)

| Variável                     | Onde setar                          | Fonte |
|-------------------------------|--------------------------------------|-------|
| `DATABASE_URL`                | Render → `albion-api` e `albion-worker` → Environment | Neon (connection string "pooled", com `?sslmode=require`) |
| `REDIS_URL`                   | Render → `albion-api` e `albion-worker` → Environment | Upstash (URL `rediss://`) |
| `TENANT_DEFAULT_ID`           | Render → `albion-api` e `albion-worker` → Environment | UUID v4 gerado **uma vez** — nunca trocar depois do primeiro seed em prod (ver bug documentado em `docs/claude.md`) |
| `API_RATE_LIMIT`              | Render → `albion-api`                | inteiro, ex. `60` |
| `SENTRY_DSN`                  | Render → `albion-api` e `albion-worker` (opcional) | DSN do projeto Sentry |
| `ALBION_BASE_URL`             | Render → `albion-api` e `albion-worker` | `https://www.albion-online-data.com/api/v2/stats` |
| `NEXT_PUBLIC_API_BASE_URL`    | Vercel → Project → Environment Variables | URL pública do serviço `albion-api` no Render |

`infra/render.yaml` já declara essas chaves (com `sync: false` pros
sensíveis) — o Render pede os valores na tela de criação do Blueprint.

## Secrets do GitHub Actions (`.github/workflows/cd.yml`)

Settings → Secrets and variables → Actions → New repository secret:

| Secret                     | Onde conseguir |
|------------------------------|----------------|
| `RENDER_API_KEY`             | Render → Account Settings → API Keys |
| `RENDER_SERVICE_ID_API`      | Render → serviço `albion-api` → Settings → Service ID |
| `RENDER_SERVICE_ID_WORKER`   | Render → serviço `albion-worker` → Settings → Service ID |
| `VERCEL_TOKEN`               | Vercel → Account Settings → Tokens |
| `VERCEL_ORG_ID`              | Vercel → Project → Settings → General ("Project ID" / `vercel link` local gera `.vercel/project.json` com os dois ids) |
| `VERCEL_PROJECT_ID`          | idem |

Sem esses secrets, `cd.yml` roda testes/build normalmente e os jobs de
deploy só imprimem "Skipping deploy (no secrets)" — não quebram o pipeline.

## Nunca commitar

- `.env` (já no `.gitignore`)
- Qualquer `DATABASE_URL`/`REDIS_URL` com credencial real
- Tokens (`RENDER_API_KEY`, `VERCEL_TOKEN`, etc.) em qualquer arquivo do
  repositório, incluindo este — os exemplos acima são só os *nomes* das
  variáveis, nunca valores reais.
