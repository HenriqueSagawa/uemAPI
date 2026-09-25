from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.collectors.cursos import CourseSourceError, build_preview, collect_courses

FIXTURE = Path(__file__).parent / "fixtures" / "cursos_pen.html"


def test_courses_remain_separate_by_campus_and_ead_is_excluded():
    html = FIXTURE.read_text(encoding="utf-8")

    courses, nead_url = collect_courses(html)
    preview = build_preview(courses, nead_url, FIXTURE, datetime(2026, 9, 25, tzinfo=UTC))

    assert [(course.nome, course.campus_id) for course in courses] == [
        ("Pedagogia", "sede"),
        ("Pedagogia", "crv"),
    ]
    assert preview["publicavel"] is False
    assert preview["total"] == 2
    assert preview["ead"]["cursos_incluidos"] is False
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
