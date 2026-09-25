from fastapi import APIRouter

from app.api.v1.dependencies import PageNumber, PageSize, SnapshotDep
from app.api.v1.responses import DETAIL_ERRORS, LIST_ERRORS
from app.core.errors import ApiError
from app.schemas.campus import Campus
from app.schemas.common import Page
from app.services.queries import paginate

router = APIRouter(prefix="/campi", tags=["Câmpus"])


@router.get("", response_model=Page[Campus], responses=LIST_ERRORS)
async def list_campi(snapshot: SnapshotDep, page: PageNumber = 1, page_size: PageSize = 50):
    return paginate(snapshot.campi, page, page_size)


@router.get(
    "/{id}",
    response_model=Campus,
    responses=DETAIL_ERRORS,
)
async def get_campus(id: str, snapshot: SnapshotDep):
    campus = snapshot.find("campi", id)
    if campus is None:
        raise ApiError(404, "not_found", "Câmpus não encontrado", {"id": id})
    return campus
