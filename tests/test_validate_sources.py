import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"uemapi_script_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_sources = _load_script("validate_sources")


@pytest.fixture
def registry() -> dict:
    return {
        "sources": {
            "fonte_publica": {
                "dataset": ["campi", "centros"],
                "url": "https://example.org/fonte",
                "type": "html",
                "collector": "campi",
                "access": "public",
                "role": "primary",
                "status": "candidate",
                "last_verified": "2026-10-16",
                "review_interval_days": None,
                "reuse_conditions": "not_verified",
                "notes": "Conferência registrada em revisão.",
            }
        }
    }


def test_accepts_the_committed_registry():
    sources = validate_sources.load_registry(ROOT / "sources" / "registry.yaml")
    assert "campi_uem" in sources
    assert sources["campi_uem"]["reuse_conditions"] == "not_verified"


def test_validates_datasets_declared_as_single_value_or_list(registry):
    validated = validate_sources.validate_registry(registry)
    assert list(validated) == ["fonte_publica"]
    assert validated["fonte_publica"]["dataset"] == ["campi", "centros"]


def _invalid(registry: dict, **changes) -> dict:
    raw = copy.deepcopy(registry)
    raw["sources"]["fonte_publica"].update(changes)
    return raw


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"dataset": "alunos"}, "dataset inválido"),
        ({"dataset": ["campi", "campi"]}, "dataset repetido"),
        ({"url": "http://example.org/fonte"}, "HTTPS"),
        ({"url": None}, "URL ausente"),
        ({"type": "xml"}, "type inválido"),
        ({"access": "private"}, "access inválido"),
        ({"role": "mirror"}, "role inválido"),
        ({"status": "published"}, "status inválido"),
        ({"reuse_conditions": "approved"}, "reuse_conditions inválido"),
        ({"last_verified": "16/10/2026"}, "AAAA-MM-DD"),
        ({"last_verified": "2099-01-01"}, "futuro"),
        ({"review_interval_days": 0}, "review_interval_days inválido"),
        ({"notes": ""}, "notes ausente"),
    ],
)
def test_rejects_inconsistent_entries(registry, changes, message):
    with pytest.raises(validate_sources.SourceError, match=message):
        validate_sources.validate_registry(_invalid(registry, **changes))


def test_rejects_missing_fields_and_invalid_documents(registry):
    raw = copy.deepcopy(registry)
    del raw["sources"]["fonte_publica"]["collector"]
    with pytest.raises(validate_sources.SourceError, match="campos ausentes: collector"):
        validate_sources.validate_registry(raw)

    with pytest.raises(validate_sources.SourceError, match="chave sources"):
        validate_sources.validate_registry({"fontes": {}})

    with pytest.raises(validate_sources.SourceError, match="sem fontes"):
        validate_sources.validate_registry({"sources": {}})

    with pytest.raises(validate_sources.SourceError, match="source_id inválido"):
        validate_sources.validate_registry(
            {"sources": {"Fonte Inválida": registry["sources"]["fonte_publica"]}}
        )


def test_cli_reports_success_and_failure(tmp_path, capsys, registry):
    valid = tmp_path / "registry.yaml"
    valid.write_text(
        "sources:\n"
        "  fonte_publica:\n"
        "    dataset: campi\n"
        "    url: https://example.org/fonte\n"
        "    type: html\n"
        "    collector: campi\n"
        "    access: public\n"
        "    role: primary\n"
        "    status: candidate\n"
        '    last_verified: "2026-10-16"\n'
        "    review_interval_days: null\n"
        "    reuse_conditions: not_verified\n"
        "    notes: conferida\n",
        encoding="utf-8",
    )
    assert validate_sources.main(["--registry", str(valid)]) == 0
    assert "1 fontes válidas" in capsys.readouterr().out

    broken = _invalid(registry, status="publicado")
    invalid = tmp_path / "invalido.yaml"
    invalid.write_text(json.dumps(broken), encoding="utf-8")
    assert validate_sources.main(["--registry", str(invalid)]) == 1
    assert "status inválido" in capsys.readouterr().err
