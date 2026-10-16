# Deploy free-tier (Neon + Upstash + Render + Vercel + Cloudflare)

> **Nada aqui foi executado por mim** — exige login nas suas contas, que eu
> não tenho acesso neste ambiente. Este guia é o passo a passo pra você (ou
> uma sessão futura, já logada) executar. Ver `docs/claude.md`, changelog do
> turno 3, pra detalhes de por que isso ficou bloqueado.

Ordem recomendada: banco → cache → API/worker → web → DNS (cada etapa
depende da anterior ter gerado a URL/credencial usada na próxima).

## 1. Banco — Neon (Postgres, free)

1. Crie uma conta em https://neon.tech e um novo projeto.
2. Dentro do projeto, crie um banco (ou use o `neondb` padrão).
3. Em **Connection Details**, copie a "Pooled connection" (recomendado para
   serviços serverless/containers que abrem+fecham conexões com frequência).
4. Monte o `DATABASE_URL` no formato que o backend espera — troque o
   prefixo `postgresql://` por `postgresql+psycopg://` e garanta
   `?sslmode=require`:
   ```
   postgresql+psycopg://<user>:<password>@<endpoint>.neon.tech/<db>?sslmode=require
   ```
5. Guarde esse valor — vai para a env `DATABASE_URL` do serviço `albion-api`
   e `albion-worker` no Render (passo 3).

Rode as migrações contra o Neon **antes** de apontar a API pra ele (local,
com o Neon já com SSL liberado para seu IP — Neon libera por padrão):

```bash
DATABASE_URL="postgresql+psycopg://..." RUN_LOCAL=1 ./scripts/migrate.sh
DATABASE_URL="postgresql+psycopg://..." RUN_LOCAL=1 ./scripts/seed.sh
```

(`RUN_LOCAL=1` roda via Poetry direto no host em vez de via container —
exige `cd backend && poetry install` uma vez antes.)

## 2. Redis — Upstash (free)

1. Crie uma conta em https://upstash.com e um novo database Redis (escolha
   uma região próxima da região do Render que você vai usar no passo 3).
2. Na aba **Connect**, copie a URL no formato `rediss://` (TLS) — funciona
   direto com `redis-py` (`REDIS_URL` no `.env`/env do Render).
3. Guarde esse valor — vai para `REDIS_URL`.

## 3. API + worker — Render (free, via Docker)

1. Crie uma conta em https://render.com e conecte sua conta do GitHub.
2. **New → Blueprint** → aponte para o repositório `albion-market-app` →
   o Render lê `infra/render.yaml` (já no repo) e propõe os dois serviços:
   `albion-api` (web, com healthcheck `/health`) e `albion-worker`
   (background worker).
3. Antes de confirmar, preencha as envs marcadas `sync: false` no
   `render.yaml` pra cada serviço: `DATABASE_URL` (Neon, passo 1),
   `REDIS_URL` (Upstash, passo 2), `TENANT_DEFAULT_ID` (o mesmo UUID usado
   no seed — **não troque depois**, ver nota em `docs/claude.md`), e
   `SENTRY_DSN` (opcional, deixe vazio se não for usar).
4. Depois do primeiro deploy, confirme:
   ```bash
   curl https://<seu-servico>.onrender.com/health    # {"status":"ok"}
   curl https://<seu-servico>.onrender.com/metrics
   ```
5. Plano free do Render "dorme" depois de inatividade — a primeira request
   depois disso demora alguns segundos (cold start). Não é bug.

## 4. Web — Vercel (Hobby, free)

1. Crie uma conta em https://vercel.com, conecte o GitHub.
2. **Add New → Project** → selecione o repositório `albion-market-app`.
3. Em **Root Directory**, selecione `web` (o monorepo tem o Next.js dentro
   de `web/`, não na raiz — `web/vercel.json` já está configurado, mas o
   Root Directory precisa ser setado manualmente no dashboard).
4. Em **Environment Variables**, adicione `NEXT_PUBLIC_API_BASE_URL` com a
   URL do Render do passo 3 (ex.: `https://albion-api.onrender.com`) — e
   ajuste `web/next.config.js` se quiser usá-la no lugar de `API_BASE_URL`
   atual (hoje o proxy usa `API_BASE_URL`, sem o prefixo `NEXT_PUBLIC_`,
   porque o rewrite roda no servidor; `NEXT_PUBLIC_API_BASE_URL` só é
   necessário se algum componente cliente precisar chamar a API direto).
5. Deploy. Confirme a tela inicial abrindo e a busca funcionando contra a
   API do Render.

## 5. DNS/CDN — Cloudflare (opcional, free)

1. Se você tiver um domínio, adicione-o à Cloudflare (free plan) e aponte
   os nameservers pra lá.
2. Crie um registro `CNAME` pro domínio (ou subdomínio, ex. `app.`) apontando
   pro domínio gerado pela Vercel (`cname.vercel-dns.com` ou o que a Vercel
   indicar na aba Domains do projeto).
3. (Opcional, futuro multi-tenant) Um wildcard `*.seu-dominio.com` →
   mesmo CNAME, se algum dia cada tenant tiver subdomínio próprio — não é
   necessário pro MVP (1 tenant).
4. Ative "Proxied" (ícone de nuvem laranja) se quiser cache/CDN da
   Cloudflare na frente; "DNS only" se preferir que só a Vercel sirva.

## Checklist de pós-deploy

```bash
curl https://<render>.onrender.com/health     # {"status":"ok"}
curl https://<render>.onrender.com/metrics    # métricas Prometheus
curl "https://<render>.onrender.com/items?query=T4&page=1&page_size=10"
```

- [ ] `/health` retorna 200
- [ ] `/metrics` expõe métricas
- [ ] Web abre e a busca de itens retorna resultado
- [ ] `/prices?item_id=...&agg=1h` responde (vazio é esperado até o
      coletor real do worker estar implementado — ver TODO em
      `worker/worker_app/collector.py`)
- [ ] Trocar o header `X-Tenant-ID` pra um UUID aleatório retorna vazio em
      `/items` e `/prices` (confirma RLS em produção, não só local)

## CI/CD automático (`.github/workflows/cd.yml`)

Depois que o repositório estiver no GitHub, configure os secrets em
**Settings → Secrets and variables → Actions** pra que o push em `main`
dispare o deploy automaticamente (ver `docs/SECRETS.md` pra lista
completa). Sem os secrets configurados, o workflow roda os testes/build
normalmente e só **pula** os jobs de deploy (não falha).
