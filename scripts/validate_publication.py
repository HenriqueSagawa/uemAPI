"""Valida o snapshot, as fontes e a aprovação antes de publicar a API."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline import (  # noqa: E402
    DATASETS,
    SnapshotError,
    build_snapshot,
    serialize_snapshot,
)
from app.pipeline.io import read_json  # noqa: E402
from app.services.repository import DatasetError, Snapshot, load_snapshot  # noqa: E402
from scripts.validate_sources import SourceError, load_registry  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
APPROVAL_KEYS = {
    "versao",
    "publicacao",
    "aprovado_por",
    "data_aprovacao",
    "escopo",
    "snapshot_consultado_em",
    "contagens",
    "fontes",
    "limitacoes",
}


class PublicationError(ValueError):
    """A aprovação de publicação está incompleta ou inconsistente."""


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicationError(f"{field} ausente na aprovação")
    return value


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise PublicationError("snapshot_consultado_em inválido na aprovação")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PublicationError("snapshot_consultado_em inválido na aprovação") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PublicationError("snapshot_consultado_em sem fuso na aprovação")
    return parsed


def _date(value: Any) -> date:
    if not isinstance(value, str):
        raise PublicationError("data_aprovacao ausente na aprovação")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise PublicationError("data_aprovacao precisa ser AAAA-MM-DD") from exc


def load_approval(path: Path) -> dict[str, Any]:
    """Carrega o registro estruturado que autoriza esta publicação."""
    try:
        raw = read_json(path)
    except ValueError as exc:
        raise PublicationError(f"não foi possível ler a aprovação: {path}") from exc
    if not isinstance(raw, dict) or set(raw) != APPROVAL_KEYS:
        raise PublicationError("registro de aprovação inválido")
    if raw.get("versao") != 1:
        raise PublicationError("versão do registro de aprovação inválida")
    for field in ("publicacao", "aprovado_por", "escopo"):
        _text(raw.get(field), field)
    _date(raw.get("data_aprovacao"))
    _time(raw.get("snapshot_consultado_em"))
    counts = raw.get("contagens")
    if (
        not isinstance(counts, dict)
        or set(counts) != set(DATASETS)
        or any(not isinstance(counts[name], int) or counts[name] < 1 for name in DATASETS)
    ):
        raise PublicationError("contagens inválidas na aprovação")
    fontes = raw.get("fontes")
    if (
        not isinstance(fontes, list)
        or not fontes
        or any(not isinstance(item, str) or not item.strip() for item in fontes)
        or len(set(fontes)) != len(fontes)
    ):
        raise PublicationError("lista de fontes inválida na aprovação")
    limitacoes = raw.get("limitacoes")
    if (
        not isinstance(limitacoes, list)
        or not limitacoes
        or any(not isinstance(item, str) or not item.strip() for item in limitacoes)
    ):
        raise PublicationError("lista de limitações inválida na aprovação")
    return raw


def _used_sources(snapshot: Snapshot) -> list[str]:
    return sorted(
        {record.fonte.source_id for name in DATASETS for record in snapshot.records(name)}
    )


def _check_sources(
    snapshot: Snapshot,
    registry: dict[str, dict[str, Any]],
    today: date,
) -> list[str]:
    used = _used_sources(snapshot)
    problems = []
    for source_id in used:
        entry = registry.get(source_id)
        if entry is None:
            problems.append(f"fonte usada fora do catálogo: {source_id}")
            continue
        if entry["status"] != "approved":
            problems.append(f"fonte sem status approved: {source_id}")
        if entry["reuse_conditions"] != "verified":
            problems.append(f"fonte sem reutilização verificada: {source_id}")
        interval = entry["review_interval_days"]
        if not isinstance(interval, int) or isinstance(interval, bool) or interval < 1:
            problems.append(f"fonte sem intervalo de revisão: {source_id}")
        else:
            last_verified = date.fromisoformat(entry["last_verified"])
            if last_verified + timedelta(days=interval) < today:
                problems.append(f"fonte com revisão vencida: {source_id}")
    for name in DATASETS:
        expected = {record.fonte.source_id for record in snapshot.records(name)}
        for source_id in expected:
            entry = registry.get(source_id)
            if entry is not None and name not in entry["dataset"]:
                problems.append(f"fonte {source_id} não declara o dataset {name}")
    return problems


def _check_approval(
    approval: dict[str, Any],
    snapshot: Snapshot,
    used_sources: list[str],
    today: date,
) -> list[str]:
    problems = []
    approved_at = _date(approval["data_aprovacao"])
    if approved_at > today:
        problems.append("data_aprovacao no futuro")
    if approved_at < snapshot.consultado_em.date():
        problems.append("aprovação anterior à captura mais recente do snapshot")
    if _time(approval["snapshot_consultado_em"]) != snapshot.consultado_em:
        problems.append("snapshot_consultado_em diverge do snapshot publicado")
    if approval["contagens"] != snapshot.counts:
        problems.append("contagens da aprovação divergem do snapshot publicado")
    if sorted(approval["fontes"]) != used_sources:
        problems.append("fontes da aprovação divergem das fontes usadas no snapshot")
    return problems


def validate_publication(
    data_dir: Path,
    manifest_path: Path,
    registry_path: Path,
    approval_path: Path,
    today: date | None = None,
) -> dict[str, Any]:
    """Confere se o snapshot publicado corresponde às entradas e à aprovação."""
    today = today or date.today()
    snapshot = load_snapshot(data_dir)
    built = build_snapshot(manifest_path)
    texts = serialize_snapshot(built.datasets)
    drift = []
    for name in DATASETS:
        filename = f"{name}.json"
        try:
            current = (data_dir / filename).read_text(encoding="utf-8")
        except OSError:
            drift.append(f"ausente: {filename}")
            continue
        if current != texts[filename]:
            drift.append(f"divergente: {filename}")
    approval = load_approval(approval_path)
    registry = load_registry(registry_path)
    used_sources = _used_sources(snapshot)
    problems = [
        *[f"data/{item}" for item in drift],
        *_check_sources(snapshot, registry, today),
        *_check_approval(approval, snapshot, used_sources, today),
    ]
    if problems:
        raise PublicationError("; ".join(problems))
    return {
        "publicavel": True,
        "publicacao": approval["publicacao"],
        "aprovado_por": approval["aprovado_por"],
        "data_aprovacao": approval["data_aprovacao"],
        "data_dir": str(data_dir),
        "contagens": snapshot.counts,
        "snapshot_consultado_em": snapshot.consultado_em.isoformat(),
        "fontes": used_sources,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--manifest", type=Path, default=ROOT / "reviews" / "snapshot-inputs.json")
    parser.add_argument("--registry", type=Path, default=ROOT / "sources" / "registry.yaml")
    parser.add_argument(
        "--approval",
        type=Path,
        default=ROOT / "reviews" / "2026-11-20-publicacao" / "aprovacao.json",
    )
    args = parser.parse_args(argv)
    try:
        report = validate_publication(
            args.data_dir,
            args.manifest,
            args.registry,
            args.approval,
        )
    except (PublicationError, DatasetError, SnapshotError, SourceError, ValueError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
