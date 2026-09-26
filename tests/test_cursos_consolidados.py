import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.collectors.curso_detalhes import CourseDetailSourceError
from app.collectors.cursos import collect_courses
from app.collectors.cursos_consolidados import (
    DetailCapture,
    build_batch_preview,
    load_manifest,
)

FIXTURES = Path(__file__).parent / "fixtures"
INDEX = FIXTURES / "cursos_pen.html"
DETAIL = FIXTURES / "curso_detalhe_pen.html"
MANIFEST = FIXTURES / "cursos_consolidados_manifesto.json"
CAPTURED_AT = datetime(2026, 9, 26, 12, tzinfo=UTC)
COURSES, _ = collect_courses(INDEX.read_text(encoding="utf-8"))


def capture(course, path):
    return DetailCapture(course.campus_id, course.url_detalhe, path, CAPTURED_AT)


def report(captures):
    return build_batch_preview(
        INDEX.read_text(encoding="utf-8"), captures, INDEX, MANIFEST, CAPTURED_AT
    )


def test_reports_accepted_missing_invalid_and_extra_captures(tmp_path):
    invalid = tmp_path / "invalido.html"
    invalid.write_text(
        DETAIL.read_text(encoding="utf-8").replace("Pedagogia</h3>", "Outro nome</h3>"),
        encoding="utf-8",
    )
    extra = DetailCapture(
        "sede",
        "https://www.pen.uem.br/site/public/curso/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        tmp_path / "extra.html",
        CAPTURED_AT,
    )
    preview = report(
        [
            capture(COURSES[0], DETAIL),
            capture(COURSES[1], tmp_path / "ausente.html"),
            capture(COURSES[2], invalid),
            extra,
        ]
    )

    assert preview["publicavel"] is False
    assert {key: value for key, value in preview["resumo"].items() if key != "por_campus"} == {
        "total_indice": 6,
        "total_manifesto": 4,
        "aceitos": 1,
        "sem_captura": 3,
        "arquivo_ausente": 1,
        "falha_leitura": 0,
        "invalidos": 1,
        "fora_do_indice": 1,
        "cobertura_completa": False,
    }
    assert preview["resumo"]["por_campus"]["sede"]["aceitos"] == 1
    assert preview["resumo"]["por_campus"]["car"]["invalidos"] == 1
    assert preview["resumo"]["por_campus"]["crc"]["arquivo_ausente"] == 1
    assert [item["status"] for item in preview["resultados"]] == [
        "aceito",
        "arquivo_ausente",
        "invalido",
        "sem_captura",
        "sem_captura",
        "sem_captura",
    ]
    assert preview["resultados"][0]["previa"]["curso"]["id_candidato"] == "sede-pedagogia"
    assert preview["resultados"][2]["motivo"] == "título do detalhe difere do índice"
    assert preview["fora_do_indice"][0]["url_detalhe"] == extra.url_detalhe
    assert "contato@example.org" not in json.dumps(preview, ensure_ascii=False)


def test_complete_coverage_with_distinct_valid_captures(tmp_path):
    breadcrumbs = {
        "sede": "Graduação - Campus Sede",
        "crc": "Graduação - Campus Regional de Cianorte",
        "car": "Graduação - Campus do Arenito",
        "crg": "Graduação - Campus Regional de Goioerê",
        "crv": "Graduação - Campus Regional do Vale do Ivaí",
        "cau": "Graduação - Campus Regional de Umuarama",
    }
    base = DETAIL.read_text(encoding="utf-8")
    captures = []
    for course in COURSES:
        path = tmp_path / f"{course.campus_id}.html"
        path.write_text(
            base.replace("Pedagogia</h3>", f"{course.nome}</h3>").replace(
                "Graduação - Campus Sede", breadcrumbs[course.campus_id]
            ),
            encoding="utf-8",
        )
        captures.append(capture(course, path))

    preview = report(captures)

    assert preview["resumo"]["aceitos"] == len(COURSES)
    assert preview["resumo"]["cobertura_completa"] is True
    assert preview["fora_do_indice"] == []
    assert all(item["status"] == "aceito" for item in preview["resultados"])


def test_unreadable_utf8_is_reported_without_stopping_other_courses(tmp_path):
    unreadable = tmp_path / "codificacao-invalida.html"
    unreadable.write_bytes(b"\xff")

    preview = report([capture(COURSES[0], DETAIL), capture(COURSES[1], unreadable)])

    assert preview["resumo"]["aceitos"] == 1
    assert preview["resumo"]["falha_leitura"] == 1
    assert preview["resultados"][1]["status"] == "falha_leitura"
    assert "previa" not in preview["resultados"][1]


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda data: data["detalhes"].append(data["detalhes"][0]), "duplicada"),
        (
            lambda data: data["detalhes"][0].update(consultado_em="2026-09-26T12:00:00"),
            "fuso",
        ),
        (lambda data: data["detalhes"][0].update(nome="Pedagogia"), "campos inválidos"),
    ],
)
def test_rejects_ambiguous_manifest(tmp_path, mutate, expected):
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "manifesto.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match=expected):
        load_manifest(path)


def test_manifest_resolves_paths_relative_to_its_directory(tmp_path):
    path = tmp_path / "manifesto.json"
    path.write_text(MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")

    captures = load_manifest(path)

    assert captures[0].arquivo == tmp_path / "curso_detalhe_pen.html"
    assert captures[0].consultado_em == CAPTURED_AT


def test_batch_rejects_candidate_id_collisions():
    index = INDEX.read_text(encoding="utf-8").replace(
        '<li><a href="https://www.pen.uem.br/site/public/curso/1111111111111111111111111111111111111111">Pedagogia</a></li>',
        '<li><a href="https://www.pen.uem.br/site/public/curso/1111111111111111111111111111111111111111">Pedagogia</a></li>'
        '<li><a href="https://www.pen.uem.br/site/public/curso/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">Pedagogia</a></li>',
    )

    with pytest.raises(CourseDetailSourceError, match="IDs candidatos duplicados"):
        build_batch_preview(index, [], INDEX, MANIFEST, CAPTURED_AT)


def test_batch_rejects_reusing_one_capture_for_two_courses():
    with pytest.raises(ValueError, match="arquivo de detalhe duplicado"):
        report([capture(COURSES[0], DETAIL), capture(COURSES[1], DETAIL)])


def test_cli_prints_report_without_writing_files(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[1]))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.collectors.cursos_consolidados",
            "--indice",
            str(INDEX.resolve()),
            "--manifesto",
            str(MANIFEST.resolve()),
            "--consultado-em-indice",
            "2026-09-26T12:00:00Z",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    preview = json.loads(result.stdout)
    assert preview["resumo"]["aceitos"] == 1
    assert preview["resumo"]["sem_captura"] == 5
    assert list(tmp_path.iterdir()) == []
