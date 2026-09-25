from typing import Annotated

from fastapi import Depends, Query, Request

from app.core.errors import ApiError
from app.services.repository import Snapshot


async def get_snapshot(request: Request) -> Snapshot:
    snapshot: Snapshot | None = request.app.state.snapshot
    if snapshot is None:
        raise ApiError(503, "data_unavailable", "Dados aprovados indisponíveis")
    return snapshot


SnapshotDep = Annotated[Snapshot, Depends(get_snapshot)]
PageNumber = Annotated[int, Query(ge=1, default=1)]
PageSize = Annotated[int, Query(ge=1, le=100, default=20)]
