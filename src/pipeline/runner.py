from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from src.pipeline import stages as stage_impl
from src.store.paths import OutputPaths

STAGE_ORDER = [
    "manifest",
    "ingest",
    "raw",
    "standard",
    "spatial",
    "link",
    "features",
    "model",
    "plots",
]

STAGE_FUNCS = {
    "manifest": stage_impl.run_manifest,
    "ingest": stage_impl.run_ingest,
    "raw": stage_impl.run_raw,
    "standard": stage_impl.run_standard,
    "spatial": stage_impl.run_spatial,
    "link": stage_impl.run_link,
    "features": stage_impl.run_features,
    "model": stage_impl.run_model,
    "plots": stage_impl.run_plots,
}


def _validate_stage_order(stages: List[str]) -> None:
    order_index = {name: idx for idx, name in enumerate(STAGE_ORDER)}
    last_idx = -1
    for stage in stages:
        if stage not in order_index:
            raise ValueError(f"Unknown stage: {stage}")
        if order_index[stage] < last_idx:
            raise ValueError("Stage order must follow A->A'->B->E->F->H sequence.")
        last_idx = order_index[stage]


def run_stages(
    stages: List[str],
    base_dir: Path,
    config: Dict[str, Any],
    output_paths: OutputPaths,
    run_id: str,
    params_hash: str,
    strict: bool,
    event_id: str | None,
) -> None:
    _validate_stage_order(stages)
    for stage in stages:
        func = STAGE_FUNCS[stage]
        func(
            base_dir=base_dir,
            config=config,
            output_paths=output_paths,
            run_id=run_id,
            params_hash=params_hash,
            strict=strict,
            event_id=event_id,
        )
