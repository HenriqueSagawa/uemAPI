"""Leitura, serialização determinística e escrita atômica do snapshot."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from app.pipeline.datasets import DATASETS, MODELS
from app.services.repository import parse_snapshot


def read_json(path: Path) -> Any:
    """Lê um JSON com mensagem de erro curta, sem expor o conteúdo do arquivo."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"não foi possível ler JSON: {path}") from exc


def dump_dataset(dataset: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Valida e converte o dataset para valores JSON, na ordem do schema."""
    adapter = TypeAdapter(list[MODELS[dataset]])
    return adapter.dump_python(adapter.validate_python(records), mode="json")


def serialize_dataset(dataset: str, records: list[dict[str, Any]]) -> str:
    """Serializa um dataset na ordem do schema e com IDs ordenados."""
    payload = dump_dataset(dataset, records)
    payload.sort(key=lambda item: str(item["id"]).casefold())
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def serialize_snapshot(datasets: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    return {f"{name}.json": serialize_dataset(name, datasets[name]) for name in DATASETS}


def read_snapshot(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Lê os quatro arquivos sem validar; usado apenas para comparar snapshots."""
    return {name: read_json(data_dir / f"{name}.json") for name in DATASETS}


def write_snapshot(datasets: dict[str, list[dict[str, Any]]], data_dir: Path) -> None:
    """Valida o conteúdo final e só então substitui os quatro arquivos."""
    texts = serialize_snapshot(datasets)
    parse_snapshot({name: json.loads(texts[f"{name}.json"]) for name in DATASETS})
    data_dir.mkdir(parents=True, exist_ok=True)
    staging = data_dir / f".snapshot-{os.getpid()}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    try:
        for filename, text in texts.items():
            (staging / filename).write_text(text, encoding="utf-8")
        for filename in texts:
            os.replace(staging / filename, data_dir / filename)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
