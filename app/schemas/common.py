from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Status(StrEnum):
    ATIVO = "ativo"
    INATIVO = "inativo"
    DESCONHECIDO = "desconhecido"


class Fonte(StrictModel):
    source_id: str = Field(min_length=1)
    url: HttpUrl
    consultado_em: datetime

    @field_validator("consultado_em")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("consultado_em precisa incluir fuso horário")
        return value


class Entidade(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    nome: str = Field(min_length=1)
    status: Status = Status.DESCONHECIDO
    fonte: Fonte


T = TypeVar("T")


class PageMeta(StrictModel):
    page: int
    page_size: int
    total: int


class Page(StrictModel, Generic[T]):
    data: list[T]
    meta: PageMeta


class ErrorDetail(StrictModel):
    code: str
    message: str
    details: dict[str, str] | None = None


class ErrorResponse(StrictModel):
    error: ErrorDetail
