import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.collectors.departamentos import CENTROS
from app.collectors.departamentos_consolidados import (
    DepartmentCapture,
    build_batch_preview,
    load_manifest,
)

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLE = FIXTURES / "departamentos_consolidados_manifesto.json"
CTC = FIXTURES / "departamentos_ctc.html"
CAPTURED_AT = datetime(2026, 9, 26, 12, tzinfo=UTC)


def capture(center, path):
    return DepartmentCapture(center, path, CAPTURED_AT)


def page(center, department_sigla):
    name = CENTROS[center][0]
    return f"""<article id="content">
      <header><h1 class="documentFirstHeading">
      {center} - {name} (Departamentos e Órgãos)
      </h1></header>
      <div id="content-core"><div class="entries">
        <article class="entry"><header><a href="centro.pdf/view">
          {center} - {name} (Resolução nº 001/2026)
        </a></header></article>
        <article class="entry"><header><a href="departamento.pdf/view">
          {department_sigla} - Departamento de Exemplo (Resolução nº 002/2026)
        </a></header></article>
      </div></div>
    </article>"""


def test_accepts_seven_distinct_centers_without_claiming_completeness(tmp_path):
    captures = []
    for index, center in enumerate(CENTROS):
        path = tmp_path / f"{center}.html"
        path.write_text(page(center, f"D{index:02}"), encoding="utf-8")
        captures.append(capture(center, path))

    preview = build_batch_preview(captures, tmp_path / "manifesto.json")

    assert preview["modo"] == "previa"
    assert preview["publicavel"] is False
    assert preview["resumo"] == {
        "total_centros": 7,
        "total_manifesto": 7,
        "aceitos": 7,
        "sem_captura": 0,
        "arquivo_ausente": 0,
        "falha_leitura": 0,
        "invalidos": 0,
        "departamentos_aceitos": 7,
        "siglas_duplicadas": 0,
        "cobertura_fontes_completa": True,
    }
    assert [result["centro_sigla"] for result in preview["resultados"]] == sorted(CENTROS)
    assert all(result["previa"]["publicavel"] is False for result in preview["resultados"])
    assert all(result["quantidade_departamentos"] == 1 for result in preview["resultados"])
    assert "completude de cada lista exige revisão manual" in preview["proveniencia"]["cobertura"]


def test_isolates_missing_file_read_failure_and_invalid_source(tmp_path):
    invalid = tmp_path / "invalido.html"
    invalid.write_text(page("CCB", "DBB"), encoding="utf-8")
    unreadable = tmp_path / "invalido-utf8.html"
    unreadable.write_bytes(b"\xff")
    captures = [
        capture("CTC", CTC),
        capture("CCA", invalid),
        capture("CCB", tmp_path / "nao-existe.html"),
        capture("CCE", unreadable),
    ]

    preview = build_batch_preview(captures, tmp_path / "manifesto.json")
    by_center = {result["centro_sigla"]: result for result in preview["resultados"]}

    assert by_center["CTC"]["status"] == "aceito"
    assert by_center["CCA"]["status"] == "invalido"
    assert by_center["CCA"]["motivo"] == "captura incompatível com a estrutura esperada"
    assert by_center["CCB"]["status"] == "arquivo_ausente"
    assert by_center["CCE"]["status"] == "falha_leitura"
    assert all(by_center[center]["status"] == "sem_captura" for center in ("CCH", "CCS", "CSA"))
    assert preview["resumo"]["departamentos_aceitos"] == 4
    assert preview["resumo"]["cobertura_fontes_completa"] is False


def test_reports_same_department_sigla_across_centers_without_rejecting_sources(tmp_path):
    duplicated = tmp_path / "cca.html"
    duplicated.write_text(page("CCA", "DIN"), encoding="utf-8")

    preview = build_batch_preview(
        [capture("CCA", duplicated), capture("CTC", CTC)], tmp_path / "manifesto.json"
    )

    assert preview["resumo"]["aceitos"] == 2
    assert preview["resumo"]["siglas_duplicadas"] == 1
    assert preview["duplicidades"] == [{"sigla": "DIN", "centros": ["CCA", "CTC"]}]


@pytest.mark.parametrize(
    "change,expected",
    [
        (lambda data: data["centros"].append(data["centros"][0]), "centro duplicado"),
        (
            lambda data: data["centros"][1].update(arquivo=data["centros"][0]["arquivo"]),
            "arquivo de centro duplicado",
        ),
        (lambda data: data["centros"][0].update(centro_sigla="XYZ"), "centro desconhecido"),
        (
            lambda data: data["centros"][0].update(consultado_em="2026-09-26T12:00:00"),
            "fuso horário",
        ),
        (lambda data: data["centros"][0].update(extra="valor"), "campos inválidos"),
    ],
)
def test_rejects_ambiguous_manifest(tmp_path, change, expected):
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "manifesto.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=expected):
        load_manifest(path)


def test_manifest_resolves_paths_relative_to_its_directory(tmp_path):
    path = tmp_path / "manifesto.json"
    path.write_text(
        json.dumps(
            {
                "centros": [
                    {
                        "centro_sigla": "CTC",
                        "arquivo": "pagina.html",
                        "consultado_em": "2026-09-26T12:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert load_manifest(path) == [capture("CTC", tmp_path / "pagina.html")]


def test_build_rejects_reused_file_and_duplicate_center():
    with pytest.raises(ValueError, match="arquivo de centro duplicado"):
        build_batch_preview([capture("CCA", CTC), capture("CTC", CTC)], EXAMPLE)
    with pytest.raises(ValueError, match="centro duplicado"):
        build_batch_preview([capture("CTC", CTC), capture("CTC", CTC)], EXAMPLE)


def test_cli_prints_report_without_writing_files(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", str(Path(__file__).resolve().parents[1]))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.collectors.departamentos_consolidados",
            "--manifesto",
            str(EXAMPLE),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    preview = json.loads(result.stdout)
    assert preview["resumo"]["aceitos"] == 1
    assert preview["resumo"]["arquivo_ausente"] == 6
    assert preview["publicavel"] is False
    assert list(tmp_path.iterdir()) == []
