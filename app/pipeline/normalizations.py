"""Verificação e aplicação das propostas de normalização registradas na revisão."""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.pipeline.datasets import DATASETS, MODELS
from app.pipeline.io import read_json

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED = ("dataset", "id", "campo", "valor_observado", "valor_proposto", "impressao_base")


class NormalizationError(ValueError):
    """Uma proposta não pode ser verificada ou aplicada com segurança."""


@dataclass(frozen=True)
class Proposal:
    dataset: str
    id: str
    campo: str
    valor_observado: Any
    valor_proposto: Any
    impressao_base: str


@dataclass(frozen=True)
class AppliedProposal:
    proposal: Proposal
    campo_api: str


@dataclass(frozen=True)
class SkippedProposal:
    proposal: Proposal
    motivo: str


@dataclass(frozen=True)
class NormalizationOutcome:
    aplicadas: tuple[AppliedProposal, ...]
    ignoradas: tuple[SkippedProposal, ...]


def load_proposals(path: Path) -> tuple[Proposal, ...]:
    """Lê o manifesto de propostas e valida a estrutura declarativa."""
    raw = read_json(path)
    if not isinstance(raw, dict) or raw.get("versao") != 1:
        raise NormalizationError("documento de normalizações inválido")
    entries = raw.get("propostas")
    if not isinstance(entries, list) or not entries:
        raise NormalizationError("documento de normalizações sem propostas")
    proposals = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or any(field not in entry for field in _REQUIRED):
            raise NormalizationError("proposta de normalização inválida")
        dataset, record_id, campo = entry["dataset"], entry["id"], entry["campo"]
        digest = entry["impressao_base"]
        if dataset not in DATASETS:
            raise NormalizationError(f"dataset desconhecido na proposta: {dataset!r}")
        if not isinstance(record_id, str) or not record_id.strip():
            raise NormalizationError("proposta sem ID de registro")
        if not isinstance(campo, str) or not campo.startswith("/"):
            raise NormalizationError("proposta sem caminho de campo")
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise NormalizationError(f"impressão base inválida: {record_id}")
        if entry["valor_observado"] == entry["valor_proposto"]:
            raise NormalizationError(f"proposta sem alteração efetiva: {record_id}")
        key = (dataset, record_id, campo)
        if key in seen:
            raise NormalizationError(f"proposta duplicada: {record_id} {campo}")
        seen.add(key)
        proposals.append(
            Proposal(
                dataset=dataset,
                id=record_id,
                campo=campo,
                valor_observado=entry["valor_observado"],
                valor_proposto=entry["valor_proposto"],
                impressao_base=digest,
            )
        )
    return tuple(proposals)


def _resolve(record: dict[str, Any], campo: str) -> Any:
    current: Any = record
    for part in campo.lstrip("/").split("/"):
        try:
            if isinstance(current, list):
                current = current[int(part)]
            elif isinstance(current, dict):
                current = current[part]
            else:
                raise KeyError(part)
        except (KeyError, IndexError, ValueError) as exc:
            raise NormalizationError(f"campo não encontrado na base: {campo}") from exc
    return current


def _api_field(proposal: Proposal) -> str | None:
    parts = proposal.campo.lstrip("/").split("/")
    if len(parts) != 1:
        return None
    if parts[0] in MODELS[proposal.dataset].model_fields:
        return parts[0]
    return None


def apply_proposals(
    proposals: tuple[Proposal, ...],
    records: Mapping[str, Mapping[str, dict[str, Any]]],
    digests: Mapping[str, Mapping[str, str]],
) -> tuple[dict[str, dict[str, dict[str, Any]]], NormalizationOutcome]:
    """Confere impressão, valor observado e escopo antes de alterar o registro."""
    updated = {
        dataset: {key: copy.deepcopy(record) for key, record in items.items()}
        for dataset, items in records.items()
    }
    applied = []
    skipped = []
    for proposal in proposals:
        dataset_records = updated.get(proposal.dataset)
        dataset_digests = digests.get(proposal.dataset)
        if dataset_records is None or dataset_digests is None:
            raise NormalizationError(f"dataset ausente para a proposta: {proposal.dataset}")
        if proposal.id not in dataset_records or proposal.id not in dataset_digests:
            raise NormalizationError(
                f"{proposal.dataset}: registro da proposta não encontrado: {proposal.id}"
            )
        if dataset_digests[proposal.id] != proposal.impressao_base:
            raise NormalizationError(
                f"{proposal.dataset}: impressão base divergente para {proposal.id}"
            )
        record = dataset_records[proposal.id]
        if _resolve(record, proposal.campo) != proposal.valor_observado:
            raise NormalizationError(
                f"{proposal.dataset}: valor observado divergente em {proposal.id}"
            )
        field = _api_field(proposal)
        if field is None:
            skipped.append(
                SkippedProposal(proposal, "campo não pertence ao modelo canônico da v0.1")
            )
            continue
        record[field] = copy.deepcopy(proposal.valor_proposto)
        applied.append(AppliedProposal(proposal, field))
    return updated, NormalizationOutcome(tuple(applied), tuple(skipped))
