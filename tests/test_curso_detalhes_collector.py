import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.collectors.curso_detalhes import (
    CourseDetailSourceError,
    build_preview,
    collect_course_detail,
)

FIXTURES = Path(__file__).parent / "fixtures"
INDEX = FIXTURES / "cursos_pen.html"
DETAIL = FIXTURES / "curso_detalhe_pen.html"
URL = "https://www.pen.uem.br/site/public/curso/1111111111111111111111111111111111111111"
CAPTURED_AT = datetime(2026, 9, 26, tzinfo=UTC)


def collect(index=None, detail=None, campus="sede", url=URL, captured_at=CAPTURED_AT):
    return collect_course_detail(
        INDEX.read_text(encoding="utf-8") if index is None else index,
        DETAIL.read_text(encoding="utf-8") if detail is None else detail,
        campus,
        url,
        captured_at,
    )


def test_matches_index_and_preserves_academic_blocks_without_personal_data():
    result = collect()
    preview = build_preview(result, INDEX, DETAIL)

    assert result.id_candidato == "sede-pedagogia"
    assert result.course.nome == "Pedagogia"
    assert str(result.fonte.url) == URL
    assert preview["publicavel"] is False
    assert preview["curso"]["informacoes_academicas"] == [
        {
            "turno": "Integral",
            "habilitacoes": ["Licenciatura", "Bacharelado em Ensino (opções: A e B)"],
            "graus_academicos": ["Licenciado em Pedagogia"],
        },
        {"turno": "Noturno", "habilitacoes": ["Licenciatura"], "graus_academicos": []},
    ]
    assert "contato@example.org" not in json.dumps(preview, ensure_ascii=False)
    assert "Texto que não faz parte da prévia" not in json.dumps(preview, ensure_ascii=False)


@pytest.mark.parametrize(
    "detail,expected",
    [
        ("", "estrutura"),
        (DETAIL.read_text(encoding="utf-8").replace("Pedagogia</h3>", "Filosofia</h3>"), "título"),
        (
            DETAIL.read_text(encoding="utf-8").replace(
                "Graduação - Campus Sede", "Graduação - Campus Regional de Umuarama"
            ),
            "câmpus",
        ),
        (DETAIL.read_text(encoding="utf-8").replace("w-full my-6", "w-full other"), "estrutura"),
        (
            DETAIL.read_text(encoding="utf-8").replace(
                '<div class="flex flex-col w-full my-6">',
                '<div class="flex flex-col w-full my-6"></div>'
                '<div class="flex flex-col w-full my-6">',
            ),
            "estrutura",
        ),
    ],
)
def test_rejects_mismatched_or_changed_detail(detail, expected):
    with pytest.raises(CourseDetailSourceError, match=expected):
        collect(detail=detail)


def test_requires_index_match_and_unique_candidate_ids():
    with pytest.raises(CourseDetailSourceError, match="não encontrado"):
        collect(campus="crc")
    with pytest.raises(CourseDetailSourceError, match="URL"):
        collect(url="https://example.org/course")
    index = INDEX.read_text(encoding="utf-8").replace(
        '<li><a href="' + URL + '">Pedagogia</a></li>',
        '<li><a href="' + URL + '">Pedagogia</a></li>'
        '<li><a href="https://www.pen.uem.br/site/public/curso/'
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">Pedagogia</a></li>',
    )
    with pytest.raises(CourseDetailSourceError, match="IDs candidatos duplicados"):
        collect(index=index)


def test_requires_capture_timezone():
    with pytest.raises(ValidationError, match="fuso"):
        collect(captured_at=datetime(2026, 9, 26))


def test_cli_prints_preview_without_writing_files(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[1]))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.collectors.curso_detalhes",
            "--indice",
            str(INDEX.resolve()),
            "--html",
            str(DETAIL.resolve()),
            "--campus",
            "sede",
            "--url",
            URL,
            "--consultado-em",
            "2026-09-26T12:00:00Z",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["curso"]["id_candidato"] == "sede-pedagogia"
    assert list(tmp_path.iterdir()) == []
