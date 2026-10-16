-- Habilita pgcrypto para geração de UUID (gen_random_uuid()) usado em todas as tabelas multi-tenant.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
