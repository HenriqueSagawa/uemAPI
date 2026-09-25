import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.schemas.campus import Campus
from app.schemas.centro import Centro
from app.schemas.curso import Curso
from app.schemas.departamento import Departamento

DATASET_TYPES = {
    "campi": Campus,
    "centros": Centro,
    "departamentos": Departamento,
    "cursos": Curso,
}


class DatasetError(Exception):
    """An approved dataset is missing or invalid."""


@dataclass(frozen=True)
class Snapshot:
    campi: tuple[Campus, ...]
    centros: tuple[Centro, ...]
    departamentos: tuple[Departamento, ...]
    cursos: tuple[Curso, ...]
    indexes: Mapping[tuple[str, str], Mapping[str, Any]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        indexes = {}
        for dataset in DATASET_TYPES:
            records = self.records(dataset)
            indexes[(dataset, "id")] = MappingProxyType(
                {record.id.casefold(): record for record in records}
            )
            if dataset != "cursos":
                indexes[(dataset, "sigla")] = MappingProxyType(
                    {
                        record.sigla.casefold(): record
                        for record in records
                        if record.sigla is not None
                    }
                )
        object.__setattr__(self, "indexes", MappingProxyType(indexes))

    def records(self, dataset: str) -> tuple[Any, ...]:
        return getattr(self, dataset)

    def find(self, dataset: str, key: str, field: str = "id") -> Any | None:
        return self.indexes[(dataset, field)].get(key.casefold())

    @property
    def consultado_em(self):
        return max(
            record.fonte.consultado_em
            for dataset in DATASET_TYPES
            for record in self.records(dataset)
        )

    @property
    def counts(self) -> dict[str, int]:
        return {dataset: len(self.records(dataset)) for dataset in DATASET_TYPES}


def _unique(records: tuple[Any, ...], field: str, dataset: str) -> None:
    keys = [value.casefold() for record in records if (value := getattr(record, field)) is not None]
    if len(keys) != len(set(keys)):
        raise DatasetError(f"{dataset}: {field} duplicado")


def _references_exist(snapshot: Snapshot) -> None:
    campus_ids = {item.id for item in snapshot.campi}
    centro_siglas = {item.sigla.casefold() for item in snapshot.centros}
    departamentos = {item.sigla.casefold(): item for item in snapshot.departamentos}

    for departamento in snapshot.departamentos:
        if departamento.centro_sigla and departamento.centro_sigla.casefold() not in centro_siglas:
            raise DatasetError("departamentos: referência a centro inexistente")
        if departamento.campus_id and departamento.campus_id not in campus_ids:
            raise DatasetError("departamentos: referência a câmpus inexistente")
    for curso in snapshot.cursos:
        if curso.campus_id and curso.campus_id not in campus_ids:
            raise DatasetError("cursos: referência a câmpus inexistente")
        if curso.centro_sigla and curso.centro_sigla.casefold() not in centro_siglas:
            raise DatasetError("cursos: referência a centro inexistente")
        if curso.departamento_sigla:
            departamento = departamentos.get(curso.departamento_sigla.casefold())
            if departamento is None:
                raise DatasetError("cursos: referência a departamento inexistente")
            if (
                curso.centro_sigla
                and departamento.centro_sigla
                and curso.centro_sigla.casefold() != departamento.centro_sigla.casefold()
            ):
                raise DatasetError("cursos: centro e departamento incompatíveis")


def load_snapshot(data_dir: Path) -> Snapshot:
    """Read and validate all four files before exposing any records."""
    parsed = {}
    for dataset, model in DATASET_TYPES.items():
        path = data_dir / f"{dataset}.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            records = TypeAdapter(list[model]).validate_python(raw)
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
            raise DatasetError(f"{dataset}: arquivo ausente ou inválido") from exc
        if not records:
            raise DatasetError(f"{dataset}: dataset vazio")
        parsed[dataset] = tuple(records)
        _unique(parsed[dataset], "id", dataset)
        if dataset != "cursos":
            _unique(parsed[dataset], "sigla", dataset)

    snapshot = Snapshot(**parsed)
    _references_exist(snapshot)
    return snapshot
