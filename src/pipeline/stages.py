from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from src.pipeline.ingest import run_ingest
from src.pipeline.manifest import build_manifest
from src.pipeline.raw import run_raw
from src.pipeline.features import run_features
from src.pipeline.link import run_link
from src.pipeline.model import run_model
from src.pipeline.plots import run_plots
from src.pipeline.spatial import run_spatial
from src.pipeline.standard import run_standard
from src.store.paths import OutputPaths


def run_manifest(
    base_dir: Path,
    config: Dict[str, Any],
    output_paths: OutputPaths,
    run_id: str,
    params_hash: str,
    **_: Any,
) -> Dict[str, Any]:
    output_file = output_paths.manifests / f"run_{run_id}.json"
    return build_manifest(base_dir, config, output_file, run_id, params_hash)


def _not_ready(stage: str) -> None:
    raise NotImplementedError(f"Stage not implemented yet: {stage}")


run_ingest = run_ingest
run_raw = run_raw
run_standard = run_standard
run_spatial = run_spatial


run_link = run_link
run_features = run_features
run_model = run_model
run_plots = run_plots
