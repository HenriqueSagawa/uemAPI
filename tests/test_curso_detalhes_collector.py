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


def test_unknown_html_label_stops_before_personal_data():
    detail = DETAIL.read_text(encoding="utf-8").replace(
        "<b>Coordenação:</b>", "<b>Responsável pelo curso:</b>"
    )
    preview = build_preview(collect(detail=detail), INDEX, DETAIL)

    assert preview["curso"]["informacoes_academicas"][1]["habilitacoes"] == ["Licenciatura"]
    assert "Pessoa Exemplo" not in json.dumps(preview, ensure_ascii=False)
    assert "contato@example.org" not in json.dumps(preview, ensure_ascii=False)


def test_known_personal_label_on_same_html_line_stops_academic_value():
    detail = DETAIL.read_text(encoding="utf-8").replace(
        "<b>Habilitação:</b> Licenciatura</p>\n            <p><b>Coordenação:</b>",
        "<b>Habilitação:</b> Licenciatura <b>Coordenação:</b>",
    )
    preview = build_preview(collect(detail=detail), INDEX, DETAIL)

    assert preview["curso"]["informacoes_academicas"][1]["habilitacoes"] == ["Licenciatura"]
    assert "Pessoa Exemplo" not in json.dumps(preview, ensure_ascii=False)
    assert "contato@example.org" not in json.dumps(preview, ensure_ascii=False)


def test_html_source_line_breaks_do_not_split_academic_values():
    detail = (
        DETAIL.read_text(encoding="utf-8")
        .replace("Integral<br>", "Vespertino ou\n Noturno<br>")
        .replace("Licenciado em Pedagogia<br>", "Licenciado em\n Pedagogia<br>")
    )
    blocks = collect(detail=detail).blocks

    assert blocks[0].turno == "Vespertino ou Noturno"
    assert blocks[0].graus_academicos == ["Licenciado em Pedagogia"]


def test_rejects_contact_in_academic_value():
    detail = DETAIL.read_text(encoding="utf-8").replace(
        "<b>Habilitação:</b> Licenciatura</p>",
        "<b>Habilitação:</b> Licenciatura, contato@example.org</p>",
    )
    with pytest.raises(CourseDetailSourceError, match="contato"):
        collect(detail=detail)


def test_rejects_unlabelled_text_after_academic_value():
    detail = DETAIL.read_text(encoding="utf-8").replace(
        "<b>Habilitação:</b> Licenciatura</p>",
        "<b>Habilitação:</b> Licenciatura<br>Pessoa Exemplo</p>",
    )
    with pytest.raises(CourseDetailSourceError, match="ambíguo"):
        collect(detail=detail)


@pytest.mark.parametrize(
    "deadline_label",
    [
        "Prazo Mínimo",
        "Prazo de Conclusão",
        "Prazo Mínimo de Conclusão",
        "Prazo Máximo de Conclusão",
    ],
)
def test_academic_deadline_before_degree_is_ignored_without_stopping(deadline_label):
    detail = DETAIL.read_text(encoding="utf-8").replace(
        "<p><b>Grau Acadêmico:</b>",
        f"<p><b>{deadline_label}:</b> 4 a 7 anos</p><p><b>Grau Acadêmico:</b>",
    )
    preview = build_preview(collect(detail=detail), INDEX, DETAIL)

    assert preview["curso"]["informacoes_academicas"][0]["graus_academicos"] == [
        "Licenciado em Pedagogia"
    ]
    assert "4 a 7 anos" not in json.dumps(preview, ensure_ascii=False)


def test_deadline_list_with_colons_does_not_hide_following_degree():
    detail = DETAIL.read_text(encoding="utf-8").replace(
        "<p><b>Grau Acadêmico:</b>",
        "<p><b>Prazo de Conclusão:</b></p>"
        "<ul><li>Licenciatura - Mínimo: 4 anos e Máximo: 7 anos</li></ul>"
        "<p><b>Grau Acadêmico:</b>",
    )
    blocks = collect(detail=detail).blocks

    assert blocks[0].graus_academicos == ["Licenciado em Pedagogia"]
    assert blocks[0].habilitacoes == ["Licenciatura", "Bacharelado em Ensino (opções: A e B)"]


def test_br_separated_dashed_habilitations_keep_degree_after_deadline():
    detail = DETAIL.read_text(encoding="utf-8")
    start = detail.index("            <p><b>Turno:")
    end = detail.index("            <p><b>Coordenação:")
    detail = (
        detail[:start] + "<p><b>Habilitações:</b><br />\n"
        "- Licenciatura em Área A (Matutino)<br />\n"
        "- Bacharelado em Área B (Matutino)<br />\n"
        "- Licenciado em Área C (Noturno)<br />\n"
        "- Licenciado em Área D (Noturno)<br />\n"
        "<br /><b>Prazo de Conclusão:</b><br />\n"
        "- Licenciatura em Área A - Mínimo: 4 anos e Máximo: 7 anos<br />\n"
        "<br /><b>Grau Acadêmico:</b> Licenciado em Pedagogia</p>\n" + detail[end:]
    )
    preview = build_preview(collect(detail=detail), INDEX, DETAIL)
    academic = preview["curso"]["informacoes_academicas"]

    assert academic == [
        {
            "turno": None,
            "habilitacoes": [
                "Licenciatura em Área A (Matutino)",
                "Bacharelado em Área B (Matutino)",
                "Licenciado em Área C (Noturno)",
                "Licenciado em Área D (Noturno)",
            ],
            "graus_academicos": ["Licenciado em Pedagogia"],
        }
    ]
    assert "Mínimo" not in json.dumps(preview, ensure_ascii=False)
    assert "contato@example.org" not in json.dumps(preview, ensure_ascii=False)


def test_br_separated_dashed_degree_items_are_preserved():
    detail = DETAIL.read_text(encoding="utf-8").replace(
        "<b>Grau Acadêmico:</b> Licenciado em Pedagogia<br>",
        "<b>Grau Acadêmico:</b><br>- Licenciado em Pedagogia<br>- Bacharel em Educação<br>",
    )
    assert collect(detail=detail).blocks[0].graus_academicos == [
        "Licenciado em Pedagogia",
        "Bacharel em Educação",
    ]


def test_br_separated_dashed_contact_is_rejected():
    detail = DETAIL.read_text(encoding="utf-8").replace(
        "<b>Habilitação:</b> Licenciatura</p>",
        "<b>Habilitação:</b> Licenciatura<br>- contato@example.org</p>",
    )
    with pytest.raises(CourseDetailSourceError, match="contato"):
        collect(detail=detail)


def test_dashed_text_in_new_paragraph_is_still_ambiguous():
    detail = DETAIL.read_text(encoding="utf-8").replace(
        "<b>Habilitação:</b> Licenciatura</p>",
        "<b>Habilitação:</b> Licenciatura</p><p>- Pessoa Exemplo</p>",
    )
    with pytest.raises(CourseDetailSourceError, match="ambíguo"):
        collect(detail=detail)


def test_personal_label_after_deadline_still_stops_before_following_degree():
    detail = DETAIL.read_text(encoding="utf-8").replace(
        "<p><b>Grau Acadêmico:</b>",
        "<p><b>Prazo de Conclusão:</b> 4 a 7 anos</p>"
        "<p><b>Responsável pelo curso:</b> Pessoa Exemplo, contato@example.org</p>"
        "<p><b>Grau Acadêmico:</b>",
    )
    preview = build_preview(collect(detail=detail), INDEX, DETAIL)

    assert preview["curso"]["informacoes_academicas"][0]["graus_academicos"] == []
    assert "Pessoa Exemplo" not in json.dumps(preview, ensure_ascii=False)


def test_unrecognized_deadline_label_requires_review():
    detail = DETAIL.read_text(encoding="utf-8").replace(
        "<p><b>Grau Acadêmico:</b>",
        "<p><b>Prazo de Integralização:</b> 4 a 7 anos</p><p><b>Grau Acadêmico:</b>",
    )
    with pytest.raises(CourseDetailSourceError, match="prazo acadêmico não reconhecido"):
        collect(detail=detail)


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
