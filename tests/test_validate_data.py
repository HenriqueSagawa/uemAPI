import importlib.util
import json
from pathlib import Path

import pytest

from app.pipeline import DATASETS, build_snapshot, serialize_snapshot

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reviews" / "snapshot-inputs.json"


def _load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"uemapi_script_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_data = _load_script("validate_data")


@pytest.fixture(scope="module")
def built():
    return build_snapshot(MANIFEST)


@pytest.fixture
def approved(built, tmp_path) -> Path:
    data_dir = tmp_path / "data"
    texts = serialize_snapshot(built.datasets)
    data_dir.mkdir()
    for filename, text in texts.items():
        (data_dir / filename).write_text(text, encoding="utf-8")
    return data_dir


def test_absent_snapshot_is_not_an_error_unless_required(tmp_path, capsys):
    assert validate_data.main(["--data-dir", str(tmp_path / "vazio")]) == 0
    assert "nada a validar" in capsys.readouterr().err

    assert validate_data.main(["--data-dir", str(tmp_path / "vazio"), "--require"]) == 1
    assert "nada a validar" in capsys.readouterr().err


def test_incomplete_snapshot_fails(approved, capsys):
    (approved / "cursos.json").unlink()
    assert validate_data.main(["--data-dir", str(approved)]) == 1
    assert "snapshot incompleto" in capsys.readouterr().err


def test_invalid_snapshot_fails_without_exposing_records(approved, capsys):
    (approved / "cursos.json").write_text("[]\n", encoding="utf-8")
    assert validate_data.main(["--data-dir", str(approved)]) == 1
    assert "dataset vazio" in capsys.readouterr().err


def test_valid_snapshot_reports_counts(approved, capsys):
    assert validate_data.main(["--data-dir", str(approved)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["contagens"] == {
        "campi": 7,
        "centros": 7,
        "departamentos": 49,
        "cursos": 67,
    }
    assert set(report["contagens"]) == set(DATASETS)
    assert report["snapshot_consultado_em"].endswith("+00:00")
