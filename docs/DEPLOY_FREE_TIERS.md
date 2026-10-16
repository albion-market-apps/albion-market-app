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

## 4. Web — Netlify (free), não Vercel

**Mudança de plano registrada no turno 7/8**: Vercel não tem Team com plano
free de verdade (só Pro Trial ou Pro pago) — abandonado. Fomos de Netlify,
que também não tem Team nova free, mas permite deploy direto na conta
pessoal existente do usuário (sem custo, só sem separação de billing — ver
`docs/claude.md`). Site real: https://albion-web.netlify.app.

1. Login no Netlify com GitHub.
2. No site (`albion-web` já existe) → **Project configuration → Developer
   settings → Repository → Link repository** → GitHub → autorizar.
   - Se a organização do repo não aparecer na lista de contas: o GitHub
     App do Netlify precisa ser instalado/autorizado pra ela também —
     `github.com/apps/netlify/installations/new`, escolher a org, **"Only
     select repositories"** (menor privilégio) → só o repo do projeto.
   - **Netlify Starter (free) não deploya repositório privado de
     organização** — só público, ou privado de conta pessoal. Se o repo
     for privado de org, ou ele fica público, ou o deploy pede upgrade
     pra Pro ($20/mês). Decisão de visibilidade é sempre do usuário.
3. `web/netlify.toml` já configura `base = "web"`, `pnpm build`, plugin
   `@netlify/plugin-nextjs` — no passo "Configure project and deploy",
   confirme "Base directory" = `web` (às vezes vem em branco mesmo com o
   `netlify.toml` certo).
4. Em **Environment variables**, adicione `API_BASE_URL` (não
   `NEXT_PUBLIC_API_BASE_URL`!) com a URL do Render do passo 3. **Nome
   importa**: `web/next.config.js` lê `process.env.API_BASE_URL` — o
   rewrite roda no servidor, nunca precisa do prefixo `NEXT_PUBLIC_`. Usar
   o nome errado faz `/api/*` responder 500 sem nenhum aviso claro — bug
   real que aconteceu no turno 9, só percebido testando a busca de verdade
   no site publicado.
5. "Deploy" dispara o build (Git CD fica configurado — todo push em `main`
   que mexe em `web/` builda e publica de novo automaticamente).

Se algum dia a separação de billing via Team passar a importar de verdade
(ex.: o projeto crescer), reavaliar Vercel Pro ou Netlify com Team paga —
por ora, free com conta pessoal é a decisão vigente.

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
