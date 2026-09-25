from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.collectors.cursos import CourseSourceError, build_preview, collect_courses

FIXTURE = Path(__file__).parent / "fixtures" / "cursos_pen.html"


def test_courses_remain_separate_by_campus_and_ead_is_excluded():
    html = FIXTURE.read_text(encoding="utf-8")

    courses, nead_url = collect_courses(html)
    preview = build_preview(courses, nead_url, FIXTURE, datetime(2026, 9, 25, tzinfo=UTC))

    assert [
        (course.nome, course.campus_id) for course in courses if course.nome == "Pedagogia"
    ] == [
        ("Pedagogia", "sede"),
        ("Pedagogia", "crv"),
    ]
    assert preview["publicavel"] is False
    assert preview["total"] == 6
    assert preview["ead"]["cursos_incluidos"] is False
    assert preview["comparacao"]["status"] == "sem_captura_anterior"
    assert preview["comparacao"]["revisao_necessaria"] is True
    assert "ID estável de curso" in preview["proveniencia"]["pendente"]
    assert "id" not in preview["cursos"][0]


def test_unknown_campus_stops_preview():
    html = FIXTURE.read_text(encoding="utf-8").replace("Ivaiporã/PR", "Paranavaí/PR")

    with pytest.raises(CourseSourceError, match="câmpus desconhecido"):
        collect_courses(html)


def test_unexpected_course_url_stops_preview():
    html = FIXTURE.read_text(encoding="utf-8").replace(
        "https://www.pen.uem.br/site/public/curso/1111111111111111111111111111111111111111",
        "https://example.org/curso/1111111111111111111111111111111111111111",
    )

    with pytest.raises(CourseSourceError, match="URL de detalhe inesperada"):
        collect_courses(html)


def test_missing_ead_section_stops_preview():
    html = FIXTURE.read_text(encoding="utf-8").replace(
        "Modalidade de Educação a Distância", "Outros cursos"
    )

    with pytest.raises(CourseSourceError, match="link para os cursos da EaD"):
        collect_courses(html)


def test_heading_css_change_does_not_drop_courses():
    html = FIXTURE.read_text(encoding="utf-8").replace("text-xl", "text-lg")

    courses, _ = collect_courses(html)

    assert len(courses) == 6


def test_course_link_outside_known_section_stops_preview():
    html = FIXTURE.read_text(encoding="utf-8").replace(
        '<p class="text-xl mb-3">Campus Sede - Maringá/PR</p>',
        '<div class="text-xl mb-3">Campus Sede - Maringá/PR</div>',
    )

    with pytest.raises(CourseSourceError, match="fora de uma seção conhecida"):
        collect_courses(html)


def test_missing_campus_section_stops_preview():
    html = FIXTURE.read_text(encoding="utf-8")
    section = (
        '      <p class="text-xl mb-3">Câmpus Regional do Vale do Ivaí - Ivaiporã/PR</p>\n'
        "      <ul>\n"
        '        <li><a href="https://www.pen.uem.br/site/public/curso/'
        '2222222222222222222222222222222222222222">Pedagogia</a></li>\n'
        "      </ul>\n"
    )
    assert section in html

    with pytest.raises(CourseSourceError, match="ausentes=\\['crv'\\]"):
        collect_courses(html.replace(section, ""))


def test_intervening_title_stops_campus_assignment():
    html = FIXTURE.read_text(encoding="utf-8").replace(
        '<p class="text-xl mb-3">Campus Sede - Maringá/PR</p>',
        '<p class="text-xl mb-3">Campus Sede - Maringá/PR</p><h3>Outros assuntos</h3>',
    )

    with pytest.raises(CourseSourceError, match="seção interrompida"):
        collect_courses(html)


def test_relative_course_link_outside_section_stops_preview():
    html = FIXTURE.read_text(encoding="utf-8").replace(
        '<p class="text-xl mb-3">Campus Sede - Maringá/PR</p>',
        '<div class="text-xl mb-3">Campus Sede - Maringá/PR</div>',
    )
    html = html.replace(
        "https://www.pen.uem.br/site/public/curso/1111111111111111111111111111111111111111",
        "/site/public/curso/1111111111111111111111111111111111111111",
    )

    with pytest.raises(CourseSourceError, match="fora de uma seção conhecida"):
        collect_courses(html)


def test_relative_course_link_is_normalized_in_known_section():
    url = "https://www.pen.uem.br/site/public/curso/1111111111111111111111111111111111111111"
    html = FIXTURE.read_text(encoding="utf-8").replace(
        url, "/site/public/curso/1111111111111111111111111111111111111111"
    )

    courses, _ = collect_courses(html)

    assert courses[0].url_detalhe == url


def test_removed_course_in_existing_section_is_flagged():
    current_html = FIXTURE.read_text(encoding="utf-8")
    extra_url = "https://www.pen.uem.br/site/public/curso/7777777777777777777777777777777777777777"
    previous_html = current_html.replace(
        "</a></li>\n      </ul>",
        f'</a></li>\n        <li><a href="{extra_url}">Curso anterior</a></li>\n      </ul>',
        1,
    )
    current, nead_url = collect_courses(current_html)
    previous, _ = collect_courses(previous_html)

    preview = build_preview(
        current, nead_url, FIXTURE, datetime(2026, 9, 25, tzinfo=UTC), previous, FIXTURE
    )
    comparison = preview["comparacao"]

    assert comparison["status"] == "revisar"
    assert comparison["revisao_necessaria"] is True
    assert comparison["contagens_por_campus"]["sede"] == {"anterior": 2, "atual": 1}
    assert comparison["removidos"] == [
        {
            "nome": "Curso anterior",
            "campus_id": "sede",
            "modalidade": "presencial",
            "url_detalhe": extra_url,
        }
    ]


def test_identical_capture_has_no_comparison_alert():
    html = FIXTURE.read_text(encoding="utf-8")
    courses, nead_url = collect_courses(html)

    preview = build_preview(
        courses, nead_url, FIXTURE, datetime(2026, 9, 25, tzinfo=UTC), courses, FIXTURE
    )

    assert preview["comparacao"]["status"] == "sem_alteracoes"
    assert preview["comparacao"]["revisao_necessaria"] is False
    assert preview["comparacao"]["removidos"] == []
