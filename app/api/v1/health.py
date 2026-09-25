from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.services.repository import Snapshot

router = APIRouter(tags=["Saúde"])


class HealthResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    version: str
    datasets: dict[str, int]
    snapshot_consultado_em: datetime | None


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
async def health(request: Request, response: Response):
    snapshot: Snapshot | None = request.app.state.snapshot
    if snapshot is None:
        response.status_code = 503
    return HealthResponse(
        status="ready" if snapshot else "unavailable",
        version=request.app.state.settings.version,
        datasets=snapshot.counts if snapshot else {},
        snapshot_consultado_em=snapshot.consultado_em if snapshot else None,
    )
