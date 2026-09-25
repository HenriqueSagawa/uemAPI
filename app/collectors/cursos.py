"""Prévia das entradas de graduação presencial no índice da PEN."""

import argparse
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from app.schemas.common import Fonte

SOURCE_URL = "https://www.pen.uem.br/site/public/cursos"
DETAIL_PREFIX = "https://www.pen.uem.br/site/public/curso/"
DETAIL_URL = re.compile(r"https://www\.pen\.uem\.br/site/public/curso/[0-9a-f]{40}\Z")
NEAD_URL = re.compile(r"https://portal\.nead\.uem\.br/site/web/site/cursos(?:#graduacao)?\Z")


class CourseSourceError(ValueError):
    """O índice local não corresponde à estrutura esperada."""


def _normalize(value: str) -> str:
    without_accents = "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    )
    return " ".join(without_accents.casefold().split())


# Associação explícita com os IDs da API. A página da PEN não fornece esses IDs.
CAMPUS_HEADINGS = {
    _normalize("Campus Sede - Maringá/PR"): "sede",
    _normalize("Campus Regional de Cianorte - Cianorte/PR"): "crc",
    _normalize("Campus do Arenito - Cidade Gaúcha/PR"): "car",
    _normalize("Campus Regional do Arenito - Cidade Gaúcha/PR"): "car",
    _normalize("Campus Regional de Goioerê - Goioerê/PR"): "crg",
    _normalize("Campus Regional do Noroeste - Diamante do Norte/PR"): "crn",
    _normalize("Campus Regional de Umuarama - Umuarama/PR"): "cau",
    _normalize("Campus Regional do Vale do Ivaí - Ivaiporã/PR"): "crv",
}
DISTANCE_HEADING = _normalize("Modalidade de Educação a Distância")
# Seções presentes no índice da PEN verificado em 2026-09-25. Mudanças exigem revisão.
EXPECTED_CAMPUS_IDS = frozenset({"sede", "crc", "car", "crg", "crv", "cau"})


@dataclass(frozen=True)
class CourseCandidate:
    nome: str
    campus_id: str
    modalidade: str
    url_detalhe: str


class CourseIndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.courses: list[CourseCandidate] = []
        self.nead_url: str | None = None
        self._main = False
        self._heading_parts: list[str] | None = None
        self._heading_tag: str | None = None
        self._pending_section: str | None = None
        self._section: str | None = None
        self._in_list = False
        self._in_item = False
        self._link_parts: list[str] | None = None
        self._link_url: str | None = None
        self._item_links = 0
        self._section_items = 0
        self._seen_sections: set[str] = set()
        self._seen_course_links: set[tuple[str, str]] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "main":
            self._main = True
        if not self._main:
            return
        if self._pending_section is not None and tag != "ul":
            raise CourseSourceError("seção interrompida antes da lista de cursos")
        if tag in {"p", "h1", "h2", "h3", "h4", "h5", "h6"} and not self._in_list:
            self._heading_parts = []
            self._heading_tag = tag
        elif tag == "ul" and self._pending_section:
            self._section = self._pending_section
            self._pending_section = None
            self._in_list = True
            self._section_items = 0
        elif tag == "ul" and self._in_list:
            raise CourseSourceError("lista aninhada em uma seção de cursos")
        elif tag == "li" and self._in_list:
            self._in_item = True
            self._item_links = 0
        elif tag == "a" and self._in_item:
            if self._link_parts is not None:
                raise CourseSourceError("link aninhado na lista de cursos")
            self._link_parts = []
            self._link_url = attributes.get("href")
        elif tag == "a" and urljoin(SOURCE_URL, attributes.get("href") or "").startswith(
            DETAIL_PREFIX
        ):
            raise CourseSourceError("link de curso fora de uma seção conhecida")

    def handle_data(self, data: str) -> None:
        if self._pending_section is not None and data.strip():
            raise CourseSourceError("seção interrompida antes da lista de cursos")
        if self._heading_parts is not None:
            self._heading_parts.append(data)
        if self._link_parts is not None:
            self._link_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._main:
            return
        if self._pending_section is not None:
            raise CourseSourceError("seção interrompida antes da lista de cursos")
        if tag == self._heading_tag and self._heading_parts is not None:
            self._set_heading(" ".join(self._heading_parts))
            self._heading_parts = None
            self._heading_tag = None
        elif tag == "a" and self._link_parts is not None:
            self._add_link(" ".join(self._link_parts), self._link_url)
            self._link_parts = None
            self._link_url = None
        elif tag == "li" and self._in_item:
            if self._item_links != 1:
                raise CourseSourceError("entrada sem um único link de curso")
            self._in_item = False
        elif tag == "ul" and self._in_list:
            if self._section_items == 0:
                raise CourseSourceError("seção de cursos vazia")
            self._in_list = False
            self._section = None
        elif tag == "main":
            self._main = False

    def _set_heading(self, heading: str) -> None:
        normalized = _normalize(heading)
        if normalized == DISTANCE_HEADING:
            section = "ead"
        elif normalized.startswith("campus "):
            section = CAMPUS_HEADINGS.get(normalized)
            if section is None:
                raise CourseSourceError(f"câmpus desconhecido: {heading.strip()}")
        else:
            return
        if self._pending_section or self._in_list:
            raise CourseSourceError("seção sem lista de cursos")
        if section in self._seen_sections:
            raise CourseSourceError(f"seção duplicada: {heading.strip()}")
        self._seen_sections.add(section)
        self._pending_section = section

    def _add_link(self, name: str, url: str | None) -> None:
        name = " ".join(name.split())
        if not name or not url:
            raise CourseSourceError("nome ou URL ausente na lista de cursos")
        absolute_url = urljoin(SOURCE_URL, url)
        if self._section == "ead":
            if not NEAD_URL.fullmatch(absolute_url):
                raise CourseSourceError("link da EaD não corresponde ao portal NEAD")
            if self.nead_url is not None:
                raise CourseSourceError("link da EaD duplicado")
            self.nead_url = absolute_url
        else:
            if not DETAIL_URL.fullmatch(absolute_url):
                raise CourseSourceError(f"URL de detalhe inesperada: {url}")
            key = (self._section, absolute_url)
            if key in self._seen_course_links:
                raise CourseSourceError("link de curso duplicado no mesmo câmpus")
            self._seen_course_links.add(key)
            self.courses.append(
                CourseCandidate(
                    nome=name,
                    campus_id=self._section,
                    modalidade="presencial",
                    url_detalhe=absolute_url,
                )
            )
        self._item_links += 1
        self._section_items += 1

    def finish(self) -> str:
        self.close()
        if self._pending_section or self._in_list or self._in_item or self._link_parts is not None:
            raise CourseSourceError("seção de cursos incompleta")
        if not self.courses:
            raise CourseSourceError("nenhum curso presencial encontrado")
        if self.nead_url is None:
            raise CourseSourceError("link para os cursos da EaD não encontrado")
        found_campuses = self._seen_sections - {"ead"}
        if found_campuses != EXPECTED_CAMPUS_IDS:
            missing = sorted(EXPECTED_CAMPUS_IDS - found_campuses)
            unexpected = sorted(found_campuses - EXPECTED_CAMPUS_IDS)
            raise CourseSourceError(
                f"cobertura de câmpus divergente; ausentes={missing}, novos={unexpected}"
            )
        return self.nead_url


def collect_courses(html: str) -> tuple[list[CourseCandidate], str]:
    """Lê o índice da PEN sem transformar seus links em IDs da API."""
    parser = CourseIndexParser()
    parser.feed(html)
    nead_url = parser.finish()
    return parser.courses, nead_url


def build_preview(
    courses: list[CourseCandidate], nead_url: str, html_path: Path, consultado_em: datetime
) -> dict:
    fonte = Fonte(source_id="cursos_graduacao", url=SOURCE_URL, consultado_em=consultado_em)
    return {
        "modo": "previa",
        "publicavel": False,
        "entrada": str(html_path),
        "fonte": fonte.model_dump(mode="json"),
        "proveniencia": {
            "unidade": "uma entrada de curso por câmpus no índice da PEN",
            "verificado_no_html": ["nome do link", "agrupamento por câmpus", "URL de detalhe"],
            "mapeamento_local": "títulos de câmpus para IDs da uemAPI",
            "campi_esperados": sorted(EXPECTED_CAMPUS_IDS),
            "campi_encontrados": sorted({course.campus_id for course in courses}),
            "modalidade": "presencial inferida da separação entre câmpus e EaD na página",
            "pendente": [
                "ID estável de curso",
                "ofertas distintas por turno e habilitação",
                "grau",
                "centro e departamento",
                "cursos da EaD",
                "condições de reutilização",
            ],
        },
        "ead": {"url": nead_url, "cursos_incluidos": False},
        "total": len(courses),
        "cursos": [asdict(course) for course in courses],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera uma prévia local dos cursos da PEN")
    parser.add_argument("--html", required=True, type=Path, help="arquivo HTML salvo localmente")
    parser.add_argument(
        "--consultado-em",
        required=True,
        help="data e hora com fuso da captura do HTML (ISO 8601)",
    )
    args = parser.parse_args()
    try:
        consultado_em = datetime.fromisoformat(args.consultado_em.replace("Z", "+00:00"))
        html = args.html.read_text(encoding="utf-8")
        courses, nead_url = collect_courses(html)
        preview = build_preview(courses, nead_url, args.html, consultado_em)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(preview, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
