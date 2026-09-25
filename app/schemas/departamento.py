from pydantic import Field

from app.schemas.common import Entidade


class Departamento(Entidade):
    sigla: str = Field(min_length=1)
    centro_sigla: str | None = None
    campus_id: str | None = None
