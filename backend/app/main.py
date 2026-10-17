import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import alerts, cities, health, items, opportunities, prices
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.services.collector import collect_once

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


async def _collector_loop() -> None:
    """Coleta preços reais em loop, direto no processo da API.

    Por quê aqui e não num worker separado: o Render free tier não tem
    plano gratuito de Background Worker (ver docs/claude.md, turno 11) —
    rodar em processo é o jeito de ter coleta periódica sem upgrade de
    plano. `asyncio.to_thread` porque `collect_once` é código síncrono
    (SQLAlchemy sync + httpx sync) e não pode bloquear o event loop.
    """
    tenant_id = UUID(settings.tenant_default_id)
    while True:
        try:
            await asyncio.to_thread(collect_once, tenant_id)
        except Exception:
            logger.exception("coletor: falha num ciclo de coleta, tentando de novo no próximo")
        await asyncio.sleep(settings.poll_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_collector_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="Albion Market Tracker API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restringir por ambiente antes de ir para produção
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(items.router)
app.include_router(cities.router)
app.include_router(prices.router)
app.include_router(opportunities.router)
app.include_router(alerts.router)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
