"""Valida o catálogo de fontes antes de usar qualquer registro em revisão."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

SOURCE_ID = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
DATASETS = frozenset({"campi", "centros", "departamentos", "cursos"})
TYPES = frozenset({"html", "pdf", "json", "csv"})
ACCESS = frozenset({"public", "restricted"})
ROLES = frozenset({"primary", "secondary", "validation"})
STATUSES = frozenset({"candidate", "approved", "rejected"})
REUSE = frozenset({"verified", "not_verified"})
REQUIRED = (
    "dataset",
    "url",
    "type",
    "collector",
    "access",
    "role",
    "status",
    "last_verified",
    "review_interval_days",
    "reuse_conditions",
    "notes",
)


class SourceError(ValueError):
    """O catálogo de fontes está inválido."""


def _datasets(value: Any, source_id: str) -> list[str]:
    values = value if isinstance(value, list) else [value]
    if not values or any(not isinstance(item, str) or item not in DATASETS for item in values):
        raise SourceError(f"{source_id}: dataset inválido")
    if len(set(values)) != len(values):
        raise SourceError(f"{source_id}: dataset repetido")
    return values


def _url(value: Any, source_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceError(f"{source_id}: URL ausente")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.netloc:
        raise SourceError(f"{source_id}: URL precisa usar HTTPS na fonte")
    return value


def _date(value: Any, source_id: str) -> date:
    if not isinstance(value, str):
        raise SourceError(f"{source_id}: last_verified ausente")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise SourceError(f"{source_id}: last_verified precisa ser AAAA-MM-DD") from exc
    if parsed > date.today():
        raise SourceError(f"{source_id}: last_verified no futuro")
    return parsed


def _interval(value: Any, source_id: str) -> None:
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise SourceError(f"{source_id}: review_interval_days inválido")


def _text(value: Any, field: str, source_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceError(f"{source_id}: {field} ausente")
    return value


def validate_registry(raw: Any) -> dict[str, dict[str, Any]]:
    """Valida o documento carregado e devolve as fontes indexadas por source_id."""
    if not isinstance(raw, dict) or not isinstance(raw.get("sources"), dict):
        raise SourceError("catálogo deve conter a chave sources")
    sources = raw["sources"]
    if not sources:
        raise SourceError("catálogo sem fontes")
    validated = {}
    for source_id, entry in sources.items():
        if not isinstance(source_id, str) or not SOURCE_ID.fullmatch(source_id):
            raise SourceError(f"source_id inválido: {source_id!r}")
        if not isinstance(entry, dict):
            raise SourceError(f"{source_id}: entrada inválida")
        missing = [field for field in REQUIRED if field not in entry]
        if missing:
            raise SourceError(f"{source_id}: campos ausentes: {', '.join(missing)}")
        _datasets(entry["dataset"], source_id)
        _url(entry["url"], source_id)
        if entry["type"] not in TYPES:
            raise SourceError(f"{source_id}: type inválido")
        if entry["access"] not in ACCESS:
            raise SourceError(f"{source_id}: access inválido")
        if entry["role"] not in ROLES:
            raise SourceError(f"{source_id}: role inválido")
        if entry["status"] not in STATUSES:
            raise SourceError(f"{source_id}: status inválido")
        if entry["reuse_conditions"] not in REUSE:
            raise SourceError(f"{source_id}: reuse_conditions inválido")
        if entry["collector"] is not None:
            _text(entry["collector"], "collector", source_id)
        _date(entry["last_verified"], source_id)
        _interval(entry["review_interval_days"], source_id)
        _text(entry["notes"], "notes", source_id)
        validated[source_id] = entry
    return validated


def load_registry(path: Path) -> dict[str, dict[str, Any]]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SourceError(f"não foi possível ler o catálogo: {path}") from exc
    return validate_registry(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "sources" / "registry.yaml",
    )
    args = parser.parse_args(argv)
    try:
        sources = load_registry(args.registry)
    except SourceError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(f"ok: {len(sources)} fontes válidas em {args.registry.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
