from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.collectors.centros import CenterSourceError, build_preview, collect_centros

FIXTURE = Path(__file__).parent / "fixtures" / "centros_pld.html"
CAPTURED_AT = datetime(2026, 9, 26, tzinfo=UTC)


def test_collects_seven_centers_from_index_only():
    candidates = collect_centros(FIXTURE.read_text(encoding="utf-8"), CAPTURED_AT)
    preview = build_preview(candidates, FIXTURE)

    assert [candidate.centro.sigla for candidate in candidates] == [
        "CCA",
        "CCB",
        "CCE",
        "CCH",
        "CCS",
        "CSA",
        "CTC",
    ]
    assert candidates[0].centro.nome == "CENTRO DE CIÊNCIAS AGRÁRIAS"
    assert candidates[-1].centro.id == "ctc"
    assert candidates[-1].url_pagina_vinculada.endswith("/centro-de-tecnologia-ctc")
    assert all(candidate.centro.fonte.source_id == "centros_pld" for candidate in candidates)
    assert preview["total"] == 7
    assert preview["publicavel"] is False
    assert preview["proveniencia"]["campi_e_departamentos"] == "não verificados neste índice"


def test_missing_or_new_center_requires_review():
    html = FIXTURE.read_text(encoding="utf-8")
    center_entry = (
        '<article class="entry"><header><a href="centro-de-tecnologia-ctc">'
        "CTC - CENTRO DE TECNOLOGIA (Departamentos e Órgãos)</a></header></article>"
    )
    missing = html.replace(center_entry, "")
    assert missing != html
    with pytest.raises(CenterSourceError, match="ausentes=\\['CTC'\\]"):
        collect_centros(missing, CAPTURED_AT)

    new = html.replace("CTC - CENTRO DE TECNOLOGIA", "CTX - CENTRO DE TECNOLOGIA")
    with pytest.raises(CenterSourceError, match="novos=\\['CTX'\\]"):
        collect_centros(new, CAPTURED_AT)


def test_duplicate_center_or_external_link_stops_preview():
    html = FIXTURE.read_text(encoding="utf-8")
    duplicate = html.replace(
        '<article class="entry"><header><a href="centro-de-tecnologia-ctc">',
        '<article class="entry"><header><a href="centro-de-ciencias-agrarias">',
    ).replace("CTC - CENTRO DE TECNOLOGIA", "CCA - CENTRO DE TECNOLOGIA")
    with pytest.raises(CenterSourceError, match="centro duplicado: CCA"):
        collect_centros(duplicate, CAPTURED_AT)

    external = html.replace('href="centro-de-tecnologia-ctc"', 'href="https://example.org/ctc"')
    with pytest.raises(CenterSourceError, match="URL de centro inesperada"):
        collect_centros(external, CAPTURED_AT)

    reused = html.replace('href="centro-de-tecnologia-ctc"', 'href="centro-de-ciencias-agrarias"')
    with pytest.raises(CenterSourceError, match="link de centro duplicado"):
        collect_centros(reused, CAPTURED_AT)


def test_changed_entry_structure_cannot_silently_drop_a_center():
    html = FIXTURE.read_text(encoding="utf-8")
    changed = html.replace(
        '<article class="entry"><header><a href="centro-de-tecnologia-ctc">',
        '<article class="unit"><header><a href="centro-de-tecnologia-ctc">',
    )
    with pytest.raises(CenterSourceError, match="ausentes=\\['CTC'\\]"):
        collect_centros(changed, CAPTURED_AT)


def test_nested_article_cannot_hide_an_unexpected_link():
    html = FIXTURE.read_text(encoding="utf-8")
    changed = html.replace(
        "</header></article>",
        '</header><article class="summary"></article>'
        '<a href="centro-de-extra">XXX - CENTRO DE EXTRA (Departamentos e Órgãos)</a>'
        "</article>",
        1,
    )
    assert changed != html

    with pytest.raises(CenterSourceError, match="entrada de centro aninhada"):
        collect_centros(changed, CAPTURED_AT)


def test_changed_center_name_is_read_from_html():
    html = FIXTURE.read_text(encoding="utf-8").replace(
        "CCA - CENTRO DE CIÊNCIAS AGRÁRIAS",
        "CCA - CENTRO DE CIÊNCIAS AMBIENTAIS",
    )

    candidates = collect_centros(html, CAPTURED_AT)

    assert candidates[0].centro.nome == "CENTRO DE CIÊNCIAS AMBIENTAIS"
