"""Prévia local de uma página de detalhe de curso da PEN."""

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

from app.collectors.cursos import (
    CAMPUS_HEADINGS,
    DETAIL_URL,
    SOURCE_URL,
    CourseCandidate,
    _normalize,
    collect_courses,
)
from app.schemas.common import Fonte

DETAIL_CAMPUSES = {
    f"graduacao - {heading.rsplit(' - ', 1)[0]}": campus_id
    for heading, campus_id in CAMPUS_HEADINGS.items()
}
ACADEMIC_LABELS = {
    "turno": "turno",
    "habilitacao": "habilitacoes",
    "habilitacoes": "habilitacoes",
    "grau academico": "graus_academicos",
}
STOP_PREFIXES = ("coorden", "sobre o curso", "e-mail", "email", "mercado de trabalho")


class CourseDetailSourceError(ValueError):
    """A captura não corresponde ao curso e à estrutura esperados."""


@dataclass
class AcademicBlock:
    turno: str | None = None
    habilitacoes: list[str] = field(default_factory=list)
    graus_academicos: list[str] = field(default_factory=list)

    def has_data(self) -> bool:
        return bool(self.turno or self.habilitacoes or self.graus_academicos)


class CourseDetailParser(HTMLParser):
    """Lê título, vínculo ao índice e o bloco inicial de informações acadêmicas."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.div_depth = 0
        self.root_depth: int | None = None
        self.metadata_depth: int | None = None
        self.roots = 0
        self.metadata_blocks = 0
        self.titles: list[str] = []
        self.breadcrumbs: list[str] = []
        self.metadata_parts: list[str] = []
        self._title_parts: list[str] | None = None
        self._breadcrumb_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "div":
            self.div_depth += 1
            if {"container", "mb-15"} <= classes:
                if self.root_depth is not None:
                    raise CourseDetailSourceError("conteúdo principal aninhado")
                self.roots += 1
                self.root_depth = self.div_depth
            elif self.root_depth is not None and {"flex", "flex-col", "w-full", "my-6"} <= classes:
                self.metadata_blocks += 1
                self.metadata_depth = self.div_depth
        if self.root_depth is None:
            return
        if tag == "h3" and self.metadata_depth is None:
            if self._title_parts is not None:
                raise CourseDetailSourceError("título aninhado")
            self._title_parts = []
        elif tag == "a" and attributes.get("href") == SOURCE_URL and self.metadata_depth is None:
            self._breadcrumb_parts = []
        if self.metadata_depth is not None and tag in {"br", "li"}:
            self.metadata_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._title_parts is not None:
            self._title_parts.append(data)
        if self._breadcrumb_parts is not None:
            self._breadcrumb_parts.append(data)
        if self.metadata_depth is not None:
            self.metadata_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3" and self._title_parts is not None:
            self.titles.append(" ".join("".join(self._title_parts).split()))
            self._title_parts = None
        elif tag == "a" and self._breadcrumb_parts is not None:
            self.breadcrumbs.append(" ".join("".join(self._breadcrumb_parts).split()))
            self._breadcrumb_parts = None
        if self.metadata_depth is not None and tag in {"p", "li", "ul"}:
            self.metadata_parts.append("\n")
        if tag == "div":
            if self.metadata_depth == self.div_depth:
                self.metadata_depth = None
            if self.root_depth == self.div_depth:
                self.root_depth = None
            self.div_depth -= 1

    def finish(self) -> tuple[str, str, list[AcademicBlock]]:
        self.close()
        if (
            self.roots != 1
            or self.root_depth is not None
            or self.metadata_depth is not None
            or self.metadata_blocks != 1
            or len(self.titles) != 1
            or len(self.breadcrumbs) != 1
        ):
            raise CourseDetailSourceError("estrutura de detalhe ausente, repetida ou incompleta")
        blocks = _parse_academic_blocks(self.metadata_parts)
        if not blocks:
            raise CourseDetailSourceError("informações acadêmicas não reconhecidas")
        return self.titles[0], self.breadcrumbs[0], blocks


def _parse_academic_blocks(parts: list[str]) -> list[AcademicBlock]:
    blocks: list[AcademicBlock] = []
    block = AcademicBlock()
    current_field: str | None = None
    for raw_line in "".join(parts).splitlines():
        line = " ".join(raw_line.strip().removeprefix("-").split())
        if not line:
            continue
        normalized = _normalize(line)
        if normalized.startswith(STOP_PREFIXES):
            break
        label, separator, value = line.partition(":")
        field_name = ACADEMIC_LABELS.get(_normalize(label))
        if field_name is not None:
            if field_name == "turno" and block.has_data():
                blocks.append(block)
                block = AcademicBlock()
            current_field = field_name
            if separator and value.strip():
                if field_name == "turno":
                    block.turno = " ".join(value.split())
                else:
                    getattr(block, field_name).append(" ".join(value.split()))
            continue
        if normalized.startswith("prazo "):
            current_field = None
            continue
        if current_field == "turno" and block.turno is None:
            block.turno = line
        elif current_field in {"habilitacoes", "graus_academicos"}:
            getattr(block, current_field).append(line)
    if block.has_data():
        blocks.append(block)
    return blocks


def _candidate_id(course: CourseCandidate) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _normalize(course.nome)).strip("-")
    if not slug:
        raise CourseDetailSourceError("nome sem ID candidato válido")
    return f"{course.campus_id}-{slug}"


@dataclass
class CourseDetailCollection:
    course: CourseCandidate
    id_candidato: str
    blocks: list[AcademicBlock]
    fonte: Fonte


def collect_course_detail(
    index_html: str,
    detail_html: str,
    campus_id: str,
    detail_url: str,
    consultado_em: datetime,
) -> CourseDetailCollection:
    """Confere o detalhe com uma entrada do índice local, sem publicar registros."""
    if not DETAIL_URL.fullmatch(detail_url):
        raise CourseDetailSourceError("URL de detalhe inesperada")
    courses, _ = collect_courses(index_html)
    ids = [_candidate_id(course) for course in courses]
    if len(ids) != len(set(ids)):
        raise CourseDetailSourceError("IDs candidatos duplicados no índice")
    matches = [
        course
        for course in courses
        if course.campus_id == campus_id and course.url_detalhe == detail_url
    ]
    if len(matches) != 1:
        raise CourseDetailSourceError("curso não encontrado no índice e câmpus informados")
    course = matches[0]
    parser = CourseDetailParser()
    parser.feed(detail_html)
    title, breadcrumb, blocks = parser.finish()
    if _normalize(title) != _normalize(course.nome):
        raise CourseDetailSourceError("título do detalhe difere do índice")
    if DETAIL_CAMPUSES.get(_normalize(breadcrumb)) != campus_id:
        raise CourseDetailSourceError("câmpus do detalhe difere do índice")
    fonte = Fonte(source_id="cursos_graduacao", url=detail_url, consultado_em=consultado_em)
    return CourseDetailCollection(course, _candidate_id(course), blocks, fonte)


def build_preview(collection: CourseDetailCollection, index_path: Path, detail_path: Path) -> dict:
    return {
        "modo": "previa",
        "publicavel": False,
        "entrada": {"indice": str(index_path), "detalhe": str(detail_path)},
        "fonte": collection.fonte.model_dump(mode="json"),
        "curso": {
            **asdict(collection.course),
            "id_candidato": collection.id_candidato,
            "informacoes_academicas": [asdict(block) for block in collection.blocks],
        },
        "proveniencia": {
            "unidade": "uma entrada do índice por câmpus; blocos não são ofertas separadas",
            "id_candidato": "câmpus e nome normalizado; muda se o nome mudar e exige revisão",
            "verificado": ["link no índice local", "título", "câmpus exibido no detalhe"],
            "informacoes_academicas": "texto da seção inicial, agrupado pela ordem dos rótulos",
            "origem_arquivos": "não autenticada; URLs institucionais apenas de referência",
            "pendente": [
                "ID estável aprovado",
                "interpretação de turnos, habilitações e graus como ofertas",
                "centro e departamento",
                "cursos da EaD",
                "completude e condições de reutilização",
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera prévia local de detalhe de curso da PEN")
    parser.add_argument("--indice", required=True, type=Path, help="HTML local do índice da PEN")
    parser.add_argument("--html", required=True, type=Path, help="HTML local do detalhe do curso")
    parser.add_argument("--campus", required=True, choices=sorted(set(CAMPUS_HEADINGS.values())))
    parser.add_argument("--url", required=True, help="URL de detalhe associada no índice")
    parser.add_argument(
        "--consultado-em", required=True, help="hora da captura com fuso (ISO 8601)"
    )
    args = parser.parse_args()
    try:
        consultado_em = datetime.fromisoformat(args.consultado_em.replace("Z", "+00:00"))
        collection = collect_course_detail(
            args.indice.read_text(encoding="utf-8"),
            args.html.read_text(encoding="utf-8"),
            args.campus,
            args.url,
            consultado_em,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(build_preview(collection, args.indice, args.html), ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
