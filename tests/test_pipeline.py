import json
from pathlib import Path

import pytest

from app.pipeline import (
    DATASETS,
    SnapshotError,
    apply_proposals,
    build_snapshot,
    diff_snapshot,
    load_proposals,
    serialize_snapshot,
    write_snapshot,
)
from app.pipeline.normalizations import NormalizationError, Proposal
from app.review.previews import fingerprint
from app.services.repository import DatasetError, load_snapshot, parse_snapshot

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reviews" / "snapshot-inputs.json"


@pytest.fixture(scope="module")
def built():
    return build_snapshot(MANIFEST)


def test_builds_all_four_datasets_from_reviews(built):
    assert built.report["contagens"] == {
        "campi": 7,
        "centros": 7,
        "departamentos": 49,
        "cursos": 67,
    }
    assert built.report["publicavel"] is False
    snapshot = parse_snapshot(built.datasets)
    assert snapshot.counts == built.report["contagens"]


def test_applies_verified_normalization_without_hiding_evidence(built):
    dem = next(item for item in built.datasets["departamentos"] if item["id"] == "dem")
    assert dem["nome"] == "Departamento de Engenharia Mecânica"
    aplicadas = built.report["normalizacoes_aplicadas"]
    assert aplicadas == [
        {
            "dataset": "departamentos",
            "id": "dem",
            "campo": "nome",
            "valor_observado": "Deparamento de Engenharia Mecânica",
            "valor_proposto": "Departamento de Engenharia Mecânica",
        }
    ]


def test_reports_normalization_that_does_not_fit_canonical_model(built):
    ignoradas = built.report["normalizacoes_ignoradas"]
    assert len(ignoradas) == 1
    assert ignoradas[0]["dataset"] == "cursos"
    assert ignoradas[0]["campo"] == "/informacoes_academicas/0/habilitacoes"
    assert "modelo canônico" in ignoradas[0]["motivo"]


def test_projects_academic_blocks_without_inference(built):
    cursos = {item["id"]: item for item in built.datasets["cursos"]}
    agricola = cursos["car-engenharia-agricola"]
    assert agricola["grau"] == "Engenheiro Agrícola"
    assert agricola["modalidade"] == "presencial"
    assert agricola["campus_id"] == "car"
    assert agricola["centro_sigla"] is None
    assert agricola["departamento_sigla"] is None
    assert "informacoes_academicas" not in agricola
    ausentes = {item["id"] for item in built.report["grau_nao_inferido"]}
    assert "sede-musica" in ausentes
    assert cursos["sede-musica"]["grau"] is None
    assert cursos["sede-administracao"]["grau"] == "Bacharel em Administração"


def test_ignores_preview_fields_outside_the_contract(built):
    assert "url_pagina_vinculada" in built.report["campos_ignorados"]
    for centro in built.datasets["centros"]:
        assert "url_pagina_vinculada" not in centro


def test_keeps_known_coverage_gaps(built):
    cobertura = built.report["inconsistencias_cobertura"]
    assert "cursos da EaD não incluídos" in cobertura
    assert "completude dos departamentos do centro não verificada" in cobertura


def test_serialization_and_diff_are_deterministic(built):
    first = serialize_snapshot(built.datasets)
    second = serialize_snapshot(build_snapshot(MANIFEST).datasets)
    assert first == second
    assert list(first) == [f"{name}.json" for name in DATASETS]
    for name in DATASETS:
        ids = [json.loads(first[f"{name}.json"])[0]["id"]] if first[f"{name}.json"] else []
        assert ids == [ids[0].casefold()] if ids else True


def test_diff_detects_changes_against_previous_snapshot(built):
    texts = serialize_snapshot(built.datasets)
    previous = {name: json.loads(texts[f"{name}.json"]) for name in DATASETS}
    current = {name: json.loads(texts[f"{name}.json"]) for name in DATASETS}
    dem = next(item for item in previous["departamentos"] if item["id"] == "dem")
    dem["nome"] = "Deparamento de Engenharia Mecânica"
    current["cursos"] = [item for item in current["cursos"] if item["id"] != "sede-musica"]

    report = diff_snapshot(previous, current)

    assert report["snapshot_anterior"] is True
    alterados = report["datasets"]["departamentos"]["alterados"]
    assert alterados == [{"id": "dem", "campos": ["nome"]}]
    assert report["datasets"]["cursos"]["removidos"] == ["sede-musica"]
    assert report["datasets"]["campi"]["total"] == {"criados": 0, "removidos": 0, "alterados": 0}


def test_write_snapshot_validates_and_persists(tmp_path, built):
    data_dir = tmp_path / "data"
    write_snapshot(built.datasets, data_dir)
    assert sorted(path.name for path in data_dir.iterdir()) == sorted(
        f"{name}.json" for name in DATASETS
    )
    assert load_snapshot(data_dir).counts == built.report["contagens"]


def test_write_snapshot_keeps_previous_files_on_failure(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    previous = data_dir / "campi.json"
    previous.write_text("conteúdo anterior", encoding="utf-8")
    invalid = {name: [] for name in DATASETS}
    with pytest.raises(DatasetError):
        write_snapshot(invalid, data_dir)
    assert previous.read_text(encoding="utf-8") == "conteúdo anterior"


def _manifest(tmp_path: Path) -> dict:
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = MANIFEST.parent
    for entry in raw["datasets"].values():
        entry["previs"] = [str((base / item).resolve()) for item in entry["previs"]]
        entry["revisoes"] = [str((base / item).resolve()) for item in entry["revisoes"]]
    raw["normalizacoes"] = str((base / raw["normalizacoes"]).resolve())
    return raw


def _write_manifest(tmp_path: Path, raw: dict) -> Path:
    path = tmp_path / "snapshot-inputs.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


def test_manifest_refuses_pending_review(tmp_path):
    raw = _manifest(tmp_path)
    raw["datasets"]["departamentos"]["revisoes"][-1] = str(
        (ROOT / "reviews" / "2026-10-16-departamentos" / "ctc" / "revisao.json").resolve()
    )
    with pytest.raises(SnapshotError, match="pendentes"):
        build_snapshot(_write_manifest(tmp_path, raw))


def test_manifest_refuses_missing_or_duplicated_files(tmp_path):
    raw = _manifest(tmp_path)
    raw["datasets"]["campi"]["previs"] = [str(tmp_path / "ausente.json")]
    with pytest.raises(SnapshotError, match="não encontrado"):
        build_snapshot(_write_manifest(tmp_path, raw))

    raw = _manifest(tmp_path)
    raw["datasets"]["campi"]["previs"] = [
        raw["datasets"]["campi"]["previs"][0],
        raw["datasets"]["campi"]["previs"][0],
    ]
    raw["datasets"]["campi"]["revisoes"] = [
        raw["datasets"]["campi"]["revisoes"][0],
        raw["datasets"]["campi"]["revisoes"][0],
    ]
    with pytest.raises(SnapshotError, match="repetido"):
        build_snapshot(_write_manifest(tmp_path, raw))


def test_manifest_requires_exactly_four_datasets(tmp_path):
    raw = _manifest(tmp_path)
    del raw["datasets"]["cursos"]
    with pytest.raises(SnapshotError, match="exatamente os quatro"):
        build_snapshot(_write_manifest(tmp_path, raw))


def test_manifest_requires_a_single_course_consolidation(tmp_path):
    raw = _manifest(tmp_path)
    extra_previa = str(ROOT / "reviews/2026-10-16-campi-centros/campi-previa.json")
    extra_revisao = str(ROOT / "reviews/2026-10-16-campi-centros/campi-revisao.json")
    raw["datasets"]["cursos"]["previs"].append(extra_previa)
    raw["datasets"]["cursos"]["revisoes"].append(extra_revisao)
    with pytest.raises(SnapshotError, match="exatamente um consolidado"):
        build_snapshot(_write_manifest(tmp_path, raw))

    raw = _manifest(tmp_path)
    raw["datasets"]["campi"]["revisoes"].append(
        str(ROOT / "reviews/2026-10-16-campi-centros/centros-revisao.json")
    )
    with pytest.raises(SnapshotError, match="não pareadas"):
        build_snapshot(_write_manifest(tmp_path, raw))


def _proposal(record: dict, **overrides) -> Proposal:
    base = {
        "dataset": "departamentos",
        "id": "dem",
        "campo": "/nome",
        "valor_observado": "antigo",
        "valor_proposto": "novo",
        "impressao_base": fingerprint(record, {}),
    }
    base.update(overrides)
    return Proposal(**base)


def test_apply_proposals_requires_matching_evidence():
    record = {"id": "dem", "nome": "antigo"}
    records = {"departamentos": {"dem": record}}
    digests = {"departamentos": {"dem": fingerprint(record, {})}}

    updated, outcome = apply_proposals((_proposal(record),), records, digests)
    assert updated["departamentos"]["dem"]["nome"] == "novo"
    assert record["nome"] == "antigo"
    assert len(outcome.aplicadas) == 1

    with pytest.raises(NormalizationError, match="impressão base divergente"):
        apply_proposals((_proposal(record, impressao_base="0" * 64),), records, digests)
    with pytest.raises(NormalizationError, match="valor observado divergente"):
        apply_proposals((_proposal(record, valor_observado="outro"),), records, digests)
    with pytest.raises(NormalizationError, match="não encontrado"):
        apply_proposals((_proposal(record, id="inexistente"),), records, digests)


def test_apply_proposals_skips_nested_fields_outside_the_model():
    record = {
        "id": "curso",
        "informacoes_academicas": [{"habilitacoes": ["Licenciatura"]}],
    }
    records = {"cursos": {"car|url": record}}
    digests = {"cursos": {"car|url": fingerprint(record, {})}}
    proposal = _proposal(
        record,
        dataset="cursos",
        id="car|url",
        campo="/informacoes_academicas/0/habilitacoes",
        valor_observado=["Licenciatura"],
        valor_proposto=["Bacharel em Engenharia Agrícola"],
        impressao_base=digests["cursos"]["car|url"],
    )
    updated, outcome = apply_proposals((proposal,), records, digests)
    assert updated["cursos"]["car|url"] == record
    assert outcome.aplicadas == ()
    assert len(outcome.ignoradas) == 1


def test_load_proposals_rejects_ambiguous_documents(tmp_path):
    real = json.loads(
        (ROOT / "reviews/2026-10-22-pendencias/normalizacoes-propostas.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        len(load_proposals(ROOT / "reviews/2026-10-22-pendencias/normalizacoes-propostas.json"))
        == 2
    )

    duplicate = json.loads(json.dumps(real))
    duplicate["propostas"].append(duplicate["propostas"][0])
    path = tmp_path / "duplicado.json"
    path.write_text(json.dumps(duplicate, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(NormalizationError, match="duplicada"):
        load_proposals(path)

    no_change = json.loads(json.dumps(real))
    no_change["propostas"][0]["valor_proposto"] = no_change["propostas"][0]["valor_observado"]
    path = tmp_path / "sem-alteracao.json"
    path.write_text(json.dumps(no_change, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(NormalizationError, match="sem alteração"):
        load_proposals(path)

    bad_digest = json.loads(json.dumps(real))
    bad_digest["propostas"][0]["impressao_base"] = "x"
    path = tmp_path / "hash-invalido.json"
    path.write_text(json.dumps(bad_digest, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(NormalizationError, match="impressão base inválida"):
        load_proposals(path)
