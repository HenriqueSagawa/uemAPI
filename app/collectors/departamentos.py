"""Prévia de departamentos em uma cópia local da página de um centro na PLD."""

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from app.schemas.common import Fonte
from app.schemas.departamento import Departamento

SOURCE_ROOT = "https://pld.uem.br/dvl/regulamentos/centros-de-ensino"
# Mapeia somente as páginas dos centros, sem catálogo de departamentos.
CENTROS = {
    "CCA": ("Centro de Ciências Agrárias", "centro-de-ciencias-agrarias"),
    "CCB": ("Centro de Ciências Biológicas", "centro-de-ciencias-biologicas-ccb"),
    "CCE": ("Centro de Ciências Exatas", "centro-de-ciencias-exatas-cce"),
    "CCH": (
        "Centro de Ciências Humanas, Letras e Artes",
        "centro-de-ciencias-humanas-letras-e-artes-cch",
    ),
    "CCS": ("Centro de Ciências da Saúde", "centro-de-ciencias-da-saude-ccs"),
    "CSA": ("Centro de Ciências Sociais Aplicadas", "centro-de-ciencias-sociais-aplicadas-csa"),
    "CTC": ("Centro de Tecnologia", "centro-de-tecnologia-ctc"),
}
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
RESOLUTION = re.compile(r"\s*-?\s*\((?:Resolução|Resolucao)\b[^()]*\)?$", re.IGNORECASE)
LABEL = re.compile(r"^([^\s]+)\s+-\s+(.+)$")


class DepartamentoSourceError(ValueError):
    """A captura não corresponde à página e à estrutura esperadas."""


@dataclass
class Link:
    href: str
    parts: list[str] = field(default_factory=list)
    image: bool = False

    @property
    def label(self) -> str:
        return " ".join("".join(self.parts).split())


class DepartmentPageParser(HTMLParser):
    """Captura somente o conteúdo principal e as entradas de content-core."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, str]] = []
        self.headings: list[str] = []
        self.entries: list[list[Link]] = []
        self.contents = 0
        self.cores = 0
        self.lists = 0
        self.heading_parts: list[str] = []
        self.links: list[Link] | None = None
        self.link: Link | None = None

    def _inside(self, role: str) -> bool:
        return any(item_role == role for _, item_role in self.stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        role = ""
        if tag == "article" and attributes.get("id") == "content":
            if self.stack:
                raise DepartamentoSourceError("conteúdo principal aninhado")
            self.contents += 1
            role = "content"
        elif not self.stack:
            return
        elif tag == "article" and self._inside("entry"):
            raise DepartamentoSourceError("article aninhado em uma entrada")
        elif tag == "div" and attributes.get("id") == "content-core":
            self.cores += 1
            role = "core"
        elif tag == "div" and "entries" in classes and self._inside("core"):
            if self._inside("entries"):
                raise DepartamentoSourceError("lista de entradas aninhada")
            self.lists += 1
            role = "entries"
        elif tag == "article" and "entry" in classes:
            if not self._inside("entries"):
                raise DepartamentoSourceError("entrada fora da lista esperada")
            self.links = []
            role = "entry"
        elif tag == "article" and self._inside("core"):
            raise DepartamentoSourceError("article fora do formato entry no conteúdo principal")
        elif tag == "a" and self._inside("entries") and not self._inside("entry"):
            raise DepartamentoSourceError("link fora de uma entrada")
        elif tag == "h1" and "documentFirstHeading" in classes:
            if self._inside("core"):
                raise DepartamentoSourceError("título fora do cabeçalho principal")
            self.heading_parts = []
            role = "heading"
        elif tag == "a" and self._inside("entry"):
            if self.link is not None or not any(item_tag == "header" for item_tag, _ in self.stack):
                raise DepartamentoSourceError("link fora do cabeçalho da entrada ou aninhado")
            self.link = Link(attributes.get("href") or "")
            assert self.links is not None
            self.links.append(self.link)
            role = "link"
        if tag == "img" and self.link is not None:
            self.link.image = True
        if tag not in VOID_TAGS:
            self.stack.append((tag, role))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._inside("heading"):
            self.heading_parts.append(data)
        if self.link is not None:
            self.link.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or tag in VOID_TAGS:
            return
        if self.stack[-1][0] != tag:
            raise DepartamentoSourceError("estrutura HTML incompleta ou fechamento inesperado")
        _, role = self.stack.pop()
        if role == "heading":
            self.headings.append(" ".join("".join(self.heading_parts).split()))
        elif role == "link":
            self.link = None
        elif role == "entry":
            assert self.links is not None
            self.entries.append(self.links)
            self.links = None

    def finish(self) -> None:
        self.close()
        if self.stack or (self.contents, self.cores, self.lists) != (1, 1, 1):
            raise DepartamentoSourceError(
                "conteúdo principal ou lista ausente, repetida ou incompleta"
            )


def _regulation_url(href: str, source_url: str) -> str:
    # Rejeita evasões antes de urljoin, que normalizaria segmentos de travessia.
    if (
        not href
        or any(char.isspace() or ord(char) < 32 for char in href)
        or any(char in href for char in "\\%?#")
        or any(segment in {".", ".."} for segment in urlsplit(href).path.split("/"))
    ):
        raise DepartamentoSourceError("URL de regulamento inválida")
    resolved = urljoin(source_url + "/", href)
    parsed = urlsplit(resolved)
    prefix = urlsplit(source_url).path + "/"
    if (
        parsed.scheme != "https"
        or parsed.netloc != "pld.uem.br"
        or not parsed.path.startswith(prefix)
        or parsed.path == prefix
        or "//" in parsed.path
    ):
        raise DepartamentoSourceError("URL de regulamento fora da página institucional do centro")
    return resolved


@dataclass
class DepartmentCollection:
    centro_sigla: str
    source_url: str
    departamentos: list[Departamento]
    auditoria: list[dict]
    excluidos: list[dict]


def collect_departamentos(
    html: str, centro_sigla: str, consultado_em: datetime
) -> DepartmentCollection:
    """Extrai candidatos e mantém entradas excluídas para revisão manual."""
    centro_sigla = centro_sigla.upper()
    if centro_sigla not in CENTROS:
        raise DepartamentoSourceError("centro desconhecido")
    centro_nome, slug = CENTROS[centro_sigla]
    source_url = f"{SOURCE_ROOT}/{slug}"
    fonte = Fonte(source_id="centros_pld", url=source_url, consultado_em=consultado_em)
    parser = DepartmentPageParser()
    parser.feed(html)
    parser.finish()
    expected_heading = f"{centro_sigla} - {centro_nome} (Departamentos e Órgãos)"
    if [value.casefold() for value in parser.headings] != [expected_heading.casefold()]:
        raise DepartamentoSourceError("título não identifica o centro solicitado")

    departamentos = []
    auditoria = []
    excluidos = []
    seen_siglas: set[str] = set()
    seen_urls: set[str] = set()
    found_center = False
    for links in parser.entries:
        textual = [link for link in links if link.label]
        if len(textual) != 1 or len(links) not in {1, 2}:
            raise DepartamentoSourceError(
                "entrada deve conter um único link textual de regulamento"
            )
        link = textual[0]
        url = _regulation_url(link.href, source_url)
        if any(
            not other.label and (not other.image or _regulation_url(other.href, source_url) != url)
            for other in links
        ):
            raise DepartamentoSourceError("link de ícone inesperado na entrada")
        match = LABEL.fullmatch(link.label)
        if match is None or not match[1].isupper():
            raise DepartamentoSourceError("rótulo sem sigla e nome reconhecíveis")
        sigla, raw_name = match.groups()
        nome = RESOLUTION.sub("", raw_name).strip()
        if sigla.casefold() in seen_siglas or url in seen_urls:
            raise DepartamentoSourceError("sigla ou URL duplicada na página")
        seen_siglas.add(sigla.casefold())
        seen_urls.add(url)
        audit = {"sigla": sigla, "rotulo_original": link.label, "regulamento_url": url}
        if sigla in CENTROS or nome.casefold().startswith("centro de "):
            if sigla != centro_sigla or nome.casefold() != centro_nome.casefold():
                raise DepartamentoSourceError("entrada de centro incompatível com o título")
            found_center = True
            excluidos.append({**audit, "motivo": "regulamento do próprio centro"})
            continue
        typo_dem = sigla == "DEM" and nome == "Deparamento de Engenharia Mecânica"
        if nome.startswith("Departamento") and not nome.startswith("Departamento de "):
            raise DepartamentoSourceError("nome de departamento incompleto ou inesperado")
        if not nome.startswith("Departamento de ") and not typo_dem:
            excluidos.append(
                {
                    **audit,
                    "motivo": "rótulo não identifica departamento; classificação exige revisão",
                }
            )
            continue
        departamentos.append(
            Departamento(
                id=sigla.lower(), nome=nome, sigla=sigla, centro_sigla=centro_sigla, fonte=fonte
            )
        )
        if typo_dem:
            audit["observacao"] = (
                "grafia Deparamento observada na fonte; nome preservado para revisão"
            )
        auditoria.append(audit)
    if not found_center or not departamentos:
        raise DepartamentoSourceError("regulamento do centro ou departamentos ausentes")
    return DepartmentCollection(centro_sigla, source_url, departamentos, auditoria, excluidos)


def build_preview(collection: DepartmentCollection, html_path: Path) -> dict:
    return {
        "modo": "previa",
        "publicavel": False,
        "entrada": str(html_path),
        "cobertura": {
            "centro_sigla": collection.centro_sigla,
            "status": "parcial_por_centro",
            "completude": "não verificada; conferir ausências e alterações manualmente",
            "outros_centros": "não coletados nesta captura",
        },
        "proveniencia": {
            "fonte_url": collection.source_url,
            "origem_arquivo": "não autenticada; URL institucional de referência",
            "id": "candidato interno obtido da sigla em minúsculas; exige revisão",
            "centro_sigla": "validado pelo título e pelo regulamento do próprio centro",
            "campus_id": "não informado na página; permanece null",
            "status": "desconhecido; situação atual não verificada",
            "reutilizacao": "condições pendentes de revisão",
            "regulamentos": "links preservados; conteúdo dos documentos não consultado",
        },
        "departamentos": [item.model_dump(mode="json") for item in collection.departamentos],
        "auditoria": collection.auditoria,
        "excluidos": collection.excluidos,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera prévia local dos departamentos de um centro")
    parser.add_argument("--html", required=True, type=Path, help="HTML salvo localmente")
    parser.add_argument("--centro", required=True, choices=sorted(CENTROS))
    parser.add_argument(
        "--consultado-em", required=True, help="hora da captura com fuso (ISO 8601)"
    )
    args = parser.parse_args()
    try:
        consultado_em = datetime.fromisoformat(args.consultado_em.replace("Z", "+00:00"))
        collection = collect_departamentos(
            args.html.read_text(encoding="utf-8"), args.centro, consultado_em
        )
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(build_preview(collection, args.html), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
