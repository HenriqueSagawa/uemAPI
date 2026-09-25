from pydantic import Field

from app.schemas.common import Entidade


class Campus(Entidade):
    sigla: str = Field(min_length=1)
    cidade: str | None = None
    endereco: str | None = None
