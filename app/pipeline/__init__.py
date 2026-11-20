"""Pipeline de geração do snapshot a partir das revisões registradas."""

from app.pipeline.datasets import DATASETS, MODELS
from app.pipeline.diff import diff_snapshot
from app.pipeline.io import read_snapshot, serialize_snapshot, write_snapshot
from app.pipeline.normalizations import (
    AppliedProposal,
    NormalizationError,
    NormalizationOutcome,
    Proposal,
    SkippedProposal,
    apply_proposals,
    load_proposals,
)
from app.pipeline.snapshot import (
    BuiltSnapshot,
    DatasetInputs,
    SnapshotError,
    SnapshotManifest,
    build_snapshot,
    load_manifest,
)

__all__ = [
    "DATASETS",
    "MODELS",
    "AppliedProposal",
    "BuiltSnapshot",
    "DatasetInputs",
    "NormalizationError",
    "NormalizationOutcome",
    "Proposal",
    "SkippedProposal",
    "SnapshotError",
    "SnapshotManifest",
    "apply_proposals",
    "build_snapshot",
    "diff_snapshot",
    "load_manifest",
    "load_proposals",
    "read_snapshot",
    "serialize_snapshot",
    "write_snapshot",
]
