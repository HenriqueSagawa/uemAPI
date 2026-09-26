"""Relatório local de cobertura das páginas de detalhe dos cursos da PEN."""

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.collectors import curso_detalhes
from app.collectors.cursos import SOURCE_URL, collect_courses
from app.schemas.common import Fonte


@dataclass(frozen=True)
class DetailCapture:
    campus_id: str
    url_detalhe: str
    arquivo: Path
    consultado_em: datetime


def parse_capture_time(value: str) -> datetime:
    try:
        captured_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("consultado_em deve estar em formato ISO 8601") from exc
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("consultado_em deve incluir fuso horário")
    return captured_at


def load_manifest(path: Path) -> list[DetailCapture]:
    """Associa explicitamente cada captura a um link e câmpus do índice."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"detalhes"}:
        raise ValueError("manifesto deve conter apenas a lista detalhes")
    entries = data["detalhes"]
    if not isinstance(entries, list):
        raise ValueError("detalhes deve ser uma lista")
    captures = []
    seen_keys = set()
    for position, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or set(entry) != {
            "campus_id",
            "url_detalhe",
            "arquivo",
            "consultado_em",
        }:
            raise ValueError(f"entrada {position} do manifesto tem campos inválidos")
        if any(not isinstance(entry[key], str) or not entry[key].strip() for key in entry):
            raise ValueError(f"entrada {position} do manifesto tem valor vazio ou inválido")
        key = (entry["campus_id"], entry["url_detalhe"])
        if key in seen_keys:
            raise ValueError(f"entrada duplicada no manifesto: {key[0]}, {key[1]}")
        seen_keys.add(key)
        file_path = Path(entry["arquivo"])
        captures.append(
            DetailCapture(
                campus_id=key[0],
                url_detalhe=key[1],
                arquivo=file_path if file_path.is_absolute() else path.parent / file_path,
                consultado_em=parse_capture_time(entry["consultado_em"]),
            )
        )
    return captures


def build_batch_preview(
    index_html: str,
    captures: list[DetailCapture],
    index_path: Path,
    manifest_path: Path,
    consultado_em_indice: datetime,
) -> dict:
    """Gera prévias individuais e registra lacunas sem publicar dados da API."""
    courses, nead_url = collect_courses(index_html)
    ids = [curso_detalhes.candidate_id(course) for course in courses]
    if len(ids) != len(set(ids)):
        raise curso_detalhes.CourseDetailSourceError("IDs candidatos duplicados no índice")

    by_key = {(capture.campus_id, capture.url_detalhe): capture for capture in captures}
    if len(by_key) != len(captures):
        raise ValueError("capturas duplicadas no manifesto")
    files = [capture.arquivo.resolve() for capture in captures]
    if len(files) != len(set(files)):
        raise ValueError("arquivo de detalhe duplicado no manifesto")
    index_keys = {(course.campus_id, course.url_detalhe) for course in courses}
    results = []
    counts_by_campus: dict[str, Counter] = {}
    statuses = Counter()

    for course in courses:
        key = (course.campus_id, course.url_detalhe)
        capture = by_key.get(key)
        result = {
            "campus_id": course.campus_id,
            "nome": course.nome,
            "url_detalhe": course.url_detalhe,
        }
        if capture is None:
            result["status"] = "sem_captura"
        else:
            result["arquivo"] = str(capture.arquivo)
            result["consultado_em"] = capture.consultado_em.isoformat()
            try:
                detail_html = capture.arquivo.read_text(encoding="utf-8")
            except FileNotFoundError:
                result["status"] = "arquivo_ausente"
            except (OSError, UnicodeError):
                result["status"] = "falha_leitura"
            else:
                try:
                    collection = curso_detalhes.collect_course_detail_from_candidate(
                        course, detail_html, capture.consultado_em
                    )
                except curso_detalhes.CourseDetailSourceError as exc:
                    result["status"] = "invalido"
                    result["motivo"] = str(exc)
                else:
                    result["status"] = "aceito"
                    result["previa"] = curso_detalhes.build_preview(
                        collection, index_path, capture.arquivo
                    )
        results.append(result)
        statuses[result["status"]] += 1
        counts_by_campus.setdefault(course.campus_id, Counter())[result["status"]] += 1

    extras = [
        {
            "campus_id": capture.campus_id,
            "url_detalhe": capture.url_detalhe,
            "arquivo": str(capture.arquivo),
            "consultado_em": capture.consultado_em.isoformat(),
            "status": "fora_do_indice",
        }
        for key, capture in sorted(by_key.items())
        if key not in index_keys
    ]
    accepted = statuses["aceito"]
    fonte = Fonte(source_id="cursos_graduacao", url=SOURCE_URL, consultado_em=consultado_em_indice)
    return {
        "modo": "previa",
        "publicavel": False,
        "entrada": {"indice": str(index_path), "manifesto": str(manifest_path)},
        "fonte_indice": fonte.model_dump(mode="json"),
        "ead": {"url": nead_url, "cursos_incluidos": False},
        "resumo": {
            "total_indice": len(courses),
            "total_manifesto": len(captures),
            "aceitos": accepted,
            "sem_captura": statuses["sem_captura"],
            "arquivo_ausente": statuses["arquivo_ausente"],
            "falha_leitura": statuses["falha_leitura"],
            "invalidos": statuses["invalido"],
            "fora_do_indice": len(extras),
            "cobertura_completa": accepted == len(courses) and not extras,
            "por_campus": {
                campus_id: {
                    "total": sum(counts.values()),
                    "aceitos": counts["aceito"],
                    "sem_captura": counts["sem_captura"],
                    "arquivo_ausente": counts["arquivo_ausente"],
                    "falha_leitura": counts["falha_leitura"],
                    "invalidos": counts["invalido"],
                }
                for campus_id, counts in sorted(counts_by_campus.items())
            },
        },
        "resultados": results,
        "fora_do_indice": extras,
        "proveniencia": {
            "origem_arquivos": "não autenticada; URLs institucionais apenas de referência",
            "unidade": "uma entrada do índice por câmpus; blocos acadêmicos não são ofertas",
            "revisao_pendente": [
                "IDs estáveis",
                "interpretação de ofertas",
                "centro e departamento",
                "EaD",
                "completude e condições de reutilização",
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolida prévias locais dos cursos da PEN")
    parser.add_argument("--indice", required=True, type=Path, help="HTML local do índice da PEN")
    parser.add_argument("--manifesto", required=True, type=Path, help="JSON das páginas salvas")
    parser.add_argument(
        "--consultado-em-indice",
        required=True,
        help="hora da captura do índice com fuso (ISO 8601)",
    )
    args = parser.parse_args()
    try:
        captured_at = parse_capture_time(args.consultado_em_indice)
        captures = load_manifest(args.manifesto)
        preview = build_batch_preview(
            args.indice.read_text(encoding="utf-8"),
            captures,
            args.indice,
            args.manifesto,
            captured_at,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(preview, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
