from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Dentro do container, as envs vêm direto do docker-compose (env_file + o
    # `environment:` explícito do serviço), então nenhum `.env` chega a ser lido
    # aqui. Fora do container (ex.: `poetry run uvicorn` direto no host), o
    # `.env` real do projeto fica na raiz do monorepo, não em `backend/.env` —
    # por isso procura nos dois lugares (o mais específico por último, pra
    # poder sobrescrever o da raiz se precisar).
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://albion:albion@localhost:5432/albion"
    redis_url: str = "redis://localhost:6379/0"
    tenant_default_id: str = "00000000-0000-0000-0000-000000000001"
    api_rate_limit: int = 120
    sentry_dsn: str = ""
    albion_base_url: str = "https://www.albion-online-data.com/api/v2/stats"


@lru_cache
def get_settings() -> Settings:
    return Settings()
