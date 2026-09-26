"""Relatório local de cobertura das páginas de departamentos dos sete centros."""

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.collectors.departamentos import (
    CENTROS,
    SOURCE_ROOT,
    DepartamentoSourceError,
    build_preview,
    collect_departamentos,
)


@dataclass(frozen=True)
class DepartmentCapture:
    centro_sigla: str
    arquivo: Path
    consultado_em: datetime


def parse_capture_time(value: str) -> datetime:
    try:
        captured_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("consultado_em deve estar em formato ISO 8601") from exc
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("consultado_em deve incluir fuso horário")
    return captured_at


def _validate_captures(captures: list[DepartmentCapture]) -> None:
    centers = [capture.centro_sigla for capture in captures]
    if any(center not in CENTROS for center in centers):
        raise ValueError("centro desconhecido no manifesto")
    if len(centers) != len(set(centers)):
        raise ValueError("centro duplicado no manifesto")
    files = [capture.arquivo.resolve() for capture in captures]
    if len(files) != len(set(files)):
        raise ValueError("arquivo de centro duplicado no manifesto")
    if any(
        capture.consultado_em.tzinfo is None or capture.consultado_em.utcoffset() is None
        for capture in captures
    ):
        raise ValueError("consultado_em deve incluir fuso horário")


def load_manifest(path: Path) -> list[DepartmentCapture]:
    """Associa cada página salva ao centro esperado, sem buscar fontes na rede."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"centros"}:
        raise ValueError("manifesto deve conter apenas a lista centros")
    entries = data["centros"]
    if not isinstance(entries, list):
        raise ValueError("centros deve ser uma lista")

    captures = []
    for position, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or set(entry) != {
            "centro_sigla",
            "arquivo",
            "consultado_em",
        }:
            raise ValueError(f"entrada {position} do manifesto tem campos inválidos")
        if any(not isinstance(value, str) or not value.strip() for value in entry.values()):
            raise ValueError(f"entrada {position} do manifesto tem valor vazio ou inválido")
        file_path = Path(entry["arquivo"])
        captures.append(
            DepartmentCapture(
                centro_sigla=entry["centro_sigla"],
                arquivo=file_path if file_path.is_absolute() else path.parent / file_path,
                consultado_em=parse_capture_time(entry["consultado_em"]),
            )
        )
    _validate_captures(captures)
    return captures


def build_batch_preview(captures: list[DepartmentCapture], manifest_path: Path) -> dict:
    """Reúne prévias individuais; falhas em uma fonte não interrompem as demais."""
    _validate_captures(captures)
    by_center = {capture.centro_sigla: capture for capture in captures}
    results = []
    statuses = Counter()
    sigla_centers: dict[str, set[str]] = defaultdict(set)
    departments_accepted = 0

    for center, (name, slug) in sorted(CENTROS.items()):
        result = {
            "centro_sigla": center,
            "centro_nome": name,
            "fonte_url": f"{SOURCE_ROOT}/{slug}",
        }
        capture = by_center.get(center)
        if capture is None:
            result["status"] = "sem_captura"
        else:
            result["arquivo"] = str(capture.arquivo)
            result["consultado_em"] = capture.consultado_em.isoformat()
            try:
                html = capture.arquivo.read_text(encoding="utf-8")
            except FileNotFoundError:
                result["status"] = "arquivo_ausente"
            except (OSError, UnicodeError):
                result["status"] = "falha_leitura"
            else:
                try:
                    collection = collect_departamentos(html, center, capture.consultado_em)
                except (DepartamentoSourceError, ValueError):
                    result["status"] = "invalido"
                    result["motivo"] = "captura incompatível com a estrutura esperada"
                else:
                    result["status"] = "aceito"
                    result["quantidade_departamentos"] = len(collection.departamentos)
                    result["previa"] = build_preview(collection, capture.arquivo)
                    departments_accepted += len(collection.departamentos)
                    for department in collection.departamentos:
                        sigla_centers[department.sigla.casefold()].add(center)
        results.append(result)
        statuses[result["status"]] += 1

    duplicated = [
        {"sigla": sigla.upper(), "centros": sorted(centers)}
        for sigla, centers in sorted(sigla_centers.items())
        if len(centers) > 1
    ]
    return {
        "modo": "previa",
        "publicavel": False,
        "entrada": {"manifesto": str(manifest_path)},
        "resumo": {
            "total_centros": len(CENTROS),
            "total_manifesto": len(captures),
            "aceitos": statuses["aceito"],
            "sem_captura": statuses["sem_captura"],
            "arquivo_ausente": statuses["arquivo_ausente"],
            "falha_leitura": statuses["falha_leitura"],
            "invalidos": statuses["invalido"],
            "departamentos_aceitos": departments_accepted,
            "siglas_duplicadas": len(duplicated),
            "cobertura_fontes_completa": statuses["aceito"] == len(CENTROS),
        },
        "resultados": results,
        "duplicidades": duplicated,
        "proveniencia": {
            "origem_arquivos": "não autenticada; URLs institucionais apenas de referência",
            "cobertura": (
                "sete fontes aceitas significam apenas que as páginas esperadas foram processadas; "
                "a completude de cada lista exige revisão manual"
            ),
            "revisao_pendente": [
                "completude e atualidade dos departamentos em cada centro",
                "siglas duplicadas entre centros",
                "IDs candidatos e vínculos institucionais",
                "condições de reutilização",
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolida prévias locais de departamentos da PLD")
    parser.add_argument("--manifesto", required=True, type=Path, help="JSON das páginas salvas")
    args = parser.parse_args()
    try:
        preview = build_batch_preview(load_manifest(args.manifesto), args.manifesto)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(preview, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
