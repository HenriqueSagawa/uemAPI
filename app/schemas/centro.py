from pydantic import Field

from app.schemas.common import Entidade


class Centro(Entidade):
    sigla: str = Field(min_length=1)


class CentroDetail(Centro):
    departamentos: list[str]
