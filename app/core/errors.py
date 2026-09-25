import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.common import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(
        self, status_code: int, code: str, message: str, details: dict[str, str] | None = None
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _response(status_code: int, code: str, message: str, details: dict[str, str] | None = None):
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=body.model_dump(exclude_none=True))


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError):
        return _response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, _exc: RequestValidationError):
        return _response(422, "validation_error", "Parâmetros inválidos")

    @app.exception_handler(Exception)
    async def internal_error_handler(_request: Request, exc: Exception):
        logger.exception("Falha inesperada na API", exc_info=exc)
        return _response(500, "internal_error", "Erro interno do serviço")
