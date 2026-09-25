from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.collectors.campi import CampusSourceError, build_preview, collect_campi

FIXTURE = Path(__file__).parent / "fixtures" / "campi_page.html"


def test_collector_builds_seven_candidates_from_local_html():
    html = FIXTURE.read_text(encoding="utf-8")

    campi = collect_campi(html, datetime(2026, 9, 25, tzinfo=UTC))

    assert len(campi) == 7
    assert {campus.id for campus in campi} == {
        "sede",
        "crc",
        "crg",
        "car",
        "crn",
        "cau",
        "crv",
    }
    assert next(campus for campus in campi if campus.id == "sede").sigla is None
    assert next(campus for campus in campi if campus.id == "crn").cidade == "Diamante do Norte"
    assert all(campus.fonte.source_id == "campi_uem" for campus in campi)


def test_collector_stops_when_regional_list_changes():
    html = FIXTURE.read_text(encoding="utf-8").replace("Umuarama", "Paranavaí")

    with pytest.raises(CampusSourceError, match="municípios regionais"):
        collect_campi(html, datetime(2026, 9, 25, tzinfo=UTC))


def test_preview_discloses_which_fields_the_html_does_not_validate():
    html = FIXTURE.read_text(encoding="utf-8")
    campi = collect_campi(html, datetime(2026, 9, 25, tzinfo=UTC))

    preview = build_preview(campi, FIXTURE)

    assert preview["publicavel"] is False
    assert preview["proveniencia"]["nomes_dos_links_verificados"] is False
    assert preview["proveniencia"]["definido_no_mapeamento_local"] == [
        "id",
        "nome",
        "sigla",
        "associação de cada câmpus ao município",
    ]
