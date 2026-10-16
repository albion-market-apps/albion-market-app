# ADR-0001: Arquitetura inicial do monorepo

- Status: aceito
- Data: 2026-10-16

## Contexto

Precisamos de um rastreador de preços do mercado de Albion Online, multi-tenant,
com apps web e mobile, favorecendo free tiers e com arquitetura correta desde o
início (RLS, i18n, observabilidade mínima).

## Decisão

- **Monorepo** com `backend/`, `worker/`, `web/`, `mobile/`, `infra/`, `docs/`.
- **Backend**: FastAPI + SQLAlchemy 2.x (sync) + Alembic + Postgres 15.
  Sync em vez de async por simplicidade no MVP — revisar se o coletor ou os
  endpoints de comparação exigirem alta concorrência.
- **Multi-tenant via RLS do Postgres**: toda tabela de domínio tem `tenant_id`;
  policy `USING (tenant_id = current_setting('app.tenant_id')::uuid)`. A API
  resolve o tenant pelo header `X-Tenant-ID` (fallback: `TENANT_DEFAULT_ID`) e
  aplica `SET LOCAL app.tenant_id` por transação — nunca filtra tenant em
  memória/aplicação.
- **Worker separado da API**: coleta preços (hoje stub) e publica em Redis
  (`prices_updates`), em vez de a API fazer polling direto a cada request.
- **i18n**: web usa `next-intl` sem roteamento por `[locale]` (cookie
  `locale` + `getRequestConfig`), para manter a MVP simples; mobile usa
  `easy_localization` com JSON em `assets/translations/`.
- **Sem i18n no backend**: mensagens de erro/validação ficam neutras por ora.

## Consequências

- Trocar para Postgres gerenciado (Neon/Supabase) ou Redis gerenciado
  (Upstash) deve funcionar sem mudança de código — só variáveis de ambiente.
- RLS depende de toda query passar pela mesma `Session`/transação onde o
  `SET LOCAL` foi aplicado; qualquer acesso direto ao banco fora da dependency
  `get_tenant_db` quebra o isolamento — ver `app/db/rls.py`.
- Se o produto crescer para multi-tenant "pesado" (muitos tenants, volume
  alto), reavaliar RLS vs. schema-per-tenant.
