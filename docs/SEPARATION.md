# Separação de contas e recursos

Este projeto (Albion Market Tracker) é **100% separado** da Sempreon e de
qualquer outro negócio do mantenedor. Nenhum recurso deste projeto deve
referenciar, compartilhar ou depender de:

- Organização/conta GitHub da Sempreon
- Domínios da Sempreon (`sempreontech.com.br` e variações)
- Billing/cartão de cobrança usado pela Sempreon
- Segredos, tokens ou credenciais de qualquer sistema da Sempreon

Infra, repositório, organização GitHub, team Vercel e contas de
banco/cache/deploy (Neon, Upstash, Render, Vercel) deste projeto são
provisionados à parte, mesmo que eventualmente reaproveitem o mesmo
provedor de nuvem que outro projeto do mantenedor — nunca a mesma conta,
organização ou billing.

## Checklist de separação

- [ ] Organização GitHub própria (não é a mesma que hospeda outros
      projetos do mantenedor)
- [ ] Billing da organização GitHub separado (Free, sem vínculo a
      enterprise/org existente)
- [ ] Team Vercel próprio, billing separado
- [ ] `DATABASE_URL`/`REDIS_URL` de produção apontam para recursos (Neon/
      Upstash) criados especificamente para este projeto
- [ ] Nenhum secret deste repositório/projeto é reaproveitado de outro
      projeto do mantenedor

Ver `docs/claude.md` para o status atual de cada item (preenchido conforme
os recursos forem de fato criados — ver seção "GitHub + Vercel").
