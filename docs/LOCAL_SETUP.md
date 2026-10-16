# Rodando localmente (Windows / macOS / Linux)

Passo a passo completo pra subir a stack (Postgres + Redis + API + worker)
via Docker Compose e o web via `pnpm dev`. Se algo falhar, veja
[Erros comuns e soluções](#erros-comuns-e-soluções) no final.

## 1. Instalar Docker

- **Windows**: instale o [Docker Desktop](https://www.docker.com/products/docker-desktop/)
  (exige WSL2 — o instalador oferece habilitar automaticamente). Depois de
  instalar, abra o Docker Desktop e espere o ícone da baleia ficar "Running".
- **macOS**: instale o [Docker Desktop](https://www.docker.com/products/docker-desktop/)
  (`.dmg`, ou `brew install --cask docker`). Abra o app uma vez pra ele subir
  o daemon.
- **Linux**: instale o Docker Engine + Compose plugin pela [documentação
  oficial](https://docs.docker.com/engine/install/) (varia por distro — ex.
  Debian/Ubuntu: `sudo apt-get install docker.io docker-compose-plugin`).
  Adicione seu usuário ao grupo `docker` (`sudo usermod -aG docker $USER`)
  pra não precisar de `sudo` em todo comando, depois faça logout/login.

Confirme que funcionou:

```bash
docker --version
docker compose version
docker ps   # não deve dar erro de permissão/conexão
```

## 2. Configurar o `.env`

```bash
cp env/.env.example.dev .env
```

Abra o `.env` e gere um `TENANT_DEFAULT_ID` novo (não reuse um UUID de
outro ambiente):

```bash
python3 -c "import uuid; print(uuid.uuid4())"
```

Valide o arquivo antes de seguir:

```bash
make verify-env
```

Se aparecer qualquer `FALHA`, corrija antes de continuar — subir a stack
com um `.env` inválido só adia o erro pra dentro do container.

## 3. Subir a stack

```bash
make dev          # docker compose up -d --build (db, redis, api, worker)
```

Acompanhe os healthchecks:

```bash
docker compose -f infra/docker-compose.yml ps
# db, redis e api devem aparecer como "healthy" (worker não tem healthcheck)
```

## 4. Migrar e popular o banco

```bash
make migrate              # alembic upgrade head (schema + policies de RLS)
make seed                 # == make seed-items-cities: tenant default + cidades + catálogo + aliases
```

Ambos os alvos são idempotentes — pode rodar de novo sem medo.

## 5. Verificar a API

```bash
curl -i http://localhost:8000/health     # {"status":"ok"}
curl -i http://localhost:8000/metrics    # métricas Prometheus (texto)
curl "http://localhost:8000/items?query=T4&page=1&page_size=10"
```

Rodar a suíte de testes de integração (precisa da stack de pé):

```bash
make test-api
```

## 6. Subir o web e testar i18n

```bash
cd web
pnpm install
pnpm dev
```

Abra http://localhost:3000:
- Busque um item (ex.: "Espada") e confirme que a lista aparece.
- Troque o seletor de idioma no canto superior direito (pt-BR ↔ en-US) e
  confirme que os textos mudam.

## Erros comuns e soluções

**Porta em uso (`bind: address already in use`)**
Algo já está ouvindo em 5432 (Postgres local), 6379 (Redis local), 8000 ou
3000. Pare o processo conflitante ou mude a porta publicada em
`infra/docker-compose.yml` (ex.: `"5433:5432"`) — lembre de atualizar o
`DATABASE_URL` do `.env` também, se mudar a porta do `db`.

**Migração falha com erro de RLS / `current_setting` undefined**
Normalmente significa que algo tentou rodar uma query fora da dependency
`get_tenant_db` (que aplica `SET LOCAL`/`set_config` antes de qualquer
SELECT/INSERT). Se você estiver rodando algo manualmente dentro do
container (`docker compose exec api poetry run python`), use
`app.db.rls.set_tenant(db, tenant_id)` dentro de uma transação antes de
tocar nas tabelas com RLS — ver `backend/app/db/rls.py` e o exemplo em
`backend/app/seeds/load.py`.

**`make seed` falha com `duplicate key value violates ... tenants_slug_key`**
Você trocou `TENANT_DEFAULT_ID` no `.env` depois de já ter rodado o seed
uma vez contra esse banco. `backend/app/seeds/load.py` já lida com isso
(mantém o tenant "default" existente e avisa) — se ainda assim der erro,
pode ser um banco de um turno de desenvolvimento anterior; rode
`make down && docker volume rm albion-market-tracker_pgdata` pra começar
do zero (⚠️ apaga todos os dados locais).

**`.env` não é lido / `Settings` usa valores default**
Confirme que o `.env` está na **raiz** do projeto (não em `backend/.env`
nem `worker/.env`) — ver nota em `backend/app/core/config.py` sobre
`env_file=("../.env", ".env")`. Dentro dos containers isso não é problema
(as envs vêm do `docker-compose.yml` direto).

**Web mostra `/api/items` retornando erro / tela em branco**
Confirme que a API está respondendo em `http://localhost:8000/health`
antes de testar o web — o proxy do Next.js (`API_BASE_URL`, default
`http://localhost:8000`) precisa da API de pé. Veja também o changelog do
turno 3 em [docs/claude.md](claude.md): um bug real de formato de resposta
(`/items` mudou de array pra `{items, page, ...}`) já foi corrigido lá —
se você estiver numa branch anterior a essa correção, dê `git pull`.
