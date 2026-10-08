"""Revisa prévias consolidadas de cursos da PEN sem publicar registros."""

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from os.path import normpath
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.collectors.curso_detalhes import candidate_id
from app.collectors.cursos import (
    DETAIL_URL,
    EXPECTED_CAMPUS_IDS,
    NEAD_URL,
    SOURCE_URL,
    CourseCandidate,
)
from app.review.previews import (
    DecisionKey,
    PreviewReviewError,
    diff_fields,
    fingerprint,
    load_decisions,
    read_json,
)
from app.schemas.common import Fonte

STATUSES = frozenset({"aceito", "sem_captura", "arquivo_ausente", "falha_leitura", "invalido"})
BASE_FIELDS = {"campus_id", "nome", "url_detalhe", "status"}


@dataclass(frozen=True)
class CoursePreview:
    file: Path
    index_file: str
    manifest_file: str
    captured_at: datetime
    provenance: dict[str, Any]
    entries: dict[str, dict[str, Any]]
    accepted: dict[str, dict[str, Any]]
    detail_provenance: dict[str, dict[str, Any]]
    coverage_issues: list[str]


def _object(value: Any, fields: set[str], message: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise PreviewReviewError(message)
    return value


def _text(value: Any, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PreviewReviewError(message)
    return value


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise PreviewReviewError("horário de captura de curso inválido")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PreviewReviewError("horário de captura de curso inválido") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PreviewReviewError("horário de captura de curso sem fuso")
    return parsed


def _capture_file(value: Any, message: str) -> str:
    return normpath(_text(value, message))


def _source(value: Any, expected_url: str) -> Fonte:
    try:
        source = Fonte.model_validate(value)
    except ValidationError as exc:
        raise PreviewReviewError("fonte da prévia de cursos inválida") from exc
    if source.source_id != "cursos_graduacao" or str(source.url) != expected_url:
        raise PreviewReviewError("fonte da prévia de cursos incompatível")
    return source


def _key(campus_id: str, url: str) -> str:
    """Chave da revisão; não é o ID publicado pela API."""
    return f"{campus_id}|{url}"


def _academic_blocks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise PreviewReviewError("blocos acadêmicos do curso inválidos")
    for block in value:
        _object(block, {"turno", "habilitacoes", "graus_academicos"}, "bloco acadêmico inválido")
        if block["turno"] is not None and (
            not isinstance(block["turno"], str) or not block["turno"].strip()
        ):
            raise PreviewReviewError("turno acadêmico inválido")
        for field in ("habilitacoes", "graus_academicos"):
            if not isinstance(block[field], list) or any(
                not isinstance(item, str) or not item.strip() for item in block[field]
            ):
                raise PreviewReviewError("valor acadêmico inválido")
        values = [block["turno"], *block["habilitacoes"], *block["graus_academicos"]]
        if not any(values) or any("@" in value for value in values if value):
            raise PreviewReviewError("bloco acadêmico vazio ou com contato")
    return value


def _accepted_detail(
    detail: Any, result: dict[str, Any], index_file: str, captured_at: datetime
) -> tuple[dict[str, Any], dict[str, Any]]:
    detail = _object(
        detail,
        {"modo", "publicavel", "entrada", "fonte", "curso", "proveniencia"},
        "prévia de detalhe inválida",
    )
    if detail["modo"] != "previa" or detail["publicavel"] is not False:
        raise PreviewReviewError("prévia de detalhe inválida")
    location = _object(detail["entrada"], {"indice", "detalhe"}, "entrada de detalhe inválida")
    if location != {"indice": index_file, "detalhe": result["arquivo"]}:
        raise PreviewReviewError("arquivo de detalhe incompatível com o lote")
    source = _source(detail["fonte"], result["url_detalhe"])
    if source.consultado_em != captured_at:
        raise PreviewReviewError("horário do detalhe incompatível com o lote")
    course = _object(
        detail["curso"],
        {
            "nome",
            "campus_id",
            "modalidade",
            "url_detalhe",
            "id_candidato",
            "informacoes_academicas",
        },
        "registro de curso inválido",
    )
    for field in ("nome", "campus_id", "url_detalhe"):
        if course[field] != result[field]:
            raise PreviewReviewError("detalhe não corresponde à entrada do índice")
    if course["modalidade"] != "presencial":
        raise PreviewReviewError("modalidade de curso inesperada")
    try:
        expected_id = candidate_id(
            CourseCandidate(
                course["nome"], course["campus_id"], "presencial", course["url_detalhe"]
            )
        )
    except ValueError as exc:
        raise PreviewReviewError("ID candidato do curso inválido") from exc
    if course["id_candidato"] != expected_id:
        raise PreviewReviewError("ID candidato do curso incompatível")
    _academic_blocks(course["informacoes_academicas"])
    if not isinstance(detail["proveniencia"], dict) or not detail["proveniencia"]:
        raise PreviewReviewError("proveniência de detalhe inválida")
    return (
        {
            **course,
            "fonte": {"source_id": source.source_id, "url": str(source.url)},
        },
        detail["proveniencia"],
    )


def _summary(results: dict[str, dict[str, Any]], extras: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = Counter(entry["status"] for entry in results.values())
    by_campus: dict[str, Counter] = {}
    for entry in results.values():
        by_campus.setdefault(entry["campus_id"], Counter())[entry["status"]] += 1
    return {
        "total_indice": len(results),
        "total_manifesto": len(results) - statuses["sem_captura"] + len(extras),
        "aceitos": statuses["aceito"],
        "sem_captura": statuses["sem_captura"],
        "arquivo_ausente": statuses["arquivo_ausente"],
        "falha_leitura": statuses["falha_leitura"],
        "invalidos": statuses["invalido"],
        "fora_do_indice": len(extras),
        "cobertura_completa": statuses["aceito"] == len(results) and not extras,
        "por_campus": {
            campus: {
                "total": sum(counts.values()),
                "aceitos": counts["aceito"],
                "sem_captura": counts["sem_captura"],
                "arquivo_ausente": counts["arquivo_ausente"],
                "falha_leitura": counts["falha_leitura"],
                "invalidos": counts["invalido"],
            }
            for campus, counts in sorted(by_campus.items())
        },
    }


def load_course_preview(path: Path) -> CoursePreview:
    """Confere o lote e seus detalhes antes de criar decisões revisáveis."""
    raw = _object(
        read_json(path),
        {
            "modo",
            "publicavel",
            "entrada",
            "fonte_indice",
            "ead",
            "resumo",
            "resultados",
            "fora_do_indice",
            "proveniencia",
        },
        "prévia consolidada de cursos inválida",
    )
    if raw["modo"] != "previa" or raw["publicavel"] is not False:
        raise PreviewReviewError("prévia consolidada de cursos inválida")
    location = _object(raw["entrada"], {"indice", "manifesto"}, "entrada do lote inválida")
    index_file = _text(location["indice"], "arquivo do índice inválido")
    manifest_file = _text(location["manifesto"], "arquivo do manifesto inválido")
    index_source = _source(raw["fonte_indice"], SOURCE_URL)
    ead = _object(raw["ead"], {"url", "cursos_incluidos"}, "cobertura EaD inválida")
    if (
        not isinstance(ead["url"], str)
        or not NEAD_URL.fullmatch(ead["url"])
        or ead["cursos_incluidos"] is not False
    ):
        raise PreviewReviewError("cobertura EaD inválida")
    if not isinstance(raw["proveniencia"], dict) or not raw["proveniencia"]:
        raise PreviewReviewError("proveniência do lote inválida")
    if not isinstance(raw["resultados"], list) or not raw["resultados"]:
        raise PreviewReviewError("resultados do lote inválidos")
    if not isinstance(raw["fora_do_indice"], list):
        raise PreviewReviewError("capturas fora do índice inválidas")

    entries: dict[str, dict[str, Any]] = {}
    accepted: dict[str, dict[str, Any]] = {}
    detail_provenance: dict[str, dict[str, Any]] = {}
    coverage_issues = ["cursos da EaD não incluídos"]
    candidate_ids: set[str] = set()
    capture_files: set[str] = set()
    for result in raw["resultados"]:
        if not isinstance(result, dict) or not BASE_FIELDS <= set(result):
            raise PreviewReviewError("entrada de curso inválida")
        campus = _text(result["campus_id"], "câmpus de curso inválido")
        name = _text(result["nome"], "nome de curso inválido")
        url = _text(result["url_detalhe"], "URL de curso inválida")
        status = result["status"]
        if campus not in EXPECTED_CAMPUS_IDS or not DETAIL_URL.fullmatch(url):
            raise PreviewReviewError("câmpus ou URL de curso inesperado")
        if not isinstance(status, str) or status not in STATUSES:
            raise PreviewReviewError("status de curso inválido")
        expected_fields = BASE_FIELDS.copy()
        if status != "sem_captura":
            expected_fields |= {"arquivo", "consultado_em"}
        if status == "invalido":
            expected_fields.add("motivo")
        if status == "aceito":
            expected_fields.add("previa")
        if set(result) != expected_fields:
            raise PreviewReviewError("campos de entrada de curso inválidos")
        key = _key(campus, url)
        if key in entries:
            raise PreviewReviewError("curso duplicado no índice")
        try:
            expected_id = candidate_id(CourseCandidate(name, campus, "presencial", url))
        except ValueError as exc:
            raise PreviewReviewError("ID candidato do curso inválido") from exc
        if expected_id in candidate_ids:
            raise PreviewReviewError("IDs candidatos de cursos duplicados")
        candidate_ids.add(expected_id)
        entry: dict[str, Any] = {
            "campus_id": campus,
            "nome": name,
            "url_detalhe": url,
            "status": status,
        }
        if status != "sem_captura":
            file_path = _capture_file(result["arquivo"], "arquivo de detalhe inválido")
            if file_path in capture_files:
                raise PreviewReviewError("arquivo de detalhe reutilizado no lote")
            capture_files.add(file_path)
            captured_at = _time(result["consultado_em"])
            if status == "invalido":
                _text(result["motivo"], "motivo de detalhe inválido")
            if status == "aceito":
                record, provenance = _accepted_detail(
                    result["previa"], result, index_file, captured_at
                )
                entry["curso"] = record
                entry["proveniencia_detalhe"] = provenance
                accepted[key] = record
                detail_provenance[key] = provenance
            else:
                coverage_issues.append(f"{status}: {key}")
        else:
            coverage_issues.append(f"sem_captura: {key}")
        entries[key] = entry

    if {entry["campus_id"] for entry in entries.values()} != EXPECTED_CAMPUS_IDS:
        raise PreviewReviewError("seções de câmpus do índice incompletas")

    extras: list[dict[str, Any]] = []
    extra_keys: set[str] = set()
    for item in raw["fora_do_indice"]:
        extra = _object(
            item,
            {"campus_id", "url_detalhe", "arquivo", "consultado_em", "status"},
            "captura fora do índice inválida",
        )
        campus = _text(extra["campus_id"], "câmpus fora do índice inválido")
        url = _text(extra["url_detalhe"], "URL fora do índice inválida")
        file_path = _capture_file(extra["arquivo"], "arquivo fora do índice inválido")
        _time(extra["consultado_em"])
        key = _key(campus, url)
        if (
            campus not in EXPECTED_CAMPUS_IDS
            or not DETAIL_URL.fullmatch(url)
            or extra["status"] != "fora_do_indice"
            or key in entries
            or key in extra_keys
            or file_path in capture_files
        ):
            raise PreviewReviewError("captura fora do índice incompatível ou duplicada")
        extras.append(extra)
        extra_keys.add(key)
        capture_files.add(file_path)
        coverage_issues.append(f"fora_do_indice: {key}")
    if json.dumps(raw["resumo"], sort_keys=True) != json.dumps(
        _summary(entries, extras), sort_keys=True
    ):
        raise PreviewReviewError("resumo de cobertura de cursos inconsistente")
    provenance = {
        **raw["proveniencia"],
        "fonte_indice": {"source_id": index_source.source_id, "url": str(index_source.url)},
        "ead": ead,
    }
    return CoursePreview(
        path,
        index_file,
        manifest_file,
        index_source.consultado_em,
        provenance,
        entries,
        accepted,
        detail_provenance,
        sorted(coverage_issues),
    )


def build_course_review(
    current: CoursePreview,
    previous: CoursePreview | None = None,
    decisions: dict[DecisionKey, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compara o índice completo e só admite decisões sobre detalhes aceitos."""
    if previous is not None and previous.captured_at > current.captured_at:
        raise PreviewReviewError("prévia anterior é mais recente que a atual")
    decisions = decisions or {}
    old = previous.entries if previous else {}
    new = current.entries
    added = sorted(new.keys() - old.keys())
    removed = sorted(old.keys() - new.keys())
    modified = sorted(key for key in new.keys() & old.keys() if new[key] != old[key])
    changes = (
        [{"id": key, "tipo": "adicionado", "atual": new[key]} for key in added]
        + [{"id": key, "tipo": "removido", "anterior": old[key]} for key in removed]
        + [
            {"id": key, "tipo": "alterado", "campos": diff_fields(old[key], new[key])}
            for key in modified
        ]
    )
    review_items = []
    template = []
    used_keys: set[DecisionKey] = set()
    for kind, key, record in [
        *(("registro", key, current.accepted[key]) for key in sorted(current.accepted)),
        *(("remocao", key, old[key]) for key in removed),
    ]:
        used_keys.add((kind, key))
        provenance = (
            {"lote": current.provenance, "detalhe": current.detail_provenance[key]}
            if kind == "registro"
            else {"anterior": previous.provenance, "atual": current.provenance}
        )
        digest = fingerprint(record, provenance)
        decision = decisions.get((kind, key))
        status = (
            "sem_decisao"
            if decision is None
            else "decisao_desatualizada"
            if decision["impressao"] != digest
            else decision["decisao"]
        )
        item = {"tipo": kind, "id": key, "impressao": digest, "status": status}
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
                "id": key,
                "impressao": digest,
                "decisao": "pendente",
                "justificativa": "",
                "evidencias": [],
                "data_decisao": None,
            }
        )
    obsolete = sorted(
        ({"tipo": kind, "id": key} for kind, key in decisions.keys() - used_keys),
        key=lambda item: (item["tipo"], item["id"]),
    )
    provenance_changed = previous is not None and previous.provenance != current.provenance
    coverage_changed = previous is not None and previous.coverage_issues != current.coverage_issues
    issues = current.coverage_issues
    return {
        "modo": "revisao",
        "publicavel": False,
        "dataset": "cursos",
        "entradas": {
            "atual": str(current.file),
            "indice_atual": current.index_file,
            "manifesto_atual": current.manifest_file,
            "consultado_em_atual": current.captured_at.isoformat(),
            "anterior": str(previous.file) if previous else None,
            "indice_anterior": previous.index_file if previous else None,
            "manifesto_anterior": previous.manifest_file if previous else None,
            "consultado_em_anterior": previous.captured_at.isoformat() if previous else None,
        },
        "comparacao": {
            "status": "sem_captura_anterior"
            if previous is None
            else "revisar"
            if changes or provenance_changed or coverage_changed
            else "sem_alteracoes",
            "adicionados": len(added),
            "removidos": len(removed),
            "alterados": len(modified),
            "inalterados": len(new) - len(added) - len(modified) if previous else 0,
            "mudancas": changes,
            "proveniencia_alterada": provenance_changed,
            "cobertura_alterada": coverage_changed,
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
        "modelo_decisoes": {"versao": 1, "dataset": "cursos", "decisoes": template},
        "proveniencia": {
            "atual": current.provenance,
            "anterior": previous.provenance if previous else None,
        },
        "limites": [
            "a origem dos arquivos HTML e JSON locais não é autenticada",
            "a chave da revisão não é um ID estável da API",
            "blocos acadêmicos não foram desdobrados em ofertas",
            "cursos da EaD não foram incluídos",
            "a revisão não gera arquivos em data/ nem autoriza publicação",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Revisa prévias consolidadas locais de cursos")
    parser.add_argument("--atual", required=True, type=Path, help="JSON do lote atual")
    parser.add_argument("--anterior", type=Path, help="JSON do lote anterior")
    parser.add_argument("--decisoes", type=Path, help="manifesto de decisões já registradas")
    parser.add_argument(
        "--modelo-decisoes", type=Path, help="cria um modelo sem sobrescrever arquivos"
    )
    args = parser.parse_args()
    try:
        current = load_course_preview(args.atual)
        previous = load_course_preview(args.anterior) if args.anterior else None
        decisions = load_decisions(args.decisoes, "cursos") if args.decisoes else None
        report = build_course_review(current, previous, decisions)
        if args.modelo_decisoes:
            with args.modelo_decisoes.open("x", encoding="utf-8") as output:
                json.dump(report["modelo_decisoes"], output, ensure_ascii=False, indent=2)
                output.write("\n")
    except (OSError, PreviewReviewError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
