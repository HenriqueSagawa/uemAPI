from typing import Annotated

from fastapi import APIRouter, Query

from app.api.v1.dependencies import PageNumber, PageSize, SnapshotDep
from app.api.v1.responses import DETAIL_ERRORS, LIST_ERRORS
from app.core.errors import ApiError
from app.schemas.common import Page
from app.schemas.curso import Curso
from app.services.queries import paginate

router = APIRouter(prefix="/cursos", tags=["Cursos"])


@router.get("", response_model=Page[Curso], responses=LIST_ERRORS)
async def list_cursos(
    snapshot: SnapshotDep,
    page: PageNumber = 1,
    page_size: PageSize = 50,
    campus: Annotated[str | None, Query(min_length=1)] = None,
    centro: Annotated[str | None, Query(min_length=1)] = None,
    grau: Annotated[str | None, Query(min_length=1)] = None,
    modalidade: Annotated[str | None, Query(min_length=1)] = None,
):
    records = snapshot.cursos
    if campus is not None:
        records = tuple(item for item in records if item.campus_id == campus.casefold())
    if centro is not None:
        records = tuple(
            item
            for item in records
            if item.centro_sigla and item.centro_sigla.casefold() == centro.casefold()
        )
    if grau is not None:
        records = tuple(
            item for item in records if item.grau and item.grau.casefold() == grau.casefold()
        )
    if modalidade is not None:
        records = tuple(
            item
            for item in records
            if item.modalidade and item.modalidade.casefold() == modalidade.casefold()
        )
    return paginate(records, page, page_size)


@router.get(
    "/{id}",
    response_model=Curso,
    responses=DETAIL_ERRORS,
)
async def get_curso(id: str, snapshot: SnapshotDep):
    curso = snapshot.find("cursos", id)
    if curso is None:
        raise ApiError(404, "not_found", "Curso não encontrado", {"id": id})
    return curso
