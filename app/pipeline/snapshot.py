"""Construção determinística do snapshot a partir dos lotes revisados."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.pipeline.datasets import DATASETS, MODELS
from app.pipeline.io import read_json
from app.pipeline.normalizations import (
    NormalizationOutcome,
    apply_proposals,
    load_proposals,
)
from app.review.cursos import load_course_preview
from app.review.previews import fingerprint, load_preview
from app.services.repository import DatasetError, parse_snapshot

COURSE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SnapshotError(ValueError):
    """O snapshot não pode ser gerado com segurança a partir das entradas."""


@dataclass(frozen=True)
class DatasetInputs:
    previs: tuple[Path, ...]
    revisoes: tuple[Path, ...]


@dataclass(frozen=True)
class SnapshotManifest:
    path: Path
    normalizacoes: Path | None
    ids_cursos: Path
    inputs: dict[str, DatasetInputs]


@dataclass(frozen=True)
class BuiltSnapshot:
    datasets: dict[str, list[dict[str, Any]]]
    report: dict[str, Any]


@dataclass
class _PreviewSet:
    records: dict[str, dict[str, Any]]
    digests: dict[str, str]
    consultado_em: dict[str, datetime]


def _resolve_paths(base: Path, value: Any, label: str) -> tuple[Path, ...]:
    if not isinstance(value, list) or not value:
        raise SnapshotError(f"manifesto sem arquivos para {label}")
    paths = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise SnapshotError(f"caminho inválido no manifesto: {label}")
        path = (base / item).resolve()
        if not path.is_file():
            raise SnapshotError(f"arquivo do manifesto não encontrado: {item}")
        paths.append(path)
    if len(set(paths)) != len(paths):
        raise SnapshotError(f"arquivo repetido no manifesto: {label}")
    return tuple(paths)


def load_manifest(path: Path) -> SnapshotManifest:
    """Valida o manifesto que declara quais lotes revisados geram o snapshot."""
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("versao") != 1:
        raise SnapshotError("manifesto de snapshot inválido")
    entries = raw.get("datasets")
    if not isinstance(entries, dict) or set(entries) != set(DATASETS):
        raise SnapshotError("manifesto deve declarar exatamente os quatro datasets")
    base = path.resolve().parent
    inputs = {}
    for name in DATASETS:
        entry = entries[name]
        if not isinstance(entry, dict) or set(entry) != {"previs", "revisoes"}:
            raise SnapshotError(f"entrada inválida no manifesto: {name}")
        previs = _resolve_paths(base, entry["previs"], f"{name}.previs")
        revisoes = _resolve_paths(base, entry["revisoes"], f"{name}.revisoes")
        if len(previs) != len(revisoes):
            raise SnapshotError(f"prévias e revisões não pareadas: {name}")
        if name == "cursos" and len(previs) != 1:
            raise SnapshotError("cursos: o manifesto deve declarar exatamente um consolidado")
        inputs[name] = DatasetInputs(previs, revisoes)
    normalizacoes = raw.get("normalizacoes")
    if normalizacoes is not None:
        if not isinstance(normalizacoes, str) or not normalizacoes.strip():
            raise SnapshotError("caminho de normalizações inválido")
        normalizacoes_path = (base / normalizacoes).resolve()
        if not normalizacoes_path.is_file():
            raise SnapshotError(f"normalizações não encontradas: {normalizacoes}")
    else:
        normalizacoes_path = None
    ids_cursos = raw.get("ids_cursos")
    if not isinstance(ids_cursos, str) or not ids_cursos.strip():
        raise SnapshotError("manifesto sem mapeamento de IDs de cursos")
    ids_cursos_path = (base / ids_cursos).resolve()
    if not ids_cursos_path.is_file():
        raise SnapshotError(f"mapeamento de IDs de cursos não encontrado: {ids_cursos}")
    return SnapshotManifest(path.resolve(), normalizacoes_path, ids_cursos_path, inputs)


def _load_course_ids(path: Path) -> dict[str, str]:
    """Carrega o mapeamento persistente de IDs por câmpus e URL de detalhe."""
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("versao") != 1:
        raise SnapshotError("mapeamento de IDs de cursos inválido")
    entries = raw.get("cursos")
    if not isinstance(entries, list) or not entries:
        raise SnapshotError("mapeamento de IDs de cursos sem entradas")
    ids: dict[str, str] = {}
    values: set[str] = set()
    for item in entries:
        if not isinstance(item, dict) or set(item) != {"campus_id", "url_detalhe", "id"}:
            raise SnapshotError("entrada inválida no mapeamento de IDs de cursos")
        campus_id = item["campus_id"]
        url = item["url_detalhe"]
        value = item["id"]
        if not isinstance(campus_id, str) or not campus_id.strip():
            raise SnapshotError("câmpus inválido no mapeamento de IDs de cursos")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise SnapshotError("URL de detalhe inválida no mapeamento de IDs de cursos")
        if not isinstance(value, str) or not COURSE_ID.fullmatch(value):
            raise SnapshotError(f"ID de curso inválido no mapeamento: {value!r}")
        key = f"{campus_id}|{url}"
        if key in ids:
            raise SnapshotError(f"curso repetido no mapeamento de IDs: {key}")
        if value in values:
            raise SnapshotError(f"ID de curso repetido no mapeamento: {value}")
        ids[key] = value
        values.add(value)
    return ids


def _review_gate(path: Path, coverage: list[str]) -> None:
    raw = read_json(path)
    revisao = raw.get("revisao") if isinstance(raw, dict) else None
    if not isinstance(revisao, dict):
        raise SnapshotError(f"revisão inválida: {path.name}")
    if revisao.get("pendentes") != 0:
        raise SnapshotError(f"revisão com decisões pendentes: {path.name}")
    if revisao.get("decisoes_obsoletas"):
        raise SnapshotError(f"revisão com decisões desatualizadas: {path.name}")
    if int(revisao.get("aprovados", 0)) + int(revisao.get("rejeitados", 0)) == 0:
        raise SnapshotError(f"revisão sem decisões finais: {path.name}")
    coverage.extend(str(item) for item in revisao.get("inconsistencias_cobertura") or [])


def _load_previews(name: str, inputs: DatasetInputs, coverage: list[str]) -> _PreviewSet:
    records, digests, timestamps = {}, {}, {}
    for previa_path, revisao_path in zip(inputs.previs, inputs.revisoes, strict=True):
        _review_gate(revisao_path, coverage)
        preview = load_preview(previa_path, name)
        for key, record in preview.records.items():
            if key in records:
                raise SnapshotError(f"registro repetido em {name}: {key}")
            records[key] = record
            digests[key] = fingerprint(record, preview.provenance)
            timestamps[key] = preview.captured_at
    return _PreviewSet(records, digests, timestamps)


def _parse_time(value: Any, key: str) -> datetime:
    if not isinstance(value, str):
        raise SnapshotError(f"horário de captura inválido em {key}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SnapshotError(f"horário de captura inválido em {key}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SnapshotError(f"horário de captura sem fuso em {key}")
    return parsed


def _course_timestamps(raw: Any) -> dict[str, datetime]:
    if not isinstance(raw, dict) or not isinstance(raw.get("resultados"), list):
        raise SnapshotError("consolidado de cursos inválido")
    timestamps = {}
    for item in raw["resultados"]:
        if not isinstance(item, dict) or item.get("status") != "aceito":
            continue
        try:
            key = f"{item['campus_id']}|{item['url_detalhe']}"
            stamp = item["previa"]["fonte"]["consultado_em"]
        except (KeyError, TypeError) as exc:
            raise SnapshotError("resultado de curso sem origem completa") from exc
        timestamps[key] = _parse_time(stamp, key)
    return timestamps


def _load_cursos(inputs: DatasetInputs, coverage: list[str]) -> _PreviewSet:
    previa_path = inputs.previs[0]
    _review_gate(inputs.revisoes[0], coverage)
    raw = read_json(previa_path)
    preview = load_course_preview(previa_path)
    timestamps = _course_timestamps(raw)
    records, digests = {}, {}
    for key, record in preview.accepted.items():
        if key not in timestamps:
            raise SnapshotError(f"curso aceito sem horário de captura: {key}")
        records[key] = record
        digests[key] = fingerprint(
            record, {"lote": preview.provenance, "detalhe": preview.detail_provenance[key]}
        )
    return _PreviewSet(records, digests, timestamps)


def _course_grau(record: dict[str, Any], problems: list[dict[str, str]]) -> str | None:
    blocks = record.get("informacoes_academicas")
    if not isinstance(blocks, list) or not blocks:
        problems.append({"id": record["id_candidato"], "motivo": "sem blocos acadêmicos"})
        return None
    graus = {
        grau
        for block in blocks
        for grau in (block.get("graus_academicos") or [])
        if isinstance(grau, str) and grau
    }
    if len(blocks) == 1 and len(graus) == 1:
        return next(iter(graus))
    motivo = (
        "múltiplos blocos acadêmicos; grau não inferido"
        if len(blocks) > 1
        else "bloco único sem um único grau; grau não inferido"
    )
    problems.append({"id": record["id_candidato"], "motivo": motivo})
    return None


def _project(
    records: dict[str, dict[str, dict[str, Any]]],
    previews: dict[str, _PreviewSet],
    course_ids: dict[str, str],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    list[str],
    list[dict[str, str]],
    list[str],
]:
    ignored_fields: set[str] = set()
    grau_problems: list[dict[str, str]] = []
    datasets = {}
    for name in DATASETS:
        allowed = set(MODELS[name].model_fields)
        items = []
        for key, record in records[name].items():
            ignored_fields.update(
                field for field in record if field not in allowed and field != "fonte"
            )
            item = {field: value for field, value in record.items() if field in allowed}
            item["fonte"] = {
                **record["fonte"],
                "consultado_em": previews[name].consultado_em[key],
            }
            if name == "cursos":
                published_id = course_ids.get(key)
                if published_id is None:
                    raise SnapshotError(f"curso aceito sem ID estável no mapeamento: {key}")
                item["id"] = published_id
                item["nivel"] = "graduacao"
                item["grau"] = _course_grau(record, grau_problems)
                item["centro_sigla"] = None
                item["departamento_sigla"] = None
            items.append(item)
        items.sort(key=lambda entry: str(entry["id"]).casefold())
        datasets[name] = items
    unused_ids = sorted(set(course_ids) - set(records["cursos"]))
    return datasets, sorted(ignored_fields), grau_problems, unused_ids


def _validate(datasets: dict[str, list[dict[str, Any]]]) -> None:
    for name in DATASETS:
        try:
            TypeAdapter(list[MODELS[name]]).validate_python(datasets[name])
        except ValidationError as exc:
            raise SnapshotError(f"{name}: registros gerados são inválidos") from exc
    try:
        parse_snapshot(datasets)
    except DatasetError as exc:
        raise SnapshotError(f"snapshot inconsistente: {exc}") from exc


def _applied_report(outcome: NormalizationOutcome) -> tuple[list[dict], list[dict]]:
    aplicadas = [
        {
            "dataset": item.proposal.dataset,
            "id": item.proposal.id,
            "campo": item.campo_api,
            "valor_observado": item.proposal.valor_observado,
            "valor_proposto": item.proposal.valor_proposto,
        }
        for item in outcome.aplicadas
    ]
    ignoradas = [
        {
            "dataset": item.proposal.dataset,
            "id": item.proposal.id,
            "campo": item.proposal.campo,
            "motivo": item.motivo,
        }
        for item in outcome.ignoradas
    ]
    return aplicadas, ignoradas


def build_snapshot(manifest_path: Path) -> BuiltSnapshot:
    """Gera os quatro datasets somente a partir de lotes com decisões finais."""
    manifest = load_manifest(manifest_path)
    course_ids = _load_course_ids(manifest.ids_cursos)
    coverage: list[str] = []
    previews = {
        name: _load_previews(name, manifest.inputs[name], coverage)
        for name in ("campi", "centros", "departamentos")
    }
    previews["cursos"] = _load_cursos(manifest.inputs["cursos"], coverage)

    records = {name: previews[name].records for name in DATASETS}
    digests = {name: previews[name].digests for name in DATASETS}
    outcome = NormalizationOutcome((), ())
    if manifest.normalizacoes is not None:
        records, outcome = apply_proposals(load_proposals(manifest.normalizacoes), records, digests)

    datasets, ignored_fields, grau_problems, unused_ids = _project(records, previews, course_ids)
    _validate(datasets)
    aplicadas, ignoradas = _applied_report(outcome)
    report = {
        "publicavel": False,
        "manifesto": str(manifest.path),
        "normalizacoes": str(manifest.normalizacoes) if manifest.normalizacoes else None,
        "ids_cursos": str(manifest.ids_cursos),
        "ids_cursos_utilizados": len(course_ids) - len(unused_ids),
        "ids_cursos_nao_utilizados": unused_ids,
        "contagens": {name: len(datasets[name]) for name in DATASETS},
        "normalizacoes_aplicadas": aplicadas,
        "normalizacoes_ignoradas": ignoradas,
        "grau_nao_inferido": grau_problems,
        "campos_ignorados": ignored_fields,
        "inconsistencias_cobertura": sorted(set(coverage)),
    }
    return BuiltSnapshot(datasets, report)
