from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from src.pipeline.manifest import build_manifest
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


def run_ingest(*args: Any, **kwargs: Any) -> None:
    _not_ready("ingest")


def run_raw(*args: Any, **kwargs: Any) -> None:
    _not_ready("raw")


def run_standard(*args: Any, **kwargs: Any) -> None:
    _not_ready("standard")


def run_spatial(*args: Any, **kwargs: Any) -> None:
    _not_ready("spatial")


def run_link(*args: Any, **kwargs: Any) -> None:
    _not_ready("link")


def run_features(*args: Any, **kwargs: Any) -> None:
    _not_ready("features")


def run_model(*args: Any, **kwargs: Any) -> None:
    _not_ready("model")


def run_plots(*args: Any, **kwargs: Any) -> None:
    _not_ready("plots")
