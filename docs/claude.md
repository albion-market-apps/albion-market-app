# docs/claude.md — Albion Market Tracker

> Nota de contexto: este diretório (`/home/usuario/pessoal-painel`) tinha um
> `CLAUDE.md` de raiz tratando de outro projeto (motor de prospecção B2B da
> Sempreon). Este `docs/claude.md` é específico do projeto Albion Market
> Tracker, criado neste turno — não há relação entre os dois.

## Visão

Rastrear preços do mercado de **Albion Online** em todas as cidades do jogo,
para múltiplos tenants, com apps web e mobile e alertas de preço. MVP enxuto,
priorizando free tiers (Neon/Supabase para Postgres, Upstash para Redis,
Vercel para o web), mas com arquitetura multi-tenant e i18n corretas desde o
início.

## Decisões de stack

| Camada    | Escolha                                                              |
|-----------|-----------------------------------------------------------------------|
| Backend   | Python 3.11, Poetry, FastAPI, SQLAlchemy 2.x (sync), Alembic, Pydantic v2 |
| Worker    | Mesmo stack Python, processo separado, publica no Redis               |
| Web       | Next.js 14 (App Router), TypeScript strict, Tailwind, next-intl, SWR  |
| Mobile    | Flutter 3.x, Riverpod, Dio, easy_localization                         |
| Banco     | Postgres 15 com Row-Level Security (RLS) para isolamento multi-tenant |
| Cache/Bus | Redis (compatível Upstash) — canal `prices_updates`                   |
| Infra     | Docker Compose (db, redis, api, worker); Caddy/deploy fora do MVP     |

### Multi-tenant (RLS)

- Toda tabela de domínio tem `tenant_id UUID`.
- Policy padrão por tabela:
  `USING (tenant_id = current_setting('app.tenant_id')::uuid)`.
- A API resolve o tenant pelo header `X-Tenant-ID` (fallback
  `TENANT_DEFAULT_ID` do `.env`) e faz `SET LOCAL app.tenant_id` **dentro da
  mesma transação** antes de qualquer query — ver `backend/app/db/rls.py`
  (`set_tenant`, `get_tenant_db`).
- MVP usa só o tenant `default`, mas a dependency `get_tenant_db` já está
  pronta para múltiplos tenants.
- `tenants` (a tabela que define os tenants) **não** tem RLS — só as tabelas
  "de dentro" de um tenant (`users`, `memberships`, `cities`, `items`,
  `item_aliases`, `prices`, `alerts`).
- **Correção importante (achada testando contra Postgres real):** `SET LOCAL
  app.tenant_id = :valor` **não funciona** — `SET`/`SET LOCAL` não aceitam
  bind parameters no Postgres, só literais. `set_tenant()` usa
  `SELECT set_config('app.tenant_id', :tenant_id, true)` (o `true` = escopo
  da transação, equivalente a `SET LOCAL`), que é uma função normal e aceita
  parâmetro — mantém a defesa contra injection sem concatenar string.
- `get_tenant_db` (abre a sessão + aplica RLS) e `get_current_tenant_id`
  (só resolve o UUID do header) são dependencies **separadas** em
  `app/db/rls.py` — rotas que precisam do valor do tenant em código (ex.:
  montar a chave de cache) usam as duas; o FastAPI cacheia a segunda por
  request, então o header não é re-parseado.

### Catálogo de itens: code/name/enchant + aliases

- `items` agora tem `code` (unique_name do jogo, ex. `T4_BAG`), `name`
  (nome de exibição), `tier` e `enchant` (nível de encantamento; 0 = sem
  encantamento). A chave de unicidade é `(tenant_id, code, enchant)` — o
  mesmo `code` pode aparecer várias vezes com `enchant` diferente (linhas de
  preço distintas).
- `item_aliases` guarda variações de nome pra busca (nome em inglês,
  abreviação etc.), com RLS igual às outras tabelas do tenant.
- Migração `0002` fez `ALTER COLUMN` (`unique_name`→`code`,
  `display_name`→`name`) em vez de criar colunas novas — ok porque o projeto
  ainda não tem dado real em produção; se já tivesse, seria um `ADD COLUMN` +
  backfill + `DROP COLUMN` em etapas separadas.

### `GET /items` — busca, paginação e relevância

- Busca em `code` e `name` (`ILIKE %query%`) **e** em `item_aliases.alias`
  (via `EXISTS`, não `JOIN`, pra não duplicar linha quando o item tem vários
  aliases batendo).
- Relevância: match exato (0) > prefixo (1) > substring (2) > só via alias
  (3); dentro do mesmo rank, ordena por `name`.
- Paginação clássica `page`/`page_size` (`page_size` máx. 100); resposta traz
  `total` pra montar paginação no front.
- Índices `(tenant_id, code)` e `(tenant_id, name)` ajudam o `ORDER BY` e os
  matches de prefixo; não usamos `pg_trgm` por ora (extensão extra, custo de
  manutenção) — considerar se a base de itens crescer muito e o `ILIKE
  %meio%` começar a pesar.

### `GET /prices` — raw e agregações (1h/24h)

- `agg=raw`: últimos 200 registros **por cidade** (não no total), via CTE
  com `row_number() OVER (PARTITION BY city_id ORDER BY collected_at DESC)`
  — usa o índice `ix_prices_item_city_collected (item_id, city_id,
  collected_at DESC)`.
- `agg=1h`: agrupa por `date_trunc('hour', collected_at)` e cidade.
  `agg=24h`: agrupa por `date_trunc('day', collected_at)` (um bucket diário
  cobre a janela de 24h — mais simples/barato que buckets deslizantes).
- `sell_min/avg/max` são calculados sobre `sell_price_min` (o que um
  comprador pagaria); `buy_min/avg/max` sobre `buy_price_max` (o que um
  vendedor receberia); `qty_sum` é a soma de `qty` no bucket. Isso é uma
  escolha de modelagem pra ter 1 valor representativo por linha — revisar se
  o front precisar dos 4 campos brutos (`sell_price_min/max`,
  `buy_price_min/max`) agregados separadamente.
- `cities` filtra por `code` (`?cities=martlock,caerleon`), resolvido para
  `city_id` via `resolve_city_ids`. Sem `cities`, considera todas as cidades
  do tenant.

### Cache Redis de `/prices` (5 min)

- Chave: `tenant:{tenant_id}:prices:{item_id}:{cities_hash}:{agg}:{from}:{to}`
  — `cities_hash` é um sha1 curto da lista de `city_id` ordenada (chave curta
  e estável independente da ordem em que as cidades vêm na query string).
- `app/core/cache.py`: `get_cached_json`/`set_cached_json` (TTL 300s) e
  `invalidate_item_prices_cache(tenant_id, item_id)` — faz `SCAN` pelo
  prefixo `tenant:{tenant_id}:prices:{item_id}:*`, `DELETE` nas chaves
  encontradas e publica em `prices:cache_invalidated` (canal **diferente**
  do `prices_updates` do worker — um é "preço novo chegou", o outro é "cache
  deste item mudou").
- `record_prices()` (em `app/services/pricing.py`) é o ponto de inserção que
  chama a invalidação — é o que os testes usam pra popular dado, e é onde o
  futuro "consumer" do worker (TODO fase 1) deve plugar.

### i18n

- **Web**: `next-intl` sem roteamento por segmento `[locale]` — locale vem de
  um cookie (`locale`) lido em `web/src/i18n.ts` via `getRequestConfig`.
  Decisão deliberada para manter o MVP simples (evita middleware +
  `generateStaticParams` + duplicar rotas); revisar se precisar de URLs
  localizadas (`/en-US/...`) para SEO.
- **Mobile**: `easy_localization`, JSON em `mobile/assets/translations/`.
- **Backend**: sem i18n por ora (mensagens neutras).

## Como rodar

```bash
cp .env.example .env
make dev                # docker compose up -d --build (db, redis, api, worker)
make migrate             # alembic upgrade head (schema + RLS, incl. migração 0002)
make seed                # == make seed-items-cities: tenant default + 7 cidades + ~20 itens + aliases
make test-api             # pytest de integração dentro do container da api (precisa de make dev rodando)
```

Checagens:
- `curl http://localhost:8000/health` → `{"status":"ok"}`
- `curl http://localhost:8000/metrics` → métricas Prometheus
- Web: `cd web && pnpm install && pnpm dev` → http://localhost:3000

### Exemplos de cURL (tenant default — sem header `X-Tenant-ID`)

```bash
# busca de itens (relevância: exato > prefixo > substring > alias)
curl "http://localhost:8000/items?query=Espada&page=1&page_size=10"

# preços crus (últimos 200 por cidade), filtrando por cidade
curl "http://localhost:8000/prices?item_id=<UUID_DO_ITEM>&agg=raw&cities=martlock,caerleon"

# agregação por hora, com janela de tempo
curl "http://localhost:8000/prices?item_id=<UUID_DO_ITEM>&agg=1h&from=2026-10-20T00:00:00Z&to=2026-10-21T00:00:00Z"

# agregação diária (bucket de 24h)
curl "http://localhost:8000/prices?item_id=<UUID_DO_ITEM>&agg=24h"
```

Para outro tenant: `curl -H "X-Tenant-ID: <UUID_DO_TENANT>" ...`.
`<UUID_DO_ITEM>` sai de `GET /items`; sem dado em `prices` ainda (worker real
não está plugado — ver Fase 1), a resposta de `/prices` vem com `data: []`.

## Diagrama (texto)

```
┌─────────┐     HTTP      ┌──────────┐      SQL (RLS)     ┌────────────┐
│  Web    │ ────────────▶ │   API    │ ─────────────────▶ │  Postgres  │
│ Next.js │ ◀──────────── │ FastAPI  │ ◀───────────────── │   (tenants,│
└─────────┘   JSON         └────┬─────┘                    │ cities,   │
┌─────────┐                     │                           │ items,    │
│ Mobile  │ ───────────────────▶│                           │ prices,   │
│ Flutter │                     │                           │ alerts)   │
└─────────┘                     │                           └────────────┘
                                 │ publica
                                 ▼
                           ┌──────────┐      fetch (stub)    ┌────────────┐
                           │  Redis   │ ◀──────────────────  │   Worker   │
                           │ (pub/sub)│                       │ collector  │
                           └──────────┘                       └────────────┘
                                                                     │
                                                          TODO: Albion Online
                                                             Data Project API
```

## Próximos passos por fase

**Fase 1 (destravar o produto real) — em andamento**
- ~~Ligar `backend/app/api/routes/items.py` e `prices.py` ao banco~~ feito
  (ver `app/services/pricing.py` + RLS via `get_tenant_db`).
- ~~Cache Redis de 5 min para `/prices`~~ feito (`app/core/cache.py`).
- ~~Seed completo de cidades + catálogo inicial de itens + aliases~~ feito.
- **Falta**: implementar o coletor real em
  `worker/worker_app/collector.py` contra a Albion Online Data Project
  (`ALBION_BASE_URL`), substituindo o stub, e ligar o resultado a
  `app.services.pricing.record_prices()` — hoje essa função só é chamada
  pelos testes de integração para popular dado; é o "consumer" que falta
  entre o worker (publica em `prices_updates`) e o Postgres.

**Fase 2 (produto)**
- Endpoint `/compare`: menor preço de venda por cidade para um item,
  reaproveitando `query_aggregated_prices`/`query_raw_prices`.
- CRUD completo de `/alerts` (hoje só stub) + `alerts_runner` rodando como
  job periódico (worker ou APScheduler) que dispara notificação quando um
  alerta é cruzado.
- Expandir catálogo de itens (`backend/app/seeds/items.json` +
  `item_aliases.json`) com o catálogo completo via `ao-bin-dumps`.
- Avaliar `pg_trgm` se a busca de `/items` precisar de substring eficiente
  em uma base grande de itens (hoje usa `ILIKE` + índice btree simples).
- i18n mobile/web: revisar textos conforme telas reais forem criadas.

**Fase 3 (deploy free tier) — documentado e automatizado, não executado**
- Guia completo: [docs/DEPLOY_FREE_TIERS.md](DEPLOY_FREE_TIERS.md) (Neon →
  Upstash → Render → Vercel → Cloudflare, nessa ordem).
- `infra/render.yaml` (Blueprint do Render pra `albion-api`+`albion-worker`),
  `web/vercel.json`, `.github/workflows/cd.yml` (deploy condicional — roda
  testes/build sempre, só pula o deploy em si se os secrets não estiverem
  configurados) já estão no repo — ver changelog do turno 4.
- Continua exigindo do usuário: login nas contas Neon/Upstash/Render/Vercel
  (OAuth que eu não posso fazer por ele) e, pra push automático, um GitHub
  remoto configurado. Nada disso foi executado — só preparado.
- Sentry real (`SENTRY_DSN` já está no `.env.example`/`env/.env.example.*`,
  só falta integrar o SDK no código).

## Changelog de setup (turno 4 — docs e automação de deploy, sem executar login/deploy)

**Objetivo do turno**: depois que o turno 3 confirmou que Docker, `gh` CLI e
contas Neon/Upstash/Render/Vercel não estão disponíveis neste ambiente, o
usuário pediu pra eu **não** tentar contornar isso — em vez disso, preparar
toda a documentação e automação pra que ele (ou uma sessão futura já logada)
consiga rodar localmente e fazer o deploy sem precisar descobrir nada do
zero. Nenhum login, `git push` ou deploy real foi executado neste turno.

**Criados**
- [docs/LOCAL_SETUP.md](LOCAL_SETUP.md) — instalar Docker (Windows/macOS/
  Linux), configurar `.env`, subir a stack, migrar/seed, testar API e web,
  seção de erros comuns (porta em uso, erro de RLS, `.env` não lido, etc. —
  os dois últimos são os bugs reais que eu mesmo bati no turno 3).
- [docs/DEPLOY_FREE_TIERS.md](DEPLOY_FREE_TIERS.md) — passo a passo Neon →
  Upstash → Render (via `infra/render.yaml`) → Vercel (via `web/vercel.json`)
  → Cloudflare (opcional), nessa ordem, com checklist de pós-deploy.
- [docs/SECRETS.md](SECRETS.md) — tabela de toda variável/segredo por
  ambiente (dev, prod, GitHub Actions) e onde cada uma é setada.
- `env/.env.example.dev` e `env/.env.example.prod` — templates sem valores
  reais; o de prod documenta inline o formato esperado de cada provedor
  (ex.: Neon exige `?sslmode=require`, Upstash usa `rediss://`).
- `scripts/wait_for_db.sh`, `scripts/migrate.sh`, `scripts/seed.sh` —
  encapsulam o que antes estava inline no Makefile; suportam `RUN_LOCAL=1`
  pra rodar via Poetry direto no host (útil pra migrar/seed contra um Neon
  remoto sem precisar subir o container `api`).
- `scripts/check_env.py` — valida um `.env` sem depender de nada além da
  stdlib (roda antes mesmo de `poetry install`). Testado com o `.env` real
  do turno 3 (passa) e com os valores *literais* que o pedido original do
  turno 2 sugeria (`psycopg2`, `60/m`, UUID inválido — pega os 3 problemas
  corretamente, igual ao que achei manualmente no turno 3).
- `infra/render.yaml` — Blueprint do Render com os dois serviços
  (`albion-api` web + `albion-worker` background), healthcheck `/health`,
  envs sensíveis marcadas `sync: false`. **Não testado contra uma conta
  Render real** (sem acesso) — só validado como YAML sintaticamente válido.
- `web/vercel.json` — mínimo (`framework`, `buildCommand`, `installCommand`);
  sem rewrites próprios porque o proxy pra API já é feito em
  `web/next.config.js` via `API_BASE_URL` — duplicar em `vercel.json`
  criaria duas fontes de verdade pro mesmo rewrite.
- `.github/workflows/cd.yml` — roda testes de integração (com services
  postgres+redis, igual ao `ci.yml`) e o build do web em todo push pra
  `main`; os jobs `deploy-render` e `deploy-vercel` checam se os secrets
  necessários existem e, se não existirem, imprimem "Skipping deploy (no
  secrets)" e terminam com sucesso (não quebram o pipeline) — só disparam o
  deploy de verdade se os secrets estiverem configurados (ver
  `docs/SECRETS.md`).

**Alterados**
- `Makefile`: `migrate`/`seed` agora chamam `scripts/migrate.sh`/
  `scripts/seed.sh` (que por sua vez esperam o Postgres ficar pronto antes
  de rodar — `scripts/wait_for_db.sh`) em vez de ter o `docker compose exec`
  inline; `dev`/`down` viraram aliases de `docker-up`/`docker-down` (nomes
  pedidos no turno); novo alvo `verify-env` (roda `scripts/check_env.py`).
- `docs/claude.md` (este arquivo) — seção "Próximos passos > Fase 3"
  atualizada pra refletir que o deploy está documentado/automatizado, não
  executado.

**Verificado neste turno** (sem Docker/contas disponíveis, mesmas
limitações do turno 3):
- `bash -n` em todos os `.sh` novos → sintaxe ok.
- `python3 scripts/check_env.py .env` contra o `.env` real (gerado no turno
  3) → todos os campos `OK`.
- `python3 scripts/check_env.py` contra um `.env` com os valores *literais*
  do pedido original (`psycopg2://`, `TENANT_DEFAULT_ID=not-a-uuid`,
  `API_RATE_LIMIT=60/m`) → 3 `FALHA` + 1 `AVISO`, exit code 1 — confirma que
  o script bloqueia exatamente os problemas reais encontrados no turno 3.
- `.github/workflows/cd.yml`, `infra/render.yaml`, `web/vercel.json` →
  parseados com `yaml.safe_load`/`json.load` sem erro (só sintaxe — não dá
  pra validar semanticamente sem uma conta Render/Vercel real).
- `make verify-env` → roda o alvo novo do Makefile corretamente.

**Não verificado** (seguem as mesmas limitações do turno 3): o
`render.yaml` nunca foi de fato importado num projeto Render; o
`cd.yml` nunca rodou de verdade no GitHub Actions (precisa do repo lá);
`web/vercel.json` nunca passou por um build real da Vercel.

**Git**: nada mudou aqui além dos arquivos novos — ainda é só o commit
local do turno 3 (`59977e6`); este turno ainda não foi commitado (ver
mensagem sugerida abaixo). Repositório remoto continua não criado.

**Mensagem de commit sugerida (turno 4)**

```
docs: add local setup and free-tier deploy guides + scripts and CD scaffolding
```

## Changelog de setup (turno 3 — validação e2e, deploy prep)

**Objetivo do turno**: validação local end-to-end de tudo que foi construído
nos turnos 1–2, preparar `.env`, e deixar o repositório pronto pra git/CI/
deploy. **Importante**: este ambiente de execução não tem Docker, não tem
`sudo` sem senha, não tem `gh` CLI, e o browser embutido não tem sessão
logada em nenhuma conta (GitHub/Vercel/Render/Neon/Upstash) — então as
etapas 1 (instalar Docker), 6 (criar repo remoto + push) e 7 (deploy) do
pedido original **não puderam ser executadas de fato**. O que segue é o que
consegui fazer dentro dessas restrições, de forma honesta sobre o que é
validação real vs. o que ainda depende de ação do usuário.

### 1) Ambiente — parcial

- Docker/Compose: **indisponíveis** (`docker`: comando não encontrado) e
  `sudo` pede senha que não tenho — não tentei instalar (seria uma mudança
  de sistema sem como confirmar que teria sucesso, e instalar pacotes via
  sudo sem senha não é algo que eu deva simplesmente tentar contornar).
- `.env` criado na raiz com os valores pedidos, com 3 desvios conscientes do
  que foi pedido literalmente — documentados porque usar os valores exatos
  pedidos teria quebrado a aplicação:
  1. `DATABASE_URL`: pedido era
     `postgresql+psycopg2://postgres:postgres@db:5432/app`. Usei
     `postgresql+psycopg://albion:albion@localhost:5432/albion` — (a) o
     backend usa o driver `psycopg` (v3), não `psycopg2` (v3 é o que está
     no `pyproject.toml` desde o turno 1; trocar de driver é uma mudança de
     dependência, não só de config); (b) usuário/banco `albion`/`albion` já
     é o que `infra/docker-compose.yml` cria (mudar pra `postgres`/`app`
     quebraria o compose); (c) hostname `db` só resolve *dentro* da rede do
     Compose — pra quem roda o backend fora do Docker (o uso real de um
     `.env` na raiz, já que os containers recebem `DATABASE_URL` direto do
     `environment:` do `docker-compose.yml`, com precedência sobre o
     `env_file`), o host certo é `localhost` com a porta publicada.
  2. `API_RATE_LIMIT`: pedido era `60/m`. Usei `60` (inteiro) —
     `app/core/config.py` tipa esse campo como `int`; `"60/m"` quebraria o
     parsing do Pydantic no boot da aplicação. Documentado também no
     `.env.example`.
  3. `ALBION_BASE_URL`: pedido era
     `.../api/v2/stats/Prices`. Mantive `.../api/v2/stats` — o stub em
     `worker/worker_app/collector.py` já monta a URL final como
     `{ALBION_BASE_URL}/prices/{items}.json`; usar o valor pedido geraria
     `.../stats/Prices/prices/{items}.json` (duplicado).
  - `TENANT_DEFAULT_ID`: gerado um UUID v4 de verdade, como pedido:
    `dd410501-2e53-4e5c-857c-7e9c7c69e152`.
  - Também corrigi `app/core/config.py` e `worker_app/config.py`:
    `env_file` agora é `("../.env", ".env")` — antes, rodando o backend de
    dentro de `backend/` (fora do Docker), o Pydantic procurava
    `backend/.env` (que não existe), nunca o `.env` real na raiz do
    monorepo. Dentro do container isso não importa (as envs vêm direto do
    `docker-compose.yml`).
- `infra/docker-compose.yml` conferido linha a linha contra o `.env`:
  hostnames/portas batem (`db:5432`, `redis:6379` dentro da rede do
  Compose); nada precisou mudar lá.

### 2–3) Subir stack, migrar/seed, testar API — validado, mas sem Docker

Sem Docker, reproduzi o equivalente de `docker compose up` + `make migrate`
+ `make seed` + os `curl` pedidos usando **Postgres e Redis embarcados e
reais** (`pgserver` = Postgres 16 e `redislite`, instalados via `pip` numa
venv de scratch, sem precisar de root) rodando a API via `uvicorn` de
verdade em `0.0.0.0:8000`. Não é Docker, mas é Postgres/Redis/FastAPI
genuínos — não mocks, não SQLite.

```bash
# equivalente ao `make migrate`
alembic upgrade head
# -> 0001, depois 0002 aplicadas limpo num banco vazio

# equivalente ao `make seed && make seed-items-cities`
python -m app.seeds.load
# -> "Seed concluído: tenant default + cidades oficiais + catálogo de itens + aliases."
```

```bash
$ curl -s -i http://localhost:8000/health
HTTP/1.1 200 OK
content-type: application/json
{"status":"ok"}

$ curl -s "http://localhost:8000/items?query=T4&page=1&page_size=20" | jq '.total, .items[0]'
14
{
  "code": "T4_2H_BOW",
  "name": "Arco de Guerra",
  "tier": 4,
  "enchant": 0
}

$ curl -s "http://localhost:8000/prices?item_id=<T4_ORE>&cities=Lymhurst,Martlock&agg=1h" | jq '.data | length'
6   # 3 buckets de 1h x 2 cidades, com sell_min/avg/max, buy_min/avg/max e qty_sum
```

**Cache** — confirmado de duas formas (a medição de tempo pedida, isolada,
não é conclusiva nesse setup; expliquei por quê):
- `curl -w "%{time_total}"` repetido em `/prices?...&agg=1h`: ~3ms na 1ª
  chamada, ~2-3ms nas seguintes — diferença **dentro do ruído**, porque
  tanto o Postgres embarcado (socket Unix local) quanto o dataset de teste
  (12 linhas) são rápidos demais pra essa medição isolar o efeito do cache
  de forma visível. Isso é uma limitação do ambiente de teste, não evidência
  de que o cache não funciona.
- Inspeção direta do Redis (prova decisiva): a chave
  `tenant:{tenant}:prices:{item_id}:{hash}:1h:-:-` existe com TTL ≈ 279-290s
  (consistente com os 300s configurados) logo após a 1ª chamada — confirma
  que o cache populou e está vivo.

**RLS** — provado via `curl` real com header `X-Tenant-ID` de um tenant que
não existe:
```bash
$ curl -s -H "X-Tenant-ID: 99999999-9999-9999-9999-999999999999" \
    "http://localhost:8000/prices?item_id=<T4_ORE (do tenant default)>&agg=raw"
{"item_id":"...","agg":"raw","data":[]}

$ curl -s -H "X-Tenant-ID: 99999999-9999-9999-9999-999999999999" \
    "http://localhost:8000/items?query=T4"
{"items":[],"page":1,"page_size":20,"total":0}
```
Mesmo `item_id` do tenant default, mesmo catálogo — tenant diferente não vê
nada. Bônus: a resposta vazia do RLS probe foi cacheada sob sua **própria**
chave (namespaced por tenant), confirmando que não há vazamento de cache
entre tenants.

### 4) Web — testado contra a API real (não contra mock/offline)

`cd web && pnpm install && pnpm dev`, aberto no browser embutido contra a
API acima:
- Busca por "Ore" retornou 3 itens com relevância correta (nome, código e
  **alias** — "Espada Longa Mestre" apareceu via o alias "Claymore Mestre").
- Toggle de idioma pt-BR ↔ en-US funciona (textos mudam, resultado da busca
  persiste).
- `pnpm build`, `pnpm lint`, `pnpm type-check` — todos limpos após o fix
  abaixo.

### Bugs reais encontrados e corrigidos neste turno

Nenhum destes apareceria em lint/type-check isolado — só apareceram rodando
o sistema de ponta a ponta de verdade:

1. **Web quebrada contra a API real**: `GET /items` mudou de formato no
   turno 2 (`list[dict]` → `{items, page, page_size, total}`), mas
   `web/src/lib/api.ts` e `web/src/app/(pages)/page.tsx` continuaram
   esperando um array puro com campos antigos (`unique_name`/`display_name`).
   Resultado: `TypeError: items.map is not a function`, tela em branco.
   Corrigido: `fetchItems` agora tipa `ItemsPage`/`ItemResult` (com
   `code`/`name`/`enchant`), e a página lê `itemsPage.items`.
2. **`cities=Lymhurst,Martlock` (exemplo literal do pedido) não filtrava
   nada**: os `code` das cidades no seed estavam em minúsculo
   (`"martlock"`), então nenhum código bateu, e — pior — `resolve_city_ids`
   retornando lista vazia era tratado como "sem filtro", então a API
   devolvia **todas** as cidades em vez de um erro ou lista vazia.
   Corrigido em duas frentes:
   - `backend/app/seeds/cities.json`: `code` agora é o nome canônico da
     Albion Online Data Project (`"Martlock"`, `"FortSterling"`, etc.),
     batendo com o pedido e com o que o worker já usa.
   - `query_raw_prices`/`query_aggregated_prices`/rota `/prices`: semântica
     de `city_ids` agora é `None` = sem filtro (todas as cidades) vs.
     `[]` = filtro explícito que não bateu com nenhuma cidade (resultado
     correto: vazio). Ver docstring em `app/services/pricing.py`.
3. **Seed não era idempotente se `TENANT_DEFAULT_ID` mudasse**: `_seed_tenant`
   checava por `id`, mas `slug` tem unique constraint global — gerar um novo
   UUID v4 (como pedido no passo 1) e rodar o seed de novo contra um banco
   que já tinha um tenant "default" com outro id quebrava com
   `duplicate key value violates ... tenants_slug_key`. Corrigido: busca por
   `slug="default"` primeiro; se já existir com outro id, mantém o existente
   e avisa (não derruba o seed).

### 5) `docs/claude.md` — este changelog + seções atualizadas acima

### 6) Git — `git init` + commit local feitos; remoto não

- `git init`, branch renomeada pra `main` (consistente com `ci.yml`).
- **Decisão**: adicionei `/CLAUDE.md` ao `.gitignore`. O `CLAUDE.md` na raiz
  deste diretório é de outro projeto (notas de negócio da Sempreon — ver
  nota no topo deste arquivo) e nunca deveria ir pra um repositório chamado
  `albion-market-app`. Exclu-lo em vez de simplesmente dar `git add .` e
  publicar informação de negócio não relacionada.
- Resto do changelog de git/remoto/CI/deploy abaixo.
### 7) Deploy free-tier — não feito (ver bloqueios abaixo)

### O que ficou bloqueado, e o que preciso do usuário pra destravar

- **Docker**: não instalado (sem Docker/Compose no ambiente, `sudo` pede
  senha). Preciso que o usuário rode `make dev` no próprio ambiente com
  Docker, ou me dê acesso (ambiente com Docker, ou senha de sudo só se o
  usuário achar aceitável — não pedi a senha diretamente no chat).
- **Git remoto + GitHub**: o diretório não era repositório git
  (`git init` ainda não rodado — farei isso e o commit local, que são ações
  locais e reversíveis e já foram pedidas explicitamente). Criar o repo
  `albion-market-app` no GitHub e dar `git push` exige `gh` CLI autenticado
  ou um token — nenhum dos dois está disponível aqui, e não é algo que eu
  deva tentar contornar sozinho (login no GitHub em nome do usuário não é
  uma ação que eu faço). Preciso que o usuário rode `gh auth login` (ou me
  passe um token) e confirme que posso criar o repo e dar push.
- **Deploy (Neon/Upstash/Render/Vercel)**: todos exigem login OAuth em
  contas do usuário; o browser deste ambiente não tem nenhuma sessão salva.
  Não vou tentar logar como o usuário nesses serviços. Preciso que o
  usuário faça login manualmente (no browser embutido ou me diga que já tem
  conta/token) antes que eu possa criar os recursos e configurar as envs.

## Changelog de setup (turno 2 — dados reais, cache, testes de integração)

**Objetivo do turno**: ligar `/items` e `/prices` ao Postgres de fato, com
RLS, cache Redis de 5 min e seeds completos — ver seções acima (Catálogo de
itens, `/items`, `/prices`, Cache Redis) para o detalhe de cada decisão.

**Criados**
- `backend/alembic/versions/0002_items_catalog_and_prices_qty.py` — rename
  `unique_name`→`code`/`display_name`→`name`, nova coluna `items.enchant`,
  tabela `item_aliases` (+ RLS), coluna `prices.qty`, índice
  `ix_prices_item_city_collected (item_id, city_id, collected_at DESC)`.
- `backend/app/core/cache.py` — chave determinística, get/set com TTL,
  `invalidate_item_prices_cache` (SCAN + DELETE + publish).
- `backend/app/seeds/item_aliases.json` — aliases de busca para alguns itens.
- `backend/tests/conftest.py`, `test_items.py`, `test_prices.py`,
  `test_rls.py`, `tests/__init__.py` (necessário pro mypy não confundir
  `tests` como pacote namespace vs. módulo solto).
- `worker/tests/test_import.py` — smoke test (o job `python`/worker no CI
  falhava com "no tests collected" antes disso).

**Alterados**
- `backend/app/models/item.py` — `Item` ganhou `code`/`name`/`enchant`;
  nova classe `ItemAlias`.
- `backend/app/models/price.py` — nova coluna `qty`.
- `backend/app/db/rls.py` — **bug real corrigido**: `SET LOCAL app.tenant_id
  = :param` não compila no Postgres (`SET`/`SET LOCAL` não aceitam bind
  parameters); trocado por `SELECT set_config('app.tenant_id', :tenant_id,
  true)`. Também separei `get_current_tenant_id` de `get_tenant_db` (rotas
  que precisam do UUID do tenant em código, ex. pra chave de cache, não
  precisam mais fazer `SELECT current_setting(...)` pra redescobrir o valor).
- `backend/app/seeds/{cities.json,items.json,load.py}` — todas as 7 cidades
  oficiais, ~20 itens reais de exemplo (`code`/`name`/`tier`/`enchant`,
  incluindo 2 enchants do mesmo `code`), aliases; `load.py` reescrito
  idempotente (checa por `(tenant_id, code, enchant)` e `(tenant_id, item_id,
  alias)` antes de inserir).
- `backend/app/api/routes/items.py` — busca real via `search_items`
  (`ILIKE` + aliases + relevância) em vez de ler `items.json` do disco.
- `backend/app/api/routes/prices.py` — `raw`/`1h`/`24h` reais via
  `query_raw_prices`/`query_aggregated_prices`, com cache Redis.
- `backend/app/services/pricing.py` — reescrito: `search_items`,
  `resolve_city_ids`, `query_raw_prices` (CTE + `row_number()`),
  `query_aggregated_prices` (`date_trunc` + agregados), `record_prices`
  (insert + invalidação de cache).
- `backend/app/schemas/{items,prices}.py` — `ItemOut`/`ItemsPage` com
  `code`/`name`/`enchant`; `PriceRawOut`/`PriceBucketOut`/`PricesResponse`.
- `backend/pyproject.toml` — `per-file-ignores` pro `ruff` não marcar
  `Depends(...)`/`Query(...)` como "mutable default argument" (regra B008 —
  falso positivo no padrão de DI do FastAPI).
- `Makefile` — novos alvos `test-api` (pytest dentro do container da api) e
  `seed-items-cities` (hoje um alias de `seed`).
- `.github/workflows/ci.yml` — job `python` ganhou services `postgres` e
  `redis` + passos de `alembic upgrade head`/seed antes do `pytest` (só para
  `matrix.package == 'backend'`); sem isso os testes de integração não
  rodariam em CI.

**Verificado neste turno** — diferente do turno 1, desta vez consegui testar
contra bancos **reais**, sem Docker: instalei `pgserver` (Postgres 16
embarcado, sem root) e `redislite` (Redis embarcado) numa venv de scratch e
rodei o pipeline completo (`alembic upgrade head` → seed → `pytest`) contra
eles.

- **13 testes de integração passando** (`test_items.py`, `test_prices.py`,
  `test_rls.py`) contra Postgres+Redis reais — não mocks.
- `ruff check .` e `mypy .` limpos no backend.
- Dois bugs reais encontrados e corrigidos só por rodar contra Postgres de
  verdade (não apareceriam em `py_compile` nem em revisão de código):
  1. `SET LOCAL app.tenant_id = :tenant_id` — erro de sintaxe no Postgres
     (bind parameter não é aceito em `SET`). Ver `app/db/rls.py` acima.
  2. A fixture de teste usava o **mesmo UUID** do `TENANT_DEFAULT_ID` como
     "tenant A" — o teardown da fixture (`DELETE FROM items WHERE tenant_id
     = ...`) apagava o catálogo semeado pelo `make seed` por engano. Corrigido
     usando um UUID de teste dedicado, nunca igual ao tenant default.
- Testado manualmente (fora do pytest): cache populado na 1ª chamada a
  `/prices` (TTL 300s confirmado via `TTL` no Redis), e invalidado
  corretamente quando `record_prices` insere um preço novo para o mesmo item
  — a chamada seguinte já reflete o dado novo.
- `gen_random_uuid()` funciona nativo no Postgres 15/16 (built-in desde o
  PG13) — a extensão `pgcrypto` do `infra/initdb/01-extensions.sql` não é
  estritamente necessária pra isso, mas mantive por ora (outras funções de
  cripto podem precisar dela depois; custo de manter é baixo).

**Não verificado neste turno**: `make dev`/`docker compose` de fato (ainda
sem Docker no ambiente de execução) — o pipeline acima reproduz
Postgres+Redis+migração+seed+testes, mas não o Compose nem os healthchecks
dos containers em si. Recomendo rodar `make dev && make migrate && make seed
&& make test-api` num ambiente com Docker antes de considerar isso
"confirmado em produção".

**Mensagem de commit sugerida (turno 2)**

```
feat(api): liga /items e /prices ao Postgres com RLS, cache Redis e seeds completos
```

## Changelog de setup (turno 1 — bootstrap do monorepo)

**Criados** (estrutura completa do zero — diretório estava vazio exceto pelo
`CLAUDE.md` de outro projeto e `.claude/`):

- Raiz: `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `LICENSE` (MIT),
  `.gitignore`, `.editorconfig`, `.gitattributes`, `.env.example`, `Makefile`,
  `CODEOWNERS`, `commitlint.config.cjs`, `.pre-commit-config.yaml`.
- `.github/workflows/ci.yml`, `.github/dependabot.yml`.
- `docs/claude.md` (este arquivo), `docs/adr/ADR-0001-arquitetura-inicial.md`.
- `infra/docker-compose.yml`, `infra/backend.Dockerfile`,
  `infra/worker.Dockerfile`, `infra/initdb/01-extensions.sql` (pgcrypto).
- `backend/`: `pyproject.toml`, `alembic.ini` + `alembic/env.py` +
  `alembic/versions/0001_initial.py` (tabelas `tenants`, `users`,
  `memberships`, `cities`, `items`, `prices`, `alerts` + RLS), `app/main.py`,
  `app/core/{config,logging}.py`, `app/db/{session,rls}.py`, models,
  schemas, rotas (`health`, `items`, `prices`, `alerts`), `services/`
  (esqueletos), `seeds/` (cities.json, items.json, load.py),
  `tests/test_health.py`.
- `worker/`: `pyproject.toml`, `worker_app/{__main__,collector,config}.py`.
- `web/`: `package.json`, `next.config.js`, `tsconfig.json`,
  `tailwind.config.ts`, `postcss.config.js`, `.eslintrc.cjs`, `.prettierrc`,
  `src/i18n.ts`, `src/locale-config.ts`, `src/app/layout.tsx`,
  `src/app/locale-switcher.tsx`, `src/app/(pages)/page.tsx`,
  `src/app/globals.css`, `src/lib/api.ts`, `messages/{pt-BR,en-US}.json`.
- `mobile/`: `pubspec.yaml`, `analysis_options.yaml`, `lib/main.dart`,
  `lib/features/market/home_screen.dart`,
  `assets/translations/{pt-BR,en-US}.json`.

**Verificado neste turno** (ambiente sem Docker/Poetry/Flutter disponíveis,
mas com Node/pnpm):

- `cd web && pnpm install && pnpm build && pnpm lint && pnpm type-check` →
  todos passaram. O build pegou um erro real: `src/i18n.ts` importava
  `next/headers` e era importado por `locale-switcher.tsx` (client
  component), o que o Next.js rejeita. Corrigido extraindo as constantes
  (`SUPPORTED_LOCALES`, `LOCALE_COOKIE`, `resolveLocale`) para
  `src/locale-config.ts` (sem imports server-only), deixando `src/i18n.ts`
  só com o `getRequestConfig` que de fato precisa de `next/headers`.
- `pnpm dev` + browser: página inicial renderiza em pt-BR por padrão, troca
  para en-US via o seletor do header funciona (textos mudam de fato). A
  chamada a `/api/items` retorna 500 porque não há backend rodando nesta
  verificação (Docker indisponível no ambiente) — comportamento esperado,
  não é bug do web.
- `python3 -m py_compile` em todos os `.py` de `backend/` e `worker/` →ok.
- JSON de seeds, mensagens web e traduções mobile → válidos.

**Não verificado neste turno** (exige Docker, Poetry e Flutter, indisponíveis
no ambiente de execução): `make dev`, `make migrate`, `make seed`, `/health`,
`/metrics`, `flutter analyze`. Comandos para rodar quando esse tooling
estiver disponível:

```bash
make dev && make migrate && make seed
curl -i http://localhost:8000/health
curl -i http://localhost:8000/metrics
cd mobile && flutter pub get && flutter analyze
```

**Pendências / TODOs explícitos no código**
- `backend/app/api/routes/items.py`: lê `items.json` do disco em vez do
  banco — placeholder para destravar o front antes do CRUD real.
- `backend/app/api/routes/prices.py` e `alerts.py`: stubs (lista vazia /
  `NotImplementedError`).
- `worker/worker_app/collector.py`: `fetch_prices` ainda não chama a Albion
  Online Data Project de fato.
- `backend/app/services/{pricing,alerts_runner}.py`: só docstrings com o
  plano da Fase 2.
- `.github/workflows/ci.yml`: steps de `mypy` (backend/worker) e
  `flutter test` com `|| true` até tipagem/testes estarem completos — ver
  comentário TODO inline.
- `pnpm-lock.yaml` e `poetry.lock` **não foram gerados** neste turno (exigem
  rodar `pnpm install` / `poetry lock` localmente); o `Dockerfile` do backend
  referencia `poetry.lock*` de forma tolerante a isso.

**Mensagem de commit sugerida**

```
chore: bootstrap monorepo (api, worker, web, mobile, infra, ci, rls, i18n)
```
