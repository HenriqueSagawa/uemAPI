import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.collectors.departamentos import (
    CENTROS,
    DepartamentoSourceError,
    build_preview,
    collect_departamentos,
)

FIXTURE = Path(__file__).parent / "fixtures" / "departamentos_ctc.html"
CAPTURED_AT = datetime(2026, 9, 26, tzinfo=UTC)
SOURCE_URL = "https://pld.uem.br/dvl/regulamentos/centros-de-ensino/centro-de-tecnologia-ctc"


@pytest.fixture
def html():
    return FIXTURE.read_text(encoding="utf-8")


def collect(html, centro="CTC", consultado_em=CAPTURED_AT):
    return collect_departamentos(html, centro, consultado_em)


def test_extracts_candidates_and_keeps_exclusions_auditable(html):
    result = collect(html)
    assert [item.sigla for item in result.departamentos] == ["DIN", "DAU", "DDM", "DEM"]
    assert result.departamentos[0].id == "din"
    assert result.departamentos[0].nome == "Departamento de Informática"
    assert result.departamentos[1].nome == "Departamento de Arquitetura e Urbanismo"
    assert result.departamentos[2].nome == "Departamento de Design e Moda"
    assert result.departamentos[3].nome == "Deparamento de Engenharia Mecânica"
    assert "nome preservado" in result.auditoria[3]["observacao"]
    assert [item["sigla"] for item in result.excluidos] == ["CTC", "NUPÉLIA", "UPM-LEPEMC"]
    assert all(item.centro_sigla == "CTC" for item in result.departamentos)
    assert all(
        item.campus_id is None and item.status == "desconhecido" for item in result.departamentos
    )
    assert all(str(item.fonte.url) == SOURCE_URL for item in result.departamentos)
    assert all(item.fonte.consultado_em == CAPTURED_AT for item in result.departamentos)
    assert result.auditoria[0]["regulamento_url"] == SOURCE_URL + "/din.pdf/view"
    assert "Resolução" in result.auditoria[0]["rotulo_original"]


def test_preview_discloses_partial_coverage_and_unverified_fields(html):
    preview = build_preview(collect(html), FIXTURE)
    assert preview["publicavel"] is False
    assert preview["modo"] == "previa"
    assert preview["cobertura"]["status"] == "parcial_por_centro"
    assert preview["cobertura"]["centro_sigla"] == "CTC"
    assert "não autenticada" in preview["proveniencia"]["origem_arquivo"]
    assert "candidato" in preview["proveniencia"]["id"]
    assert preview["departamentos"][0]["campus_id"] is None
    assert preview["excluidos"][1]["motivo"].endswith("classificação exige revisão")


@pytest.mark.parametrize("centro", CENTROS)
def test_supports_each_center_heading_and_page(centro):
    nome, _ = CENTROS[centro]
    html = f"""<article id="content"><header>
    <h1 class="documentFirstHeading">{centro} - {nome} (Departamentos e Órgãos)</h1>
    </header><div id="content-core"><div class="entries">
    <article class="entry"><header><a href="centro.pdf">
    {centro} - {nome} (Resolução 1)</a></header></article>
    <article class="entry"><header><a href="dept.pdf">
    DXX - Departamento de Teste (Resolução 1)</a></header></article>
    </div></div></article>"""
    result = collect(html, centro)
    assert result.departamentos[0].centro_sigla == centro
    assert result.source_url.endswith(CENTROS[centro][1])


def test_keeps_name_parentheses_and_handles_hyphen_before_resolution(html):
    changed = html.replace(
        "Departamento de <strong>Informática</strong> (Resolução",
        "Departamento de Informática (Aplicada) -(Resolução",
    )
    assert collect(changed).departamentos[0].nome == "Departamento de Informática (Aplicada)"


@pytest.mark.parametrize(
    "before,after",
    [
        ('<h1 class="documentFirstHeading">', "<h1>"),
        ("CTC - CENTRO DE TECNOLOGIA (Departamentos e Órgãos)", "CSA - OUTRO CENTRO"),
        ("CTC - CENTRO DE TECNOLOGIA (Resolução", "CSA - CENTRO DE TECNOLOGIA (Resolução"),
        ('id="content-core"', 'id="other"'),
        ('class="entries"', 'class="other"'),
        ("</div></div>", "</div>"),
        (
            '<article class="entry"><header><span class="summary">',
            '<article class="unit"><header><span class="summary">',
        ),
        ("DIN - Departamento de ", "DIN Departamento de "),
        ("DIN - Departamento de <strong>Informática</strong>", "DIN - Departamento de"),
        ("DAU - Departamento", "DIN - Departamento"),
        ('href="dau.pdf/view"', 'href="din.pdf/view"'),
        ('<a href="dau.pdf/view">', '<a href="extra.pdf">EXTRA</a><a href="dau.pdf/view">'),
        ('<a href="din.pdf/view"><img', '<a href="different.pdf"><img'),
    ],
)
def test_rejects_unexpected_or_incomplete_content(html, before, after):
    with pytest.raises(DepartamentoSourceError):
        collect(html.replace(before, after))


@pytest.mark.parametrize(
    "nested",
    [
        '<article class="entry"></article>',
        '<article class="summary"></article>',
        "<article></article>",
    ],
)
def test_rejects_any_nested_article_before_another_link(html, nested):
    changed = html.replace(
        "</span></header></article>",
        nested + '<a href="hidden.pdf">XXX - Departamento de Oculto</a></span></header></article>',
        1,
    )
    with pytest.raises(DepartamentoSourceError, match="aninhado"):
        collect(changed)


@pytest.mark.parametrize(
    "href",
    [
        "https://example.org/din.pdf",
        "http://pld.uem.br/din.pdf",
        SOURCE_URL + "-other/din.pdf",
        SOURCE_URL + "/../din.pdf",
        "../din.pdf",
        "%2e%2e/din.pdf",
        "din.pdf?x=1",
        "din.pdf#view",
        "din.pdf?",
        "din.pdf#",
        "din\\file.pdf",
        "//user@pld.uem.br/din.pdf",
        "https://pld.uem.br:443" + SOURCE_URL.removeprefix("https://pld.uem.br") + "/din.pdf",
        "din pdf/view",
        "",
    ],
)
def test_rejects_unsafe_or_unexpected_urls(html, href):
    with pytest.raises(DepartamentoSourceError):
        collect(html.replace('href="din.pdf/view"', f'href="{href}"'))


def test_accepts_absolute_urls_and_stops_on_equivalent_duplicate_url(html):
    changed = html.replace('href="din.pdf/view"', f'href="{SOURCE_URL}/din.pdf/view"')
    assert collect(changed).auditoria[0]["regulamento_url"] == SOURCE_URL + "/din.pdf/view"
    with pytest.raises(DepartamentoSourceError, match="duplicada"):
        collect(changed.replace('href="dau.pdf/view"', 'href="din.pdf/view"'))


def test_requires_center_regulation_and_at_least_one_department(html):
    with pytest.raises(DepartamentoSourceError, match="ausentes"):
        collect(html.replace("CTC - CENTRO DE TECNOLOGIA (Resolução", "ORG - Instituto (Resolução"))
    with pytest.raises(DepartamentoSourceError, match="ausentes"):
        collect(
            html.replace("Departamento de ", "Instituto de ").replace(
                "Deparamento de ", "Instituto de "
            )
        )
    with pytest.raises(DepartamentoSourceError):
        collect("")
    with pytest.raises(DepartamentoSourceError, match="desconhecido"):
        collect(html, "XYZ")


def test_requires_capture_timezone(html):
    with pytest.raises(ValidationError, match="fuso"):
        collect(html, consultado_em=datetime(2026, 9, 26))


def run_cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "app.collectors.departamentos", *args],
        text=True,
        capture_output=True,
        cwd=cwd,
        check=False,
    )


def test_cli_prints_preview_without_writing_files(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[1]))
    result = run_cli(
        "--html",
        str(FIXTURE.resolve()),
        "--centro",
        "CTC",
        "--consultado-em",
        "2026-09-26T12:00:00Z",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    preview = json.loads(result.stdout)
    assert preview["publicavel"] is False
    assert len(preview["departamentos"]) == 4
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "extra",
    [
        ["--centro", "XYZ"],
        ["--consultado-em", "invalid"],
        ["--consultado-em", "2026-09-26T12:00:00"],
        ["--html", "/missing/page.html"],
    ],
)
def test_cli_reports_errors_without_partial_json(extra):
    result = run_cli(
        "--html", str(FIXTURE), "--centro", "CTC", "--consultado-em", "2026-09-26T12:00:00Z", *extra
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "error:" in result.stderr
