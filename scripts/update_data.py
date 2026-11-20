"""Gera o snapshot a partir dos lotes revisados. Dry-run por padrão."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline import (  # noqa: E402
    DATASETS,
    SnapshotError,
    build_snapshot,
    diff_snapshot,
    read_snapshot,
    write_snapshot,
)
from app.services.repository import DatasetError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _previous(data_dir: Path) -> dict[str, list[dict]] | None:
    files = [data_dir / f"{name}.json" for name in DATASETS]
    present = [path for path in files if path.is_file()]
    if not present:
        return None
    if len(present) != len(files):
        raise SnapshotError("data/ contém snapshot incompleto")
    return read_snapshot(data_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "reviews" / "snapshot-inputs.json")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument(
        "--write",
        action="store_true",
        help="substitui os quatro arquivos em --data-dir após validar o resultado",
    )
    args = parser.parse_args(argv)
    try:
        built = build_snapshot(args.manifest)
        previous = _previous(args.data_dir)
    except (SnapshotError, ValueError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    report = {
        "escrita": False,
        "data_dir": str(args.data_dir),
        "diff": diff_snapshot(previous, built.datasets),
        **built.report,
    }
    if args.write:
        try:
            write_snapshot(built.datasets, args.data_dir)
        except (DatasetError, ValueError) as exc:
            print(f"erro: {exc}", file=sys.stderr)
            return 2
        report["escrita"] = True
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
