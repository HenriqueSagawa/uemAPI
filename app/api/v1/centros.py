from fastapi import APIRouter

from app.api.v1.dependencies import PageNumber, PageSize, SnapshotDep
from app.api.v1.responses import DETAIL_ERRORS, LIST_ERRORS
from app.core.errors import ApiError
from app.schemas.centro import Centro, CentroDetail
from app.schemas.common import Page
from app.services.queries import paginate

router = APIRouter(prefix="/centros", tags=["Centros"])


@router.get("", response_model=Page[Centro], responses=LIST_ERRORS)
async def list_centros(snapshot: SnapshotDep, page: PageNumber = 1, page_size: PageSize = 50):
    return paginate(snapshot.centros, page, page_size)


@router.get(
    "/{sigla}",
    response_model=CentroDetail,
    responses=DETAIL_ERRORS,
)
async def get_centro(sigla: str, snapshot: SnapshotDep):
    centro = snapshot.find("centros", sigla, "sigla")
    if centro is None:
        raise ApiError(404, "not_found", "Centro não encontrado", {"sigla": sigla})
    departamentos = sorted(
        item.sigla
        for item in snapshot.departamentos
        if item.centro_sigla and item.centro_sigla.casefold() == centro.sigla.casefold()
    )
    return CentroDetail(**centro.model_dump(), departamentos=departamentos)
