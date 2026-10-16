from fastapi import APIRouter

from app.schemas.alerts import AlertCreate, AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts() -> list[AlertOut]:
    # TODO: implementar CRUD completo com a tabela `alerts` (RLS por tenant).
    return []


@router.post("", response_model=AlertOut, status_code=201)
def create_alert(payload: AlertCreate) -> AlertOut:
    # TODO: persistir no banco; aqui só eco dos dados recebidos para destravar o front.
    raise NotImplementedError("TODO: persistência de alerts ainda não implementada")
