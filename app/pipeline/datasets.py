"""Datasets e modelos canônicos usados pelo pipeline."""

from app.schemas.campus import Campus
from app.schemas.centro import Centro
from app.schemas.curso import Curso
from app.schemas.departamento import Departamento

DATASETS = ("campi", "centros", "departamentos", "cursos")

MODELS = {
    "campi": Campus,
    "centros": Centro,
    "departamentos": Departamento,
    "cursos": Curso,
}
