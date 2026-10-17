from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.rls import get_current_tenant_id, get_tenant_db
from app.models.city import City
from app.schemas.refining import RefiningComparisonOut
from app.services.refining import refining_comparison_at_city

router = APIRouter(prefix="/refining", tags=["refining"])


@router.get("", response_model=list[RefiningComparisonOut])
def refining_at_city(
    city_id: UUID,
    db: Session = Depends(get_tenant_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> list[RefiningComparisonOut]:
    """Matéria-prima à venda em `city_id` ao lado do melhor preço de venda do
    material refinado correspondente — sem calcular lucro (decisão do
    usuário: taxa de retorno do refino depende de foco/especialização/
    premium, que a API de preços não sabe). Ordenado por tier."""
    rows = refining_comparison_at_city(db, tenant_id, city_id)
    if not rows:
        return []

    city_ids = {row.refined_best_city_id for row in rows}
    cities = {
        city.id: city
        for city in db.scalars(
            select(City).where(City.tenant_id == tenant_id, City.id.in_(city_ids))
        )
    }

    return [
        RefiningComparisonOut(
            tier=row.tier,
            raw_item_id=row.raw_item_id,
            raw_code=row.raw_code,
            raw_name=row.raw_name,
            raw_price=row.raw_price,
            refined_item_id=row.refined_item_id,
            refined_code=row.refined_code,
            refined_name=row.refined_name,
            refined_best_price=row.refined_best_price,
            refined_best_city_id=row.refined_best_city_id,
            refined_best_city_name=cities[row.refined_best_city_id].name,
        )
        for row in rows
        if row.refined_best_city_id in cities  # defensivo — RLS já garante mesmo tenant
    ]
