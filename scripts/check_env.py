#!/usr/bin/env python3
"""Valida o `.env` do projeto antes de subir a stack (dev) ou configurar um
deploy (prod) — sem depender de nada além da stdlib, pra poder rodar antes
mesmo de `poetry install`/`pnpm install`.

Uso:
    python3 scripts/check_env.py            # valida ./.env (padrão)
    python3 scripts/check_env.py env/.env.example.prod

Saída: lista cada variável com OK/AVISO/FALHA. Sai com código 1 se houver
qualquer FALHA (AVISO não quebra o build, mas vale revisar).
"""

import re
import sys
import uuid
from pathlib import Path

REQUIRED = ["DATABASE_URL", "REDIS_URL", "TENANT_DEFAULT_ID", "API_RATE_LIMIT", "ALBION_BASE_URL"]
OPTIONAL = ["SENTRY_DSN"]


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def check(values: dict[str, str]) -> list[tuple[str, str, str]]:
    """Retorna lista de (nivel, variavel, mensagem). nivel: OK | AVISO | FALHA."""
    results: list[tuple[str, str, str]] = []

    for key in REQUIRED:
        if not values.get(key):
            results.append(("FALHA", key, "ausente ou vazia"))

    db_url = values.get("DATABASE_URL", "")
    if db_url:
        if db_url.startswith("postgresql+psycopg2://"):
            results.append(
                ("FALHA", "DATABASE_URL", "driver psycopg2, mas o backend usa psycopg (v3) — troque para postgresql+psycopg://")
            )
        elif not db_url.startswith("postgresql+psycopg://"):
            results.append(("AVISO", "DATABASE_URL", f"esquema inesperado (esperado postgresql+psycopg://): {db_url.split('://')[0]}"))
        else:
            results.append(("OK", "DATABASE_URL", "driver e esquema corretos"))

    redis_url = values.get("REDIS_URL", "")
    if redis_url:
        if redis_url.startswith(("redis://", "rediss://", "unix://")):
            results.append(("OK", "REDIS_URL", "esquema válido"))
        else:
            results.append(("FALHA", "REDIS_URL", f"esquema inválido: {redis_url.split('://')[0] if '://' in redis_url else redis_url}"))

    tenant_id = values.get("TENANT_DEFAULT_ID", "")
    if tenant_id:
        try:
            uuid.UUID(tenant_id)
            results.append(("OK", "TENANT_DEFAULT_ID", "UUID válido"))
        except ValueError:
            results.append(("FALHA", "TENANT_DEFAULT_ID", f"não é um UUID válido: {tenant_id!r}"))

    rate_limit = values.get("API_RATE_LIMIT", "")
    if rate_limit:
        if re.fullmatch(r"\d+", rate_limit):
            results.append(("OK", "API_RATE_LIMIT", "inteiro válido"))
        else:
            results.append(
                ("FALHA", "API_RATE_LIMIT", f"precisa ser um inteiro simples (ex.: 60), não {rate_limit!r} — app/core/config.py tipa como int")
            )

    albion_url = values.get("ALBION_BASE_URL", "")
    if albion_url:
        if not albion_url.startswith(("http://", "https://")):
            results.append(("FALHA", "ALBION_BASE_URL", f"não parece uma URL: {albion_url!r}"))
        elif albion_url.rstrip("/").endswith(("/prices", "/Prices")):
            results.append(
                (
                    "AVISO",
                    "ALBION_BASE_URL",
                    "termina em /prices — worker/worker_app/collector.py já monta "
                    "'{ALBION_BASE_URL}/prices/{items}.json'; isso geraria .../prices/prices/... duplicado",
                )
            )
        else:
            results.append(("OK", "ALBION_BASE_URL", "formato ok"))

    for key in OPTIONAL:
        if key in values:
            results.append(("OK", key, "presente (opcional)"))

    return results


def main() -> int:
    env_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".env")
    print(f"Validando {env_path}...\n")

    if not env_path.exists():
        print(f"FALHA: arquivo {env_path} não existe. Copie de .env.example e preencha.")
        return 1

    values = parse_env_file(env_path)
    results = check(values)

    has_failure = False
    for level, key, message in results:
        print(f"[{level:6}] {key}: {message}")
        if level == "FALHA":
            has_failure = True

    print()
    if has_failure:
        print("Resultado: FALHA — corrija os itens acima antes de subir a stack.")
        return 1

    print("Resultado: OK (revise os AVISOs se houver).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
