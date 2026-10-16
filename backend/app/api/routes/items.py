from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.rls import get_current_tenant_id, get_tenant_db
from app.schemas.items import ItemOut, ItemsPage
from app.services.pricing import search_items

router = APIRouter(prefix="/items", tags=["items"])

MAX_PAGE_SIZE = 100


@router.get("", response_model=ItemsPage)
def list_items(
    query: str | None = Query(default=None, description="busca por code/name/aliases"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> ItemsPage:
    items, total = search_items(db, tenant_id, query, page, page_size)
    return ItemsPage(
        items=[ItemOut.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )
