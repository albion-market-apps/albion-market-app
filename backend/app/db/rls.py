from collections.abc import Generator
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal

settings = get_settings()


def set_tenant(db: Session, tenant_id: str) -> None:
    """Define o tenant da sessão atual (escopo da transação), respeitado pelas
    policies de RLS. Usa `set_config(..., is_local=true)` em vez de `SET LOCAL`
    porque `SET`/`SET LOCAL` não aceitam bind parameters no Postgres — só
    `set_config()` (uma função normal) aceita, o que evita concatenar o valor
    direto na string SQL.
    """
    db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": tenant_id}
    )


def get_current_tenant_id(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> UUID:
    """Resolve o tenant da requisição (header `X-Tenant-ID` ou `TENANT_DEFAULT_ID`)."""
    return UUID(x_tenant_id or settings.tenant_default_id)


def get_tenant_db(
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> Generator[Session, None, None]:
    """Dependency da API: abre uma sessão e aplica RLS (SET LOCAL app.tenant_id) na transação.

    Usar sempre junto com `get_current_tenant_id` como dependency separada nas
    rotas que precisam do valor do tenant_id em código (ver app/api/routes).
    """
    db = SessionLocal()
    try:
        with db.begin():
            set_tenant(db, str(tenant_id))
            yield db
    finally:
        db.close()
