import json
import subprocess
import sys
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.collectors.cursos import collect_courses
from app.collectors.cursos_consolidados import DetailCapture, build_batch_preview
from app.review.cursos import build_course_review, load_course_preview
from app.review.previews import PreviewReviewError, load_decisions

FIXTURES = Path(__file__).parent / "fixtures"
INDEX = FIXTURES / "cursos_pen.html"
DETAIL = FIXTURES / "curso_detalhe_pen.html"
MANIFEST = FIXTURES / "cursos_consolidados_manifesto.json"
CAPTURED_AT = datetime(2026, 9, 26, 12, tzinfo=UTC)
COURSES, _ = collect_courses(INDEX.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def _batch(at: datetime = CAPTURED_AT, detail: Path | None = DETAIL) -> dict:
    captures = (
        [DetailCapture(COURSES[0].campus_id, COURSES[0].url_detalhe, detail, at)]
        if detail is not None
        else []
    )
    return build_batch_preview(INDEX.read_text(encoding="utf-8"), captures, INDEX, MANIFEST, at)


def _approve_first(template: dict) -> dict:
    decision = next(item for item in template["decisoes"] if item["tipo"] == "registro")
    decision.update(
        decisao="aprovado",
        justificativa="Detalhe acadêmico conferido com a captura.",
        evidencias=["https://www.pen.uem.br/site/public/cursos"],
        data_decisao="2026-09-26T15:00:00Z",
    )
    return template


def test_course_review_cli_reports_missing_captures_and_creates_decision_template(tmp_path):
    current = _write(tmp_path / "lote.json", _batch())
    template = tmp_path / "decisoes.json"
    command = [
        sys.executable,
        "-m",
        "app.review.cursos",
        "--atual",
        str(current),
        "--modelo-decisoes",
        str(template),
    ]

    first = subprocess.run(command, capture_output=True, text=True, check=True)
    report = json.loads(first.stdout)
    assert report["dataset"] == "cursos"
    assert report["publicavel"] is False
    assert report["comparacao"]["status"] == "sem_captura_anterior"
    assert report["comparacao"]["adicionados"] == 6
    assert len(report["modelo_decisoes"]["decisoes"]) == 1
    assert len(report["revisao"]["inconsistencias_cobertura"]) == 6
    assert "cursos da EaD não incluídos" in report["revisao"]["inconsistencias_cobertura"]
    assert json.loads(template.read_text(encoding="utf-8")) == report["modelo_decisoes"]

    second = subprocess.run(command, capture_output=True, text=True, check=False)
    assert second.returncode != 0
    assert "File exists" in second.stderr or "arquivo existe" in second.stderr

    reviewed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.review.cursos",
            "--atual",
            str(current),
            "--decisoes",
            str(template),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(reviewed.stdout)["revisao"]["registros"][0]["status"] == "pendente"


def test_course_review_uses_campus_and_url_when_name_changes(tmp_path):
    old = _batch()
    new = _batch(CAPTURED_AT + timedelta(days=1))
    new["resultados"][0]["nome"] = "Pedagogia Renovada"
    course = new["resultados"][0]["previa"]["curso"]
    course["nome"] = "Pedagogia Renovada"
    course["id_candidato"] = "sede-pedagogia-renovada"
    previous = load_course_preview(_write(tmp_path / "old.json", old))
    current = load_course_preview(_write(tmp_path / "new.json", new))

    report = build_course_review(current, previous)

    assert report["comparacao"]["adicionados"] == 0
    assert report["comparacao"]["removidos"] == 0
    assert report["comparacao"]["alterados"] == 1
    assert report["comparacao"]["mudancas"][0]["campos"]["nome"] == {
        "anterior": "Pedagogia",
        "atual": "Pedagogia Renovada",
    }


def test_course_review_treats_changed_url_as_new_entry_and_removal(tmp_path):
    previous = load_course_preview(_write(tmp_path / "old.json", _batch()))
    changed = _batch(CAPTURED_AT + timedelta(days=1))
    url = "https://www.pen.uem.br/site/public/curso/" + "a" * 40
    result = changed["resultados"][0]
    result["url_detalhe"] = url
    result["previa"]["curso"]["url_detalhe"] = url
    result["previa"]["fonte"]["url"] = url
    current = load_course_preview(_write(tmp_path / "new.json", changed))

    report = build_course_review(current, previous)

    assert report["comparacao"]["adicionados"] == 1
    assert report["comparacao"]["removidos"] == 1
    assert {item["tipo"] for item in report["modelo_decisoes"]["decisoes"]} == {
        "registro",
        "remocao",
    }


def test_course_decision_survives_capture_time_and_expires_on_academic_change(tmp_path):
    original = load_course_preview(_write(tmp_path / "old.json", _batch()))
    template = _approve_first(build_course_review(original)["modelo_decisoes"])
    decisions = load_decisions(_write(tmp_path / "decisions.json", template), "cursos")
    next_data = _batch(CAPTURED_AT + timedelta(days=1))
    same = load_course_preview(_write(tmp_path / "same.json", next_data))

    retained = build_course_review(same, original, decisions)
    assert retained["comparacao"]["status"] == "sem_alteracoes"
    assert retained["revisao"]["registros"][0]["status"] == "aprovado"
    assert retained["revisao"]["todos_itens_aprovados"] is False

    next_data["resultados"][0]["previa"]["curso"]["informacoes_academicas"][0]["turno"] = "Matutino"
    modified = load_course_preview(_write(tmp_path / "modified.json", next_data))
    expired = build_course_review(modified, original, decisions)
    assert expired["comparacao"]["alterados"] == 1
    assert expired["revisao"]["registros"][0]["status"] == "decisao_desatualizada"


def test_course_decision_expires_when_detail_provenance_changes(tmp_path):
    original = load_course_preview(_write(tmp_path / "old.json", _batch()))
    template = _approve_first(build_course_review(original)["modelo_decisoes"])
    decisions = load_decisions(_write(tmp_path / "decisions.json", template), "cursos")
    changed = _batch(CAPTURED_AT + timedelta(days=1))
    changed["resultados"][0]["previa"]["proveniencia"]["unidade"] = (
        "interpretação acadêmica revisada"
    )
    current = load_course_preview(_write(tmp_path / "new.json", changed))

    report = build_course_review(current, original, decisions)

    assert report["comparacao"]["alterados"] == 1
    assert report["revisao"]["registros"][0]["status"] == "decisao_desatualizada"


def test_missing_detail_does_not_create_false_course_removal(tmp_path):
    old = load_course_preview(_write(tmp_path / "old.json", _batch()))
    template = _approve_first(build_course_review(old)["modelo_decisoes"])
    decisions = load_decisions(_write(tmp_path / "decisions.json", template), "cursos")
    missing = load_course_preview(
        _write(tmp_path / "missing.json", _batch(CAPTURED_AT + timedelta(days=1), None))
    )

    report = build_course_review(missing, old, decisions)

    assert report["comparacao"]["removidos"] == 0
    assert report["comparacao"]["alterados"] == 1
    assert report["revisao"]["registros"] == []
    assert len(report["revisao"]["decisoes_obsoletas"]) == 1
    assert any(
        "sem_captura: sede|" in item for item in report["revisao"]["inconsistencias_cobertura"]
    )


def test_result_order_and_capture_files_do_not_change_decisions(tmp_path):
    old_data = _batch()
    previous = load_course_preview(_write(tmp_path / "old.json", old_data))
    changed = deepcopy(old_data)
    changed["resultados"].reverse()
    changed["resultados"][-1]["arquivo"] = "outra-captura.html"
    changed["resultados"][-1]["previa"]["entrada"]["detalhe"] = "outra-captura.html"
    current = load_course_preview(_write(tmp_path / "new.json", changed))

    report = build_course_review(current, previous)

    assert report["comparacao"]["status"] == "sem_alteracoes"
    assert report["comparacao"]["alterados"] == 0


def test_invalid_and_out_of_index_captures_remain_coverage_issues(tmp_path):
    invalid = tmp_path / "invalido.html"
    invalid.write_text(
        DETAIL.read_text(encoding="utf-8").replace("Pedagogia</h3>", "Outro nome</h3>"),
        encoding="utf-8",
    )
    extra = DetailCapture(
        "sede",
        "https://www.pen.uem.br/site/public/curso/" + "a" * 40,
        tmp_path / "extra.html",
        CAPTURED_AT,
    )
    captures = [
        DetailCapture(COURSES[0].campus_id, COURSES[0].url_detalhe, DETAIL, CAPTURED_AT),
        DetailCapture(COURSES[1].campus_id, COURSES[1].url_detalhe, invalid, CAPTURED_AT),
        extra,
    ]
    batch = build_batch_preview(
        INDEX.read_text(encoding="utf-8"), captures, INDEX, MANIFEST, CAPTURED_AT
    )
    current = load_course_preview(_write(tmp_path / "batch.json", batch))

    report = build_course_review(current)

    assert len(report["modelo_decisoes"]["decisoes"]) == 1
    issues = report["revisao"]["inconsistencias_cobertura"]
    assert any(issue.startswith("invalido: crc|") for issue in issues)
    assert any(issue.startswith("fora_do_indice: sede|") for issue in issues)
    assert "título do detalhe difere do índice" not in json.dumps(report, ensure_ascii=False)


def test_extra_capture_changes_coverage_even_when_index_entries_do_not(tmp_path):
    previous = load_course_preview(_write(tmp_path / "old.json", _batch()))
    captures = [
        DetailCapture(COURSES[0].campus_id, COURSES[0].url_detalhe, DETAIL, CAPTURED_AT),
        DetailCapture(
            "sede",
            "https://www.pen.uem.br/site/public/curso/" + "a" * 40,
            tmp_path / "extra.html",
            CAPTURED_AT,
        ),
    ]
    changed = build_batch_preview(
        INDEX.read_text(encoding="utf-8"), captures, INDEX, MANIFEST, CAPTURED_AT
    )
    current = load_course_preview(_write(tmp_path / "new.json", changed))

    report = build_course_review(current, previous)

    assert report["comparacao"]["status"] == "revisar"
    assert report["comparacao"]["cobertura_alterada"] is True
    assert report["comparacao"]["adicionados"] == 0
    assert report["comparacao"]["removidos"] == 0
    assert report["comparacao"]["alterados"] == 0


def test_complete_presential_captures_still_do_not_approve_ead(tmp_path):
    breadcrumbs = {
        "sede": "Graduação - Campus Sede",
        "crc": "Graduação - Campus Regional de Cianorte",
        "car": "Graduação - Campus do Arenito",
        "crg": "Graduação - Campus Regional de Goioerê",
        "crv": "Graduação - Campus Regional do Vale do Ivaí",
        "cau": "Graduação - Campus Regional de Umuarama",
    }
    captures = []
    base = DETAIL.read_text(encoding="utf-8")
    for course in COURSES:
        path = tmp_path / f"{course.campus_id}.html"
        path.write_text(
            base.replace("Pedagogia</h3>", f"{course.nome}</h3>").replace(
                "Graduação - Campus Sede", breadcrumbs[course.campus_id]
            ),
            encoding="utf-8",
        )
        captures.append(DetailCapture(course.campus_id, course.url_detalhe, path, CAPTURED_AT))
    batch = build_batch_preview(
        INDEX.read_text(encoding="utf-8"), captures, INDEX, MANIFEST, CAPTURED_AT
    )
    current = load_course_preview(_write(tmp_path / "complete.json", batch))
    template = build_course_review(current)["modelo_decisoes"]
    for decision in template["decisoes"]:
        decision.update(
            decisao="aprovado",
            justificativa="Detalhe acadêmico conferido.",
            evidencias=["https://www.pen.uem.br/site/public/cursos"],
            data_decisao="2026-09-26T15:00:00Z",
        )
    decisions = load_decisions(_write(tmp_path / "decisions.json", template), "cursos")

    report = build_course_review(current, decisions=decisions)

    assert batch["resumo"]["cobertura_completa"] is True
    assert report["revisao"]["aprovados"] == len(COURSES)
    assert report["revisao"]["inconsistencias_cobertura"] == ["cursos da EaD não incluídos"]
    assert report["revisao"]["todos_itens_aprovados"] is False
    assert report["publicavel"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "summary",
        "duplicate",
        "wrong_detail_url",
        "wrong_campus",
        "ead_included",
        "academic_contact",
        "candidate_id",
        "unexpected_field",
        "missing_campus",
        "duplicate_candidate_id",
        "reused_file",
    ],
)
def test_course_review_rejects_inconsistent_batch(tmp_path, mutation):
    preview = _batch()
    first = preview["resultados"][0]
    if mutation == "summary":
        preview["resumo"]["aceitos"] = 2
    elif mutation == "duplicate":
        preview["resultados"].append(deepcopy(first))
    elif mutation == "wrong_detail_url":
        first["previa"]["fonte"]["url"] = "https://www.pen.uem.br/site/public/curso/" + "a" * 40
    elif mutation == "wrong_campus":
        first["previa"]["curso"]["campus_id"] = "crc"
    elif mutation == "ead_included":
        preview["ead"]["cursos_incluidos"] = True
    elif mutation == "academic_contact":
        first["previa"]["curso"]["informacoes_academicas"][0]["turno"] = "contato@example.org"
    elif mutation == "candidate_id":
        first["previa"]["curso"]["id_candidato"] = "outro"
    elif mutation == "missing_campus":
        preview["resultados"].pop()
    elif mutation == "duplicate_candidate_id":
        preview["resultados"][1]["campus_id"] = "sede"
        preview["resultados"][1]["nome"] = "Pedagogia"
    elif mutation == "reused_file":
        preview["fora_do_indice"] = [
            {
                "campus_id": "sede",
                "url_detalhe": "https://www.pen.uem.br/site/public/curso/" + "a" * 40,
                "arquivo": first["arquivo"],
                "consultado_em": first["consultado_em"],
                "status": "fora_do_indice",
            }
        ]
    else:
        first["previa"]["curso"]["coordenacao"] = "Pessoa Exemplo"

    with pytest.raises(PreviewReviewError):
        load_course_preview(_write(tmp_path / "invalid.json", preview))
