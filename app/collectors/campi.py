"""Prévia local dos câmpus listados na página institucional da UEM."""

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

from pydantic import ValidationError

from app.schemas.campus import Campus
from app.schemas.common import Fonte

SOURCE_URL = "https://www.uem.br/a-uem/campus"
SUPPORT_URL = "https://pld.uem.br/lni/v05-base-de-dados-2024-2025.pdf"


class CampusSourceError(ValueError):
    """A página não corresponde à estrutura esperada para a prévia."""


@dataclass(frozen=True)
class CampusSpec:
    id: str
    nome: str
    cidade: str
    sigla: str | None


# IDs definidos em docs/campus-identifiers.md; não derivar IDs dos nomes da página.
CAMPUS_SPECS = (
    CampusSpec("sede", "Câmpus Sede", "Maringá", None),
    CampusSpec("crc", "Câmpus Regional de Cianorte", "Cianorte", "CRC"),
    CampusSpec("crg", "Câmpus Regional de Goioerê", "Goioerê", "CRG"),
    CampusSpec("car", "Câmpus Regional do Arenito", "Cidade Gaúcha", "CAR"),
    CampusSpec("crn", "Câmpus Regional do Noroeste", "Diamante do Norte", "CRN"),
    CampusSpec("cau", "Câmpus Regional de Umuarama", "Umuarama", "CAU"),
    CampusSpec("crv", "Câmpus Regional do Vale do Ivaí", "Ivaiporã", "CRV"),
)

CITY_ALIASES = {
    "cianorte": "Cianorte",
    "cidade gaucha": "Cidade Gaúcha",
    "diamante de norte": "Diamante do Norte",
    "diamante do norte": "Diamante do Norte",
    "goioere": "Goioerê",
    "ivaipora": "Ivaiporã",
    "umuarama": "Umuarama",
}

REGIONAL_LIST = re.compile(
    r"\bcampus sede\b.*?\bmaringa\b.*?\bseis campus regionais\b"
    r".*?\bmunicipios de\s+(?P<cidades>[^.]+)\."
)


class Paragraphs(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[str] = []
        self._parts: list[str] = []
        self._inside_paragraph = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self._inside_paragraph = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._inside_paragraph:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._inside_paragraph:
            self.paragraphs.append(" ".join(self._parts))
            self._inside_paragraph = False


def _normalize(value: str) -> str:
    without_accents = "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    )
    return " ".join(without_accents.casefold().split())


def extract_regional_cities(html: str) -> set[str]:
    parser = Paragraphs()
    parser.feed(html)
    matching_lists = [
        match.group("cidades")
        for paragraph in parser.paragraphs
        if (match := REGIONAL_LIST.search(_normalize(paragraph)))
    ]
    if len(matching_lists) != 1:
        raise CampusSourceError("a lista institucional de câmpus não foi encontrada uma única vez")

    names = re.split(r",\s*|\s+e\s+", matching_lists[0])
    cities = [CITY_ALIASES.get(name.strip()) for name in names]
    expected = {spec.cidade for spec in CAMPUS_SPECS if spec.id != "sede"}
    if None in cities or len(cities) != 6 or set(cities) != expected:
        raise CampusSourceError("os seis municípios regionais não correspondem à tabela revisada")
    return set(cities)


def collect_campi(html: str, consultado_em: datetime) -> list[Campus]:
    """Valida a lista da página e produz candidatos; não publica um snapshot."""
    extract_regional_cities(html)
    fonte = Fonte(source_id="campi_uem", url=SOURCE_URL, consultado_em=consultado_em)
    return [
        Campus(id=spec.id, nome=spec.nome, cidade=spec.cidade, sigla=spec.sigla, fonte=fonte)
        for spec in CAMPUS_SPECS
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera uma prévia local dos câmpus da UEM")
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
        campi = collect_campi(html, consultado_em)
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        parser.error(str(exc))

    print(
        json.dumps(
            {
                "modo": "previa",
                "publicavel": False,
                "entrada": str(args.html),
                "fontes": [SOURCE_URL, SUPPORT_URL],
                "campi": [campus.model_dump(mode="json") for campus in campi],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
