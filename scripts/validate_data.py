"""Valida o snapshot aprovado em data/ antes de publicar ou servir a API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline.datasets import DATASETS  # noqa: E402
from app.services.repository import DatasetError, load_snapshot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
    )
    parser.add_argument(
        "--require",
        action="store_true",
        help="falha quando o snapshot ainda não existe",
    )
    args = parser.parse_args(argv)
    files = [args.data_dir / f"{name}.json" for name in DATASETS]
    present = [path for path in files if path.is_file()]
    if not present:
        print(f"snapshot ausente em {args.data_dir}; nada a validar", file=sys.stderr)
        return 1 if args.require else 0
    missing = [path.name for path in files if not path.is_file()]
    if missing:
        print(f"erro: snapshot incompleto; ausentes: {', '.join(missing)}", file=sys.stderr)
        return 1
    try:
        snapshot = load_snapshot(args.data_dir)
    except DatasetError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    report = {
        "data_dir": str(args.data_dir),
        "contagens": snapshot.counts,
        "snapshot_consultado_em": snapshot.consultado_em.isoformat(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
