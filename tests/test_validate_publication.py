import copy
import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

from app.pipeline import DATASETS, build_snapshot, write_snapshot
from app.services.repository import load_snapshot

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reviews" / "snapshot-inputs.json"
APPROVAL = ROOT / "reviews" / "2026-11-20-publicacao" / "aprovacao.json"
REGISTRY = ROOT / "sources" / "registry.yaml"
TODAY = date(2026, 11, 20)


def _load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"uemapi_script_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_publication = _load_script("validate_publication")


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    built = build_snapshot(MANIFEST)
    write_snapshot(built.datasets, data_dir)
    snapshot = load_snapshot(data_dir)
    used = sorted(
        {record.fonte.source_id for name in DATASETS for record in snapshot.records(name)}
    )
    registry = {
        "campi_uem": _source(["campi"]),
        "centros_pld": _source(["centros", "departamentos"]),
        "cursos_graduacao": _source(["cursos"]),
    }
    approval = {
        "versao": 1,
        "publicacao": "v0.1.0-teste",
        "aprovado_por": "Teste",
        "data_aprovacao": "2026-11-20",
        "escopo": "Snapshot de teste.",
        "snapshot_consultado_em": snapshot.consultado_em.isoformat(),
        "contagens": snapshot.counts,
        "fontes": used,
        "limitacoes": ["Limitação de teste."],
    }
    return data_dir, snapshot, registry, approval


def _source(dataset: list[str]) -> dict:
    return {
        "dataset": dataset,
        "url": "https://example.org/fonte",
        "type": "html",
        "collector": None,
        "access": "public",
        "role": "primary",
        "status": "approved",
        "last_verified": "2026-10-16",
        "review_interval_days": 180,
        "reuse_conditions": "verified",
        "notes": "Fonte de teste.",
    }


def _write(tmp_path: Path, registry: dict, approval: dict) -> tuple[Path, Path]:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        json.dumps({"sources": registry}, ensure_ascii=False), encoding="utf-8"
    )
    approval_path = tmp_path / "aprovacao.json"
    approval_path.write_text(json.dumps(approval, ensure_ascii=False), encoding="utf-8")
    return registry_path, approval_path


def _validate(tmp_path, prepared, registry, approval):
    data_dir = prepared[0]
    registry_path, approval_path = _write(tmp_path, registry, approval)
    return validate_publication.validate_publication(
        data_dir, MANIFEST, registry_path, approval_path, today=TODAY
    )


def test_accepts_a_complete_publication(tmp_path, prepared):
    _, snapshot, registry, approval = prepared
    report = _validate(tmp_path, prepared, registry, approval)
    assert report["publicavel"] is True
    assert report["contagens"] == snapshot.counts
    assert report["fontes"] == approval["fontes"]


def test_committed_publication_is_consistent():
    report = validate_publication.validate_publication(
        ROOT / "data", MANIFEST, REGISTRY, APPROVAL, today=TODAY
    )
    assert report["contagens"] == {"campi": 7, "centros": 7, "departamentos": 49, "cursos": 67}
    assert report["publicavel"] is True


def test_rejects_snapshot_that_differs_from_the_reviews(tmp_path, prepared):
    data_dir, _, registry, approval = prepared
    campi = data_dir / "campi.json"
    original = campi.read_text(encoding="utf-8")
    campi.write_text(original + "\n", encoding="utf-8")
    try:
        with pytest.raises(validate_publication.PublicationError, match="divergente: campi.json"):
            _validate(tmp_path, prepared, registry, approval)
    finally:
        campi.write_text(original, encoding="utf-8")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"status": "candidate"}, "sem status approved"),
        ({"reuse_conditions": "not_verified"}, "reutilização verificada"),
        ({"review_interval_days": None}, "sem intervalo de revisão"),
        ({"last_verified": "2020-01-01", "review_interval_days": 30}, "revisão vencida"),
    ],
)
def test_rejects_unapproved_or_stale_sources(tmp_path, prepared, change, message):
    _, _, registry, approval = prepared
    broken = copy.deepcopy(registry)
    broken["cursos_graduacao"].update(change)
    with pytest.raises(validate_publication.PublicationError, match=message):
        _validate(tmp_path, prepared, broken, approval)


def test_rejects_source_that_does_not_declare_the_dataset(tmp_path, prepared):
    _, _, registry, approval = prepared
    broken = copy.deepcopy(registry)
    broken["cursos_graduacao"]["dataset"] = ["campi"]
    with pytest.raises(validate_publication.PublicationError, match="não declara o dataset cursos"):
        _validate(tmp_path, prepared, broken, approval)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("contagens", {"campi": 1, "centros": 7, "departamentos": 49, "cursos": 67}, "contagens"),
        ("fontes", ["campi_uem"], "fontes"),
        ("snapshot_consultado_em", "2020-01-01T00:00:00Z", "snapshot_consultado_em"),
        ("data_aprovacao", "2020-01-01", "anterior à captura"),
    ],
)
def test_rejects_approval_that_does_not_match_the_snapshot(
    tmp_path, prepared, field, value, message
):
    _, _, registry, approval = prepared
    broken = copy.deepcopy(approval)
    broken[field] = value
    with pytest.raises(validate_publication.PublicationError, match=message):
        _validate(tmp_path, prepared, registry, broken)


def test_load_approval_rejects_unknown_and_missing_fields(tmp_path, prepared):
    _, _, _, approval = prepared
    unknown = copy.deepcopy(approval)
    unknown["extra"] = True
    path = tmp_path / "desconhecido.json"
    path.write_text(json.dumps(unknown), encoding="utf-8")
    with pytest.raises(validate_publication.PublicationError, match="registro de aprovação"):
        validate_publication.load_approval(path)

    missing = copy.deepcopy(approval)
    del missing["limitacoes"]
    path = tmp_path / "incompleto.json"
    path.write_text(json.dumps(missing), encoding="utf-8")
    with pytest.raises(validate_publication.PublicationError, match="registro de aprovação"):
        validate_publication.load_approval(path)
