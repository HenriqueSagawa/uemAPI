from typing import Annotated

from fastapi import APIRouter, Query

from app.api.v1.dependencies import PageNumber, PageSize, SnapshotDep
from app.api.v1.responses import DETAIL_ERRORS, LIST_ERRORS
from app.core.errors import ApiError
from app.schemas.common import Page
from app.schemas.departamento import Departamento
from app.services.queries import paginate

router = APIRouter(prefix="/departamentos", tags=["Departamentos"])


@router.get("", response_model=Page[Departamento], responses=LIST_ERRORS)
async def list_departamentos(
    snapshot: SnapshotDep,
    page: PageNumber = 1,
    page_size: PageSize = 50,
    centro: Annotated[str | None, Query(min_length=1)] = None,
    campus: Annotated[str | None, Query(min_length=1)] = None,
):
    records = snapshot.departamentos
    if centro is not None:
        records = tuple(
            item
            for item in records
            if item.centro_sigla and item.centro_sigla.casefold() == centro.casefold()
        )
    if campus is not None:
        records = tuple(item for item in records if item.campus_id == campus.casefold())
    return paginate(records, page, page_size)


@router.get(
    "/{sigla}",
    response_model=Departamento,
    responses=DETAIL_ERRORS,
)
async def get_departamento(sigla: str, snapshot: SnapshotDep):
    departamento = snapshot.find("departamentos", sigla, "sigla")
    if departamento is None:
        raise ApiError(404, "not_found", "Departamento não encontrado", {"sigla": sigla})
    return departamento
