from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import alerts, health, items, prices
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title="Albion Market Tracker API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restringir por ambiente antes de ir para produção
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(items.router)
app.include_router(prices.router)
app.include_router(alerts.router)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
