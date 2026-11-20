from app.core.normalize import fold, slug


def test_fold_removes_accents_and_collapses_spaces():
    assert fold("  Câmpus   Sede - Maringá/PR ") == "campus sede - maringa/pr"
    assert fold("Não se aplica") == "nao se aplica"


def test_slug_builds_stable_identifiers():
    assert slug("Engenharia de Controle e Automação - Inteligência Artificial") == (
        "engenharia-de-controle-e-automacao-inteligencia-artificial"
    )
    assert slug("Ciências Biológicas") == "ciencias-biologicas"
    assert slug("  ") == ""
