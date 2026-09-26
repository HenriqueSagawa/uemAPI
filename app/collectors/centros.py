"""Prévia local dos centros de ensino listados pela PLD."""

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from app.schemas.centro import Centro
from app.schemas.common import Fonte

SOURCE_URL = "https://pld.uem.br/dvl/regulamentos/centros-de-ensino"
EXPECTED_SIGLAS = frozenset({"CCA", "CCB", "CCE", "CCH", "CCS", "CSA", "CTC"})
CENTER_LABEL = re.compile(
    r"(?P<sigla>[A-Z]{2,4}) - (?P<nome>CENTRO DE .+) \(Departamentos e Órgãos\)\Z",
    re.IGNORECASE,
)


class CenterSourceError(ValueError):
    """O índice local não corresponde à estrutura esperada."""


@dataclass(frozen=True)
class CenterCandidate:
    centro: Centro
    url_pagina_vinculada: str


class CenterIndexParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: list[tuple[str, str | None]] = []
        self._content_depth = 0
        self._seen_content = False
        self._in_entry = False
        self._entry_links: list[tuple[str, str | None]] = []
        self._link_parts: list[str] | None = None
        self._link_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "div":
            if self._content_depth:
                self._content_depth += 1
            elif attributes.get("id") == "content-core":
                if self._seen_content:
                    raise CenterSourceError("conteúdo principal duplicado")
                self._seen_content = True
                self._content_depth = 1
        if not self._content_depth:
            return
        if tag == "article" and "entry" in (attributes.get("class") or "").split():
            if self._in_entry:
                raise CenterSourceError("entrada de centro aninhada")
            self._in_entry = True
            self._entry_links = []
        elif tag == "a" and self._in_entry:
            if self._link_parts is not None:
                raise CenterSourceError("link aninhado em uma entrada de centro")
            self._link_parts = []
            self._link_href = attributes.get("href")

    def handle_data(self, data: str) -> None:
        if self._link_parts is not None:
            self._link_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._content_depth:
            return
        if tag == "a" and self._link_parts is not None:
            self._entry_links.append(
                (" ".join(" ".join(self._link_parts).split()), self._link_href)
            )
            self._link_parts = None
            self._link_href = None
        elif tag == "article" and self._in_entry:
            if len(self._entry_links) != 1:
                raise CenterSourceError("entrada de centro sem um único link")
            self.entries.append(self._entry_links[0])
            self._in_entry = False
        if tag == "div":
            self._content_depth -= 1

    def finish(self) -> list[tuple[str, str | None]]:
        self.close()
        if not self._seen_content or self._content_depth or self._in_entry or self._link_parts:
            raise CenterSourceError("índice de centros ausente ou incompleto")
        return self.entries


def _detail_url(href: str | None) -> str:
    if not href:
        raise CenterSourceError("link de centro sem URL")
    url = urljoin(f"{SOURCE_URL}/", href)
    parsed = urlsplit(url)
    prefix = urlsplit(SOURCE_URL).path + "/"
    suffix = parsed.path.removeprefix(prefix)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "pld.uem.br"
        or not parsed.path.startswith(prefix)
        or not suffix
        or "/" in suffix
        or not suffix.startswith("centro-de-")
        or parsed.query
        or parsed.fragment
    ):
        raise CenterSourceError(f"URL de centro inesperada: {href}")
    return url


def collect_centros(html: str, consultado_em: datetime) -> list[CenterCandidate]:
    """Extrai apenas os sete centros do índice, sem visitar suas páginas vinculadas."""
    parser = CenterIndexParser()
    parser.feed(html)
    entries = parser.finish()
    fonte = Fonte(source_id="centros_pld", url=SOURCE_URL, consultado_em=consultado_em)
    candidates = []
    seen: set[str] = set()
    seen_urls: set[str] = set()
    for label, href in entries:
        match = CENTER_LABEL.fullmatch(label)
        if match is None:
            raise CenterSourceError(f"entrada de centro inesperada: {label}")
        sigla = match.group("sigla").upper()
        if sigla in seen:
            raise CenterSourceError(f"centro duplicado: {sigla}")
        seen.add(sigla)
        detail_url = _detail_url(href)
        if detail_url in seen_urls:
            raise CenterSourceError(f"link de centro duplicado: {detail_url}")
        seen_urls.add(detail_url)
        candidates.append(
            CenterCandidate(
                centro=Centro(id=sigla.lower(), nome=match.group("nome"), sigla=sigla, fonte=fonte),
                url_pagina_vinculada=detail_url,
            )
        )
    if seen != EXPECTED_SIGLAS:
        missing = sorted(EXPECTED_SIGLAS - seen)
        unexpected = sorted(seen - EXPECTED_SIGLAS)
        raise CenterSourceError(
            f"cobertura de centros divergente; ausentes={missing}, novos={unexpected}"
        )
    return candidates


def build_preview(centros: list[CenterCandidate], html_path: Path) -> dict:
    return {
        "modo": "previa",
        "publicavel": False,
        "entrada": str(html_path),
        "proveniencia": {
            "fonte_url": (
                "O campo fonte.url aponta para o índice institucional; "
                "não comprova a origem do arquivo local."
            ),
            "verificado_no_html": ["sigla", "nome exibido", "link da página vinculada"],
            "transformacoes_locais": [
                "id = sigla em minúsculas",
                "sufixo '(Departamentos e Órgãos)' removido do nome",
            ],
            "campi_e_departamentos": "não verificados neste índice",
            "status": "valor padrão do schema; não verificado no HTML",
            "pendente": ["revisão dos registros", "condições de reutilização"],
        },
        "total": len(centros),
        "centros": [
            {
                **candidate.centro.model_dump(mode="json"),
                "url_pagina_vinculada": candidate.url_pagina_vinculada,
            }
            for candidate in centros
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera uma prévia local dos centros da PLD")
    parser.add_argument("--html", required=True, type=Path, help="arquivo HTML salvo localmente")
    parser.add_argument(
        "--consultado-em", required=True, help="data e hora com fuso da captura (ISO 8601)"
    )
    args = parser.parse_args()
    try:
        consultado_em = datetime.fromisoformat(args.consultado_em.replace("Z", "+00:00"))
        html = args.html.read_text(encoding="utf-8")
        centros = collect_centros(html, consultado_em)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(build_preview(centros, args.html), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
