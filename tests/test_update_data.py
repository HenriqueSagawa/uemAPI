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


update_data = _load_script("update_data")


@pytest.fixture(scope="module")
def built():
    return build_snapshot(MANIFEST)


def _run(capsys, *args: str) -> tuple[int, dict, str]:
    code = update_data.main(list(args))
    out = capsys.readouterr()
    return code, json.loads(out.out) if out.out else {}, out.err


def test_dry_run_does_not_write_by_default(tmp_path, capsys):
    data_dir = tmp_path / "data"
    code, report, _ = _run(capsys, "--manifest", str(MANIFEST), "--data-dir", str(data_dir))

    assert code == 0
    assert report["escrita"] is False
    assert report["publicavel"] is False
    assert report["diff"]["snapshot_anterior"] is False
    assert report["contagens"] == {
        "campi": 7,
        "centros": 7,
        "departamentos": 49,
        "cursos": 67,
    }
    assert not data_dir.exists()
    assert report["normalizacoes_aplicadas"][0]["id"] == "dem"
    assert "normalizacoes_ignoradas" in report


def test_write_creates_snapshot_and_next_run_shows_no_changes(tmp_path, capsys):
    data_dir = tmp_path / "data"
    code, first, _ = _run(
        capsys, "--manifest", str(MANIFEST), "--data-dir", str(data_dir), "--write"
    )
    assert code == 0
    assert first["escrita"] is True
    assert sorted(path.name for path in data_dir.iterdir()) == sorted(
        f"{name}.json" for name in DATASETS
    )

    code, second, _ = _run(capsys, "--manifest", str(MANIFEST), "--data-dir", str(data_dir))
    assert code == 0
    assert second["escrita"] is False
    assert second["diff"]["snapshot_anterior"] is True
    totals = {name: entry["total"] for name, entry in second["diff"]["datasets"].items()}
    assert all(value == {"criados": 0, "removidos": 0, "alterados": 0} for value in totals.values())


def test_check_accepts_a_snapshot_matching_the_reviews(tmp_path, capsys):
    data_dir = tmp_path / "data"
    assert _run(capsys, "--manifest", str(MANIFEST), "--data-dir", str(data_dir), "--write")[0] == 0
    code, report, _ = _run(
        capsys, "--manifest", str(MANIFEST), "--data-dir", str(data_dir), "--check"
    )
    assert code == 0
    assert report["verificacao"] == {"ok": True, "problemas": []}


def test_check_detects_drift_and_missing_snapshot(tmp_path, capsys):
    data_dir = tmp_path / "data"
    assert _run(capsys, "--manifest", str(MANIFEST), "--data-dir", str(data_dir), "--write")[0] == 0
    campi = data_dir / "campi.json"
    campi.write_text(campi.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    code, report, _ = _run(
        capsys, "--manifest", str(MANIFEST), "--data-dir", str(data_dir), "--check"
    )
    assert code == 1
    assert report["verificacao"]["ok"] is False
    assert report["verificacao"]["problemas"] == ["divergente: campi.json"]

    code, report, _ = _run(
        capsys, "--manifest", str(MANIFEST), "--data-dir", str(tmp_path / "vazio"), "--check"
    )
    assert code == 1
    assert len(report["verificacao"]["problemas"]) == len(DATASETS)
    assert all(item.startswith("ausente:") for item in report["verificacao"]["problemas"])


def test_write_and_check_are_mutually_exclusive(tmp_path, capsys):
    with pytest.raises(SystemExit):
        update_data.main(
            [
                "--manifest",
                str(MANIFEST),
                "--data-dir",
                str(tmp_path / "data"),
                "--write",
                "--check",
            ]
        )
    assert "not allowed" in capsys.readouterr().err


def test_previous_snapshot_is_not_touched_when_review_is_pending(tmp_path, capsys, built):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for filename, text in serialize_snapshot(built.datasets).items():
        (data_dir / filename).write_text(text, encoding="utf-8")
    before = {path.name: path.read_bytes() for path in data_dir.iterdir()}

    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = MANIFEST.parent
    for entry in raw["datasets"].values():
        entry["previs"] = [str((base / item).resolve()) for item in entry["previs"]]
        entry["revisoes"] = [str((base / item).resolve()) for item in entry["revisoes"]]
    raw["normalizacoes"] = str((base / raw["normalizacoes"]).resolve())
    raw["ids_cursos"] = str((base / raw["ids_cursos"]).resolve())
    raw["datasets"]["departamentos"]["revisoes"][-1] = str(
        (ROOT / "reviews" / "2026-10-16-departamentos" / "ctc" / "revisao.json").resolve()
    )
    manifest = tmp_path / "pendente.json"
    manifest.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    code, report, err = _run(
        capsys, "--manifest", str(manifest), "--data-dir", str(data_dir), "--write"
    )

    assert code == 2
    assert report == {}
    assert "pendentes" in err
    assert {path.name: path.read_bytes() for path in data_dir.iterdir()} == before


def test_incomplete_previous_snapshot_is_rejected(tmp_path, capsys, built):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    texts = serialize_snapshot(built.datasets)
    (data_dir / "campi.json").write_text(texts["campi.json"], encoding="utf-8")

    code, report, err = _run(capsys, "--manifest", str(MANIFEST), "--data-dir", str(data_dir))

    assert code == 2
    assert report == {}
    assert "incompleto" in err


def test_missing_manifest_is_reported(tmp_path, capsys):
    code, report, err = _run(
        capsys,
        "--manifest",
        str(tmp_path / "ausente.json"),
        "--data-dir",
        str(tmp_path / "data"),
    )
    assert code == 2
    assert report == {}
    assert "não foi possível ler JSON" in err
