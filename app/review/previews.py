"""Compara prévias de câmpus e centros e registra decisões sobre candidatos."""

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import ValidationError

from app.collectors.campi import CAMPUS_SPECS
from app.collectors.campi import SOURCE_URL as CAMPUS_SOURCE_URL
from app.collectors.centros import EXPECTED_SIGLAS
from app.collectors.centros import SOURCE_URL as CENTER_SOURCE_URL
from app.schemas.campus import Campus
from app.schemas.centro import Centro

Dataset = Literal["campi", "centros"]
DecisionKey = tuple[str, str]
DATASETS = {
    "campi": (Campus, "campi_uem", CAMPUS_SOURCE_URL),
    "centros": (Centro, "centros_pld", CENTER_SOURCE_URL),
}
DECISIONS = frozenset({"pendente", "aprovado", "rejeitado"})


class PreviewReviewError(ValueError):
    """Uma prévia ou um manifesto não pode ser revisado com segurança."""


@dataclass(frozen=True)
class CandidatePreview:
    dataset: Dataset
    file: Path
    html_file: str
    captured_at: datetime
    provenance: dict[str, Any]
    records: dict[str, dict[str, Any]]


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise PreviewReviewError(f"não foi possível ler JSON válido: {path}") from exc


def load_preview(path: Path, dataset: Dataset) -> CandidatePreview:
    """Valida o formato da prévia e normaliza apenas os campos revisáveis."""
    raw = _read_json(path)
    if (
        not isinstance(raw, dict)
        or raw.get("modo") != "previa"
        or raw.get("publicavel") is not False
        or not isinstance(raw.get("entrada"), str)
        or not raw["entrada"].strip()
        or not isinstance(raw.get("proveniencia"), dict)
        or not isinstance(raw.get(dataset), list)
        or not raw[dataset]
    ):
        raise PreviewReviewError(f"prévia de {dataset} inválida: {path}")

    model, source_id, source_url = DATASETS[dataset]
    if dataset == "centros" and (
        type(raw.get("total")) is not int or raw["total"] != len(raw[dataset])
    ):
        raise PreviewReviewError("total de centros não corresponde aos registros")

    records: dict[str, dict[str, Any]] = {}
    siglas: set[str] = set()
    detail_urls: set[str] = set()
    timestamps: set[datetime] = set()
    for entry in raw[dataset]:
        if not isinstance(entry, dict):
            raise PreviewReviewError("registro de prévia inválido")
        candidate = dict(entry)
        detail_url = candidate.pop("url_pagina_vinculada", None) if dataset == "centros" else None
        try:
            record = model.model_validate(candidate)
        except ValidationError as exc:
            raise PreviewReviewError("registro de prévia não corresponde ao schema") from exc
        if record.fonte.source_id != source_id or str(record.fonte.url) != source_url:
            raise PreviewReviewError("fonte de registro incompatível com o dataset")
        if record.id in records:
            raise PreviewReviewError(f"ID duplicado na prévia: {record.id}")
        if record.sigla is not None:
            if record.sigla.casefold() in siglas:
                raise PreviewReviewError(f"sigla duplicada na prévia: {record.sigla}")
            siglas.add(record.sigla.casefold())
        if dataset == "centros":
            if not isinstance(detail_url, str):
                raise PreviewReviewError("link de centro ausente ou incompatível")
            try:
                parsed = urlsplit(detail_url)
            except ValueError as exc:
                raise PreviewReviewError("link de centro ausente ou incompatível") from exc
            prefix = f"{urlsplit(CENTER_SOURCE_URL).path}/"
            slug = parsed.path.removeprefix(prefix)
            if (
                parsed.scheme != "https"
                or parsed.netloc != "pld.uem.br"
                or not parsed.path.startswith(prefix)
                or not slug.startswith("centro-de-")
                or "/" in slug
                or parsed.query
                or parsed.fragment
            ):
                raise PreviewReviewError("link de centro ausente ou incompatível")
            if detail_url in detail_urls:
                raise PreviewReviewError("link de centro duplicado na prévia")
            detail_urls.add(detail_url)
        timestamps.add(record.fonte.consultado_em)
        normalized = record.model_dump(mode="json")
        normalized["fonte"].pop("consultado_em")
        if dataset == "centros":
            normalized["url_pagina_vinculada"] = detail_url
        records[record.id] = normalized
    if len(timestamps) != 1:
        raise PreviewReviewError("registros da prévia têm horários de captura divergentes")

    return CandidatePreview(
        dataset, path, raw["entrada"], timestamps.pop(), raw["proveniencia"], records
    )


def fingerprint(record: dict[str, Any], provenance: dict[str, Any]) -> str:
    """Vincula uma decisão aos valores, sem invalidá-la só pela hora da captura."""
    canonical = json.dumps(
        {"registro": record, "proveniencia": provenance},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_decision_time(value: Any) -> None:
    if not isinstance(value, str):
        raise PreviewReviewError("data_decisao deve ter data e hora com fuso")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PreviewReviewError("data_decisao deve estar em ISO 8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PreviewReviewError("data_decisao deve incluir fuso horário")


def load_decisions(path: Path, dataset: Dataset) -> dict[DecisionKey, dict[str, Any]]:
    raw = _read_json(path)
    if (
        not isinstance(raw, dict)
        or set(raw) != {"versao", "dataset", "decisoes"}
        or type(raw["versao"]) is not int
        or raw["versao"] != 1
        or raw["dataset"] != dataset
        or not isinstance(raw["decisoes"], list)
    ):
        raise PreviewReviewError("manifesto de decisões inválido")

    decisions: dict[DecisionKey, dict[str, Any]] = {}
    for entry in raw["decisoes"]:
        if not isinstance(entry, dict) or set(entry) != {
            "tipo",
            "id",
            "impressao",
            "decisao",
            "justificativa",
            "evidencias",
            "data_decisao",
        }:
            raise PreviewReviewError("entrada de decisão inválida")
        kind, record_id = entry["tipo"], entry["id"]
        if (
            not isinstance(kind, str)
            or kind not in {"registro", "remocao"}
            or not isinstance(record_id, str)
            or not record_id
        ):
            raise PreviewReviewError("tipo ou ID de decisão inválido")
        digest = entry["impressao"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise PreviewReviewError("impressão de decisão inválida")
        if not isinstance(entry["decisao"], str) or entry["decisao"] not in DECISIONS:
            raise PreviewReviewError("decisão desconhecida")
        if (
            not isinstance(entry["justificativa"], str)
            or not isinstance(entry["evidencias"], list)
            or any(not isinstance(item, str) or not item.strip() for item in entry["evidencias"])
        ):
            raise PreviewReviewError("justificativa ou evidências inválidas")
        if entry["decisao"] != "pendente":
            if not entry["justificativa"].strip() or not entry["evidencias"]:
                raise PreviewReviewError("decisão final exige justificativa e evidência")
            _parse_decision_time(entry["data_decisao"])
        elif entry["data_decisao"] is not None:
            _parse_decision_time(entry["data_decisao"])
        key = (kind, record_id)
        if key in decisions:
            raise PreviewReviewError(f"decisão duplicada: {kind}/{record_id}")
        decisions[key] = entry
    return decisions


def _changes(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for field in sorted(set(previous) | set(current)):
        before, after = previous.get(field), current.get(field)
        if isinstance(before, dict) and isinstance(after, dict):
            for child in sorted(set(before) | set(after)):
                if before.get(child) != after.get(child):
                    changed[f"{field}.{child}"] = {
                        "anterior": before.get(child),
                        "atual": after.get(child),
                    }
        elif before != after:
            changed[field] = {"anterior": before, "atual": after}
    return changed


def _coverage_issues(current: CandidatePreview) -> list[str]:
    if current.dataset == "campi":
        expected = {spec.id for spec in CAMPUS_SPECS}
        observed = set(current.records)
    else:
        expected = EXPECTED_SIGLAS
        observed = {record["sigla"] for record in current.records.values()}
    issues = []
    if expected - observed:
        issues.append(f"ausentes: {sorted(expected - observed)}")
    if observed - expected:
        issues.append(f"inesperados: {sorted(observed - expected)}")
    return issues


def build_review(
    current: CandidatePreview,
    previous: CandidatePreview | None = None,
    decisions: dict[DecisionKey, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Mostra diffs e decisões válidas sem converter prévias em dados publicados."""
    if previous is not None:
        if previous.dataset != current.dataset:
            raise PreviewReviewError("prévia anterior pertence a outro dataset")
        if previous.captured_at > current.captured_at:
            raise PreviewReviewError("prévia anterior é mais recente que a atual")
    decisions = decisions or {}
    old = previous.records if previous else {}
    new = current.records
    added = sorted(new.keys() - old.keys())
    removed = sorted(old.keys() - new.keys())
    modified = sorted(key for key in new.keys() & old.keys() if new[key] != old[key])
    changes = (
        [{"id": key, "tipo": "adicionado", "atual": new[key]} for key in added]
        + [{"id": key, "tipo": "removido", "anterior": old[key]} for key in removed]
        + [
            {"id": key, "tipo": "alterado", "campos": _changes(old[key], new[key])}
            for key in modified
        ]
    )

    review_items = []
    template = []
    used_keys: set[DecisionKey] = set()
    for kind, record_id, record in [
        *(("registro", key, new[key]) for key in sorted(new)),
        *(("remocao", key, old[key]) for key in removed),
    ]:
        key = (kind, record_id)
        used_keys.add(key)
        provenance = current.provenance if kind == "registro" else previous.provenance
        digest = fingerprint(record, provenance)
        decision = decisions.get(key)
        if decision is None:
            status = "sem_decisao"
        elif decision["impressao"] != digest:
            status = "decisao_desatualizada"
        else:
            status = decision["decisao"]
        item = {"tipo": kind, "id": record_id, "impressao": digest, "status": status}
        if decision is not None and decision["impressao"] == digest:
            item.update(
                justificativa=decision["justificativa"],
                evidencias=decision["evidencias"],
                data_decisao=decision["data_decisao"],
            )
        review_items.append(item)
        template.append(
            {
                "tipo": kind,
                "id": record_id,
                "impressao": digest,
                "decisao": "pendente",
                "justificativa": "",
                "evidencias": [],
                "data_decisao": None,
            }
        )
    obsolete = sorted(
        ({"tipo": kind, "id": record_id} for kind, record_id in decisions.keys() - used_keys),
        key=lambda item: (item["tipo"], item["id"]),
    )
    issues = _coverage_issues(current)
    return {
        "modo": "revisao",
        "publicavel": False,
        "dataset": current.dataset,
        "entradas": {
            "atual": str(current.file),
            "html_atual": current.html_file,
            "consultado_em_atual": current.captured_at.isoformat(),
            "anterior": str(previous.file) if previous else None,
            "html_anterior": previous.html_file if previous else None,
            "consultado_em_anterior": previous.captured_at.isoformat() if previous else None,
        },
        "comparacao": {
            "status": (
                "sem_captura_anterior"
                if previous is None
                else "revisar"
                if changes or previous.provenance != current.provenance
                else "sem_alteracoes"
            ),
            "adicionados": len(added),
            "removidos": len(removed),
            "alterados": len(modified),
            "inalterados": len(new) - len(added) - len(modified) if previous else 0,
            "mudancas": changes,
            "proveniencia_alterada": previous is not None
            and previous.provenance != current.provenance,
        },
        "revisao": {
            "registros": review_items,
            "pendentes": sum(
                item["status"] in {"sem_decisao", "pendente", "decisao_desatualizada"}
                for item in review_items
            ),
            "rejeitados": sum(item["status"] == "rejeitado" for item in review_items),
            "aprovados": sum(item["status"] == "aprovado" for item in review_items),
            "decisoes_obsoletas": obsolete,
            "inconsistencias_cobertura": issues,
            "todos_itens_aprovados": bool(review_items)
            and all(item["status"] == "aprovado" for item in review_items)
            and not obsolete
            and not issues,
        },
        "modelo_decisoes": {"versao": 1, "dataset": current.dataset, "decisoes": template},
        "proveniencia": {
            "atual": current.provenance,
            "anterior": previous.provenance if previous else None,
        },
        "limites": [
            "a origem dos arquivos HTML e JSON locais não é autenticada",
            "decisões registradas não aprovam condições de reutilização das fontes",
            "a revisão não gera arquivos em data/ nem autoriza publicação",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Revisa prévias locais de câmpus ou centros")
    parser.add_argument("--dataset", required=True, choices=DATASETS)
    parser.add_argument("--atual", required=True, type=Path, help="JSON da prévia atual")
    parser.add_argument("--anterior", type=Path, help="JSON da prévia anterior")
    parser.add_argument("--decisoes", type=Path, help="manifesto de decisões já registradas")
    parser.add_argument(
        "--modelo-decisoes", type=Path, help="cria um modelo de manifesto sem sobrescrever arquivos"
    )
    args = parser.parse_args()
    try:
        current = load_preview(args.atual, args.dataset)
        previous = load_preview(args.anterior, args.dataset) if args.anterior else None
        decisions = load_decisions(args.decisoes, args.dataset) if args.decisoes else None
        report = build_review(current, previous, decisions)
        if args.modelo_decisoes:
            with args.modelo_decisoes.open("x", encoding="utf-8") as output:
                json.dump(report["modelo_decisoes"], output, ensure_ascii=False, indent=2)
                output.write("\n")
    except (OSError, PreviewReviewError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
