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
    "turnos": "turno",
    "habilitacao": "habilitacoes",
    "habilitacoes": "habilitacoes",
    "grau academico": "graus_academicos",
}
IGNORED_LABELS = {
    "prazo minimo",
    "prazo de conclusao",
    "prazo minimo de conclusao",
    "prazo maximo de conclusao",
    "prazo para conclusao",
}
METADATA_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
STOP_PREFIXES = (
    "coorden",
    "responsavel",
    "contato",
    "e-mail",
    "email",
    "sobre o curso",
    "mercado de trabalho",
)


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
        self.metadata_parts: list[tuple[str, str]] = []
        self._title_parts: list[str] | None = None
        self._breadcrumb_parts: list[str] | None = None
        self._label_parts: list[str] | None = None
        self._metadata_heading_parts: list[str] | None = None
        self._metadata_heading_tag: str | None = None
        self._list_item_depth = 0

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
        if self.metadata_depth is not None:
            if tag in METADATA_HEADING_TAGS:
                if self._metadata_heading_parts is not None:
                    raise CourseDetailSourceError("título aninhado no detalhe")
                self._metadata_heading_parts = []
                self._metadata_heading_tag = tag
            elif self._metadata_heading_parts is not None:
                return
            elif tag in {"b", "strong"}:
                if self._label_parts is not None:
                    raise CourseDetailSourceError("rótulo aninhado no detalhe")
                self._label_parts = []
            elif tag == "br":
                self.metadata_parts.append(("br", ""))
            elif tag == "li":
                self.metadata_parts.append(("break", ""))
                self._list_item_depth += 1

    def handle_data(self, data: str) -> None:
        if self._title_parts is not None:
            self._title_parts.append(data)
        if self._breadcrumb_parts is not None:
            self._breadcrumb_parts.append(data)
        if self.metadata_depth is not None:
            if self._metadata_heading_parts is not None:
                self._metadata_heading_parts.append(data)
            elif self._label_parts is not None:
                self._label_parts.append(data)
            else:
                kind = "item_text" if self._list_item_depth else "text"
                self.metadata_parts.append((kind, data))

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3" and self._title_parts is not None:
            self.titles.append(" ".join("".join(self._title_parts).split()))
            self._title_parts = None
        elif tag == "a" and self._breadcrumb_parts is not None:
            self.breadcrumbs.append(" ".join("".join(self._breadcrumb_parts).split()))
            self._breadcrumb_parts = None
        if self.metadata_depth is not None:
            if tag == self._metadata_heading_tag:
                heading = " ".join("".join(self._metadata_heading_parts or []).split())
                self.metadata_parts.append(("heading", heading))
                self._metadata_heading_parts = None
                self._metadata_heading_tag = None
            elif self._metadata_heading_parts is not None:
                return
            elif tag in {"b", "strong"} and self._label_parts is not None:
                label = " ".join("".join(self._label_parts).split())
                self._label_parts = None
                self.metadata_parts.append(("label", label.removesuffix(":")))
            elif tag in {"p", "li", "ul"}:
                self.metadata_parts.append(("break", ""))
                if tag == "li":
                    self._list_item_depth -= 1
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
            or self._label_parts is not None
            or self._metadata_heading_parts is not None
            or self._list_item_depth != 0
            or self.metadata_blocks != 1
            or len(self.titles) != 1
            or len(self.breadcrumbs) != 1
        ):
            raise CourseDetailSourceError("estrutura de detalhe ausente, repetida ou incompleta")
        blocks = _parse_academic_blocks(self.metadata_parts)
        if not blocks:
            raise CourseDetailSourceError("informações acadêmicas não reconhecidas")
        return self.titles[0], self.breadcrumbs[0], blocks


def _parse_academic_blocks(parts: list[tuple[str, str]]) -> list[AcademicBlock]:
    blocks: list[AcademicBlock] = []
    block = AcademicBlock()
    current_field: str | None = None
    awaiting_value = False
    ignoring_field = False
    segments: list[tuple[str, str]] = []
    text_parts: list[str] = []
    text_kind: str | None = None
    after_br = False
    for kind, value in [*parts, ("break", "")]:
        if kind in {"text", "item_text"}:
            if kind == "item_text":
                segment_kind = "item"
            elif text_parts and text_kind in {"value", "br_value"}:
                segment_kind = text_kind
            else:
                segment_kind = "br_value" if after_br else "value"
            if text_parts and text_kind != segment_kind:
                segments.append((text_kind, " ".join("".join(text_parts).split())))
                text_parts = []
            text_kind = segment_kind
            text_parts.append(value)
            after_br = False
            continue
        if text_parts:
            segments.append((text_kind, " ".join("".join(text_parts).split())))
            text_parts = []
        text_kind = None
        if kind in {"label", "heading"}:
            segments.append((kind, value))
        after_br = kind == "br"

    for kind, raw_value in segments:
        stripped_value = raw_value.strip()
        # A PEN também representa listas como linhas "- ..." separadas por <br>.
        marked_item = (
            kind == "br_value"
            and stripped_value.startswith("-")
            and current_field in {"habilitacoes", "graus_academicos"}
        )
        value = stripped_value.removeprefix("-").strip()
        if not value:
            continue
        if kind == "heading":
            normalized_heading = _normalize(value.removesuffix(":"))
            if (
                normalized_heading not in ACADEMIC_LABELS
                and normalized_heading not in IGNORED_LABELS
                and not normalized_heading.startswith("prazo ")
            ):
                if (
                    current_field is None
                    and not block.has_data()
                    and not blocks
                    and not normalized_heading.startswith(STOP_PREFIXES)
                ):
                    continue
                break
            kind = "label"
            value = value.removesuffix(":")
        html_label = kind == "label"
        if ignoring_field and kind == "item":
            continue
        if (
            kind in {"value", "br_value"}
            and value.startswith(":")
            and (awaiting_value or ignoring_field)
        ):
            value = value[1:].strip()
            if not value:
                continue
        if kind in {"value", "br_value", "item"}:
            label, separator, remainder = value.partition(":")
            if separator and "(" not in label and len(label) <= 60:
                kind = "label"
                value = label
                inline_value = remainder.strip()
            else:
                inline_value = ""
        else:
            inline_value = ""
        if kind == "label":
            normalized = _normalize(value)
            field_name = ACADEMIC_LABELS.get(normalized)
            if field_name is None:
                if normalized in IGNORED_LABELS:
                    current_field = None
                    awaiting_value = False
                    ignoring_field = True
                    continue
                if normalized.startswith("prazo "):
                    raise CourseDetailSourceError("rótulo de prazo acadêmico não reconhecido")
                if ignoring_field and normalized.startswith("•"):
                    if normalized.lstrip("• ").startswith(STOP_PREFIXES):
                        break
                    continue
                # Valores de prazo podem conter dois-pontos; só um rótulo HTML ou
                # um campo conhecido retoma a coleta depois deles.
                if ignoring_field and not html_label and not normalized.startswith(STOP_PREFIXES):
                    continue
                break
            if field_name == "turno" and block.has_data():
                blocks.append(block)
                block = AcademicBlock()
            current_field = field_name
            awaiting_value = True
            ignoring_field = False
            value = inline_value
        elif ignoring_field:
            continue
        if not value or current_field is None:
            continue
        if kind == "item" and current_field not in {"habilitacoes", "graus_academicos"}:
            raise CourseDetailSourceError("item ambíguo em campo acadêmico")
        if kind in {"value", "br_value"} and not (awaiting_value or marked_item):
            raise CourseDetailSourceError("trecho ambíguo em campo acadêmico")
        if "@" in value:
            raise CourseDetailSourceError("contato encontrado em campo acadêmico")
        if current_field == "turno":
            if block.turno is None:
                block.turno = value
        else:
            getattr(block, current_field).append(value)
        awaiting_value = False
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
            "informacoes_academicas": (
                "campos acadêmicos da seção inicial, agrupados pela ordem dos rótulos HTML"
            ),
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
