from pydantic import Field

from app.schemas.common import Entidade


class Campus(Entidade):
    sigla: str | None = Field(min_length=1)
    cidade: str | None = None
    endereco: str | None = None
