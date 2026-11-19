"""Comparação determinística entre snapshots."""

from __future__ import annotations

import json
from typing import Any

from app.pipeline.datasets import DATASETS
from app.pipeline.io import dump_dataset


def _canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _changed_fields(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    return sorted(key for key in set(old) | set(new) if old.get(key) != new.get(key))


def diff_snapshot(
    previous: dict[str, list[dict[str, Any]]] | None,
    current: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Resume registros criados, removidos e alterados, sem emitir os dados."""
    report: dict[str, Any] = {"snapshot_anterior": previous is not None, "datasets": {}}
    for name in DATASETS:
        new = {item["id"]: item for item in dump_dataset(name, current[name])}
        if previous is None:
            criados, removidos, alterados = sorted(new), [], []
        else:
            old = {item["id"]: item for item in previous.get(name, [])}
            criados, removidos = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
            alterados = [
                {"id": key, "campos": _changed_fields(old[key], new[key])}
                for key in sorted(old.keys() & new.keys())
                if _canonical(old[key]) != _canonical(new[key])
            ]
        report["datasets"][name] = {
            "criados": criados,
            "removidos": removidos,
            "alterados": alterados,
            "total": {
                "criados": len(criados),
                "removidos": len(removidos),
                "alterados": len(alterados),
            },
        }
    return report
