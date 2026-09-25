from typing import Literal

from app.schemas.common import Entidade


class Curso(Entidade):
    nivel: Literal["graduacao"] = "graduacao"
    grau: str | None = None
    modalidade: str | None = None
    campus_id: str | None = None
    centro_sigla: str | None = None
    departamento_sigla: str | None = None
