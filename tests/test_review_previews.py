import json
import subprocess
import sys
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.collectors.campi import build_preview as campus_preview
from app.collectors.campi import collect_campi
from app.collectors.centros import build_preview as center_preview
from app.collectors.centros import collect_centros
from app.review.previews import PreviewReviewError, build_review, load_decisions, load_preview

FIXTURES = Path(__file__).parent / "fixtures"
CAPTURED_AT = datetime(2026, 9, 26, 12, tzinfo=UTC)


def _write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _campi(at: datetime = CAPTURED_AT) -> dict:
    source = FIXTURES / "campi_page.html"
    return campus_preview(collect_campi(source.read_text(encoding="utf-8"), at), source)


def _centros(at: datetime = CAPTURED_AT) -> dict:
    source = FIXTURES / "centros_pld.html"
    return center_preview(collect_centros(source.read_text(encoding="utf-8"), at), source)


def test_first_review_lists_all_campi_as_pending_and_never_publishes(tmp_path):
    current = load_preview(_write_json(tmp_path / "campi.json", _campi()), "campi")

    report = build_review(current)

    assert report["publicavel"] is False
    assert report["comparacao"]["status"] == "sem_captura_anterior"
    assert report["comparacao"]["adicionados"] == 7
    assert report["revisao"]["pendentes"] == 7
    assert report["revisao"]["todos_itens_aprovados"] is False
    assert len(report["modelo_decisoes"]["decisoes"]) == 7


def test_change_of_name_and_link_appears_in_center_diff(tmp_path):
    old = _centros()
    new = deepcopy(old)
    new["centros"][0]["nome"] = "CENTRO DE CIÊNCIAS AMBIENTAIS"
    new["centros"][0]["url_pagina_vinculada"] = (
        "https://pld.uem.br/dvl/regulamentos/centros-de-ensino/centro-de-ciencias-ambientais"
    )
    new["centros"][0]["fonte"]["consultado_em"] = (CAPTURED_AT + timedelta(days=1)).isoformat()
    for entry in new["centros"][1:]:
        entry["fonte"]["consultado_em"] = (CAPTURED_AT + timedelta(days=1)).isoformat()
    previous = load_preview(_write_json(tmp_path / "old.json", old), "centros")
    current = load_preview(_write_json(tmp_path / "new.json", new), "centros")

    report = build_review(current, previous)

    assert report["comparacao"]["status"] == "revisar"
    assert report["comparacao"]["alterados"] == 1
    assert report["comparacao"]["inalterados"] == 6
    changed = report["comparacao"]["mudancas"][0]
    assert changed["id"] == "cca"
    assert set(changed["campos"]) == {"nome", "url_pagina_vinculada"}
    assert report["revisao"]["inconsistencias_cobertura"] == []


def test_decision_survives_new_capture_time_but_not_changed_record(tmp_path):
    old = _campi()
    updated = _campi(CAPTURED_AT + timedelta(days=1))
    old_preview = load_preview(_write_json(tmp_path / "old.json", old), "campi")
    new_preview = load_preview(_write_json(tmp_path / "new.json", updated), "campi")
    template = build_review(old_preview)["modelo_decisoes"]
    approved = next(item for item in template["decisoes"] if item["id"] == "crc")
    approved.update(
        decisao="aprovado",
        justificativa="Conferido com a tabela revisada.",
        evidencias=["docs/campus-identifiers.md"],
        data_decisao="2026-09-26T15:00:00Z",
    )
    decisions = load_decisions(_write_json(tmp_path / "decisions.json", template), "campi")

    same_data = build_review(new_preview, old_preview, decisions)
    assert same_data["comparacao"]["status"] == "sem_alteracoes"
    assert (
        next(item for item in same_data["revisao"]["registros"] if item["id"] == "crc")["status"]
        == "aprovado"
    )
    assert same_data["revisao"]["aprovados"] == 1
    assert next(item for item in same_data["revisao"]["registros"] if item["id"] == "crc")[
        "evidencias"
    ] == ["docs/campus-identifiers.md"]

    updated["campi"][1]["nome"] = "Novo nome de Cianorte"
    changed = load_preview(_write_json(tmp_path / "changed.json", updated), "campi")
    stale = build_review(changed, old_preview, decisions)
    assert stale["comparacao"]["alterados"] == 1
    assert (
        next(item for item in stale["revisao"]["registros"] if item["id"] == "crc")["status"]
        == "decisao_desatualizada"
    )


def test_removal_requires_own_decision_and_reports_missing_coverage(tmp_path):
    old = _campi()
    new = deepcopy(old)
    new["campi"] = [item for item in new["campi"] if item["id"] != "crc"]
    previous = load_preview(_write_json(tmp_path / "old.json", old), "campi")
    current = load_preview(_write_json(tmp_path / "new.json", new), "campi")

    report = build_review(current, previous)

    assert report["comparacao"]["removidos"] == 1
    assert report["comparacao"]["mudancas"][0]["id"] == "crc"
    assert {item["tipo"] for item in report["revisao"]["registros"] if item["id"] == "crc"} == {
        "remocao"
    }
    assert report["revisao"]["inconsistencias_cobertura"] == ["ausentes: ['crc']"]
    assert report["revisao"]["todos_itens_aprovados"] is False


def test_changed_provenance_invalidates_decision(tmp_path):
    old = _campi()
    current = deepcopy(old)
    current["proveniencia"]["nomes_dos_links_verificados"] = True
    old_preview = load_preview(_write_json(tmp_path / "old.json", old), "campi")
    new_preview = load_preview(_write_json(tmp_path / "new.json", current), "campi")
    template = build_review(old_preview)["modelo_decisoes"]
    approved = template["decisoes"][0]
    approved.update(
        decisao="aprovado",
        justificativa="Conferido com a página.",
        evidencias=["https://www.uem.br/a-uem/campus"],
        data_decisao="2026-09-26T15:00:00Z",
    )
    decisions = load_decisions(_write_json(tmp_path / "decisions.json", template), "campi")

    report = build_review(new_preview, old_preview, decisions)

    assert report["comparacao"]["status"] == "revisar"
    assert report["comparacao"]["proveniencia_alterada"] is True
    assert report["comparacao"]["alterados"] == 0
    assert report["revisao"]["registros"][0]["status"] == "decisao_desatualizada"


def test_all_decisions_approved_still_do_not_publish(tmp_path):
    current = load_preview(_write_json(tmp_path / "campi.json", _campi()), "campi")
    template = build_review(current)["modelo_decisoes"]
    for decision in template["decisoes"]:
        decision.update(
            decisao="aprovado",
            justificativa="Conferido com a tabela de identificadores.",
            evidencias=["docs/campus-identifiers.md"],
            data_decisao="2026-09-26T15:00:00Z",
        )
    decisions = load_decisions(_write_json(tmp_path / "decisions.json", template), "campi")

    report = build_review(current, decisions=decisions)

    assert report["revisao"]["aprovados"] == 7
    assert report["revisao"]["todos_itens_aprovados"] is True
    assert report["publicavel"] is False


def test_center_id_must_match_sigla_even_with_complete_coverage(tmp_path):
    wrong_id = _centros()
    wrong_id["centros"][0]["id"] = "wrong-id"

    with pytest.raises(PreviewReviewError, match="ID de centro não corresponde à sigla"):
        load_preview(_write_json(tmp_path / "wrong-id.json", wrong_id), "centros")


def test_invalid_preview_or_decision_is_rejected(tmp_path):
    preview = _centros()
    preview["centros"].append(deepcopy(preview["centros"][0]))
    preview["total"] += 1
    with pytest.raises(PreviewReviewError, match="ID duplicado"):
        load_preview(_write_json(tmp_path / "duplicate.json", preview), "centros")

    invalid_url = _centros()
    invalid_url["centros"][0]["url_pagina_vinculada"] = "https://[invalid"
    with pytest.raises(PreviewReviewError, match="link de centro"):
        load_preview(_write_json(tmp_path / "invalid-url.json", invalid_url), "centros")

    too_large = tmp_path / "malformed.json"
    too_large.write_text('{"number":' + "1" * 5000 + "}", encoding="utf-8")
    with pytest.raises(PreviewReviewError, match="JSON válido"):
        load_preview(too_large, "centros")

    decisions = build_review(load_preview(_write_json(tmp_path / "campi.json", _campi()), "campi"))[
        "modelo_decisoes"
    ]
    decisions["decisoes"][0]["decisao"] = ["aprovado"]
    with pytest.raises(PreviewReviewError, match="decisão desconhecida"):
        load_decisions(_write_json(tmp_path / "invalid.json", decisions), "campi")


def test_cli_creates_decision_template_without_overwriting(tmp_path):
    current = _write_json(tmp_path / "campi.json", _campi())
    template = tmp_path / "decisoes.json"
    command = [
        sys.executable,
        "-m",
        "app.review.previews",
        "--dataset",
        "campi",
        "--atual",
        str(current),
        "--modelo-decisoes",
        str(template),
    ]

    first = subprocess.run(command, capture_output=True, text=True, check=True)
    assert json.loads(first.stdout)["publicavel"] is False
    assert len(json.loads(template.read_text(encoding="utf-8"))["decisoes"]) == 7
    second = subprocess.run(command, capture_output=True, text=True, check=False)
    assert second.returncode != 0
    assert "File exists" in second.stderr or "arquivo existe" in second.stderr
