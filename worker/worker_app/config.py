from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Mesma lógica do backend (ver app/core/config.py): fora do container o
    # `.env` real está na raiz do monorepo, não em `worker/.env`.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://albion:albion@localhost:5432/albion"
    redis_url: str = "redis://localhost:6379/0"
    tenant_default_id: str = "00000000-0000-0000-0000-000000000001"
    albion_base_url: str = "https://www.albion-online-data.com/api/v2/stats"
    poll_interval_seconds: int = 300  # TODO (fase 2): usar isso no loop real do __main__


@lru_cache
def get_settings() -> Settings:
    return Settings()
