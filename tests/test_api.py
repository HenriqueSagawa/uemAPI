import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    fonte = {
        "source_id": "teste_publico",
        "url": "https://example.org/dados",
        "consultado_em": "2026-09-24T12:00:00Z",
    }
    datasets = {
        "campi": [
            {"id": "sede", "nome": "Câmpus Sede", "sigla": None, "fonte": fonte},
            {"id": "crc", "nome": "Câmpus Regional de Cianorte", "sigla": "CRC", "fonte": fonte},
        ],
        "centros": [
            {"id": "ctc", "nome": "Centro de Tecnologia", "sigla": "CTC", "fonte": fonte},
        ],
        "departamentos": [
            {
                "id": "din",
                "nome": "Departamento de Informática",
                "sigla": "DIN",
                "centro_sigla": "CTC",
                "campus_id": "sede",
                "fonte": fonte,
            },
        ],
        "cursos": [
            {
                "id": "computacao-sede",
                "nome": "Ciência da Computação",
                "grau": "bacharelado",
                "modalidade": "presencial",
                "campus_id": "sede",
                "centro_sigla": "CTC",
                "departamento_sigla": "DIN",
                "fonte": fonte,
            },
        ],
    }
    for name, records in datasets.items():
        (tmp_path / f"{name}.json").write_text(
            json.dumps(records, ensure_ascii=False), encoding="utf-8"
        )
    return tmp_path


@pytest.mark.anyio
async def test_health_and_lists_with_approved_snapshot(data_dir: Path):
    app = create_app(Settings(data_dir=data_dir))
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            health = await client.get("/v1/health")
            assert health.status_code == 200
            assert health.json()["status"] == "ready"
            assert health.json()["datasets"]["cursos"] == 1

            for resource in ("centros", "departamentos", "cursos"):
                response = await client.get(f"/v1/{resource}")
                assert response.status_code == 200
                assert response.json()["meta"] == {"page": 1, "page_size": 50, "total": 1}
                assert response.json()["data"][0]["fonte"]["source_id"] == "teste_publico"

            campi = await client.get("/v1/campi")
            assert campi.status_code == 200
            assert campi.json()["meta"]["total"] == 2
            assert {item["id"]: item["sigla"] for item in campi.json()["data"]} == {
                "sede": None,
                "crc": "CRC",
            }


@pytest.mark.anyio
async def test_details_filters_and_errors(data_dir: Path):
    app = create_app(Settings(data_dir=data_dir))
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for path in (
                "/v1/campi/sede",
                "/v1/campi/CRC",
                "/v1/centros/ctc",
                "/v1/departamentos/din",
                "/v1/cursos/computacao-sede",
            ):
                assert (await client.get(path)).status_code == 200
            assert (await client.get("/v1/centros/CTC")).json()["departamentos"] == ["DIN"]
            assert (await client.get("/v1/campi/CRC")).json()["id"] == "crc"
            filtered = await client.get("/v1/cursos?centro=CTC&campus=sede")
            assert filtered.json()["meta"]["total"] == 1
            empty = await client.get("/v1/cursos?grau=licenciatura")
            assert empty.json()["meta"]["total"] == 0
            missing = await client.get("/v1/cursos/inexistente")
            assert missing.status_code == 404
            assert missing.json()["error"]["code"] == "not_found"
            invalid = await client.get("/v1/cursos?page_size=101")
            assert invalid.status_code == 422
            assert invalid.json()["error"]["code"] == "validation_error"


@pytest.mark.anyio
async def test_duplicate_campus_acronym_prevents_publication(data_dir: Path):
    path = data_dir / "campi.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    records[0]["sigla"] = "CRC"
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

    app = create_app(Settings(data_dir=data_dir))
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/v1/health")).status_code == 503


@pytest.mark.anyio
async def test_no_approved_snapshot_returns_503(tmp_path: Path):
    app = create_app(Settings(data_dir=tmp_path))
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/v1/health")).status_code == 503
            unavailable = await client.get("/v1/cursos")
            assert unavailable.status_code == 503
            assert unavailable.json()["error"]["code"] == "data_unavailable"


@pytest.mark.anyio
async def test_invalid_reference_prevents_publication(data_dir: Path):
    path = data_dir / "cursos.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    records[0]["campus_id"] = "nao-existe"
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

    app = create_app(Settings(data_dir=data_dir))
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/v1/health")).status_code == 503
            assert (await client.get("/v1/cursos")).status_code == 503
