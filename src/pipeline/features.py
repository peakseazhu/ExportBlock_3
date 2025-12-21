from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from src.store.parquet import read_parquet
from src.utils import ensure_dir, write_json


def run_features(
    base_dir: Path,
    config: Dict[str, Any],
    output_paths,
    run_id: str,
    params_hash: str,
    strict: bool,
    event_id: str | None,
) -> None:
    if event_id is None:
        event_id = (config.get("events") or [{}])[0].get("event_id")
    linked_dir = output_paths.linked / event_id
    aligned_path = linked_dir / "aligned.parquet"
    if not aligned_path.exists():
        raise FileNotFoundError(f"Aligned parquet not found: {aligned_path}")

    aligned_df = pd.read_parquet(aligned_path)
    if aligned_df.empty:
        features_df = pd.DataFrame()
    else:
        aligned_df["value"] = pd.to_numeric(aligned_df["value"], errors="coerce")
        feature_records: List[Dict[str, Any]] = []
        group_cols = ["source", "station_id", "channel"]
        for (source, station_id, channel), group in aligned_df.groupby(group_cols):
            values = group["value"].dropna().astype(float)
            if values.empty:
                continue
            stats = {
                "mean": float(values.mean()),
                "std": float(values.std()),
                "min": float(values.min()),
                "max": float(values.max()),
                "rms": float(np.sqrt(np.mean(values**2))),
                "count": int(values.count()),
            }
            for feature, value in stats.items():
                feature_records.append(
                    {
                        "event_id": event_id,
                        "source": source,
                        "station_id": station_id,
                        "channel": channel,
                        "feature": feature,
                        "value": value,
                    }
                )
        features_df = pd.DataFrame.from_records(feature_records)

    features_dir = output_paths.features / event_id
    ensure_dir(features_dir)
    if not features_df.empty:
        features_df.to_parquet(features_dir / "features.parquet", index=False)
    else:
        pd.DataFrame(
            columns=["event_id", "source", "station_id", "channel", "feature", "value"]
        ).to_parquet(features_dir / "features.parquet", index=False)

    summary = {
        "event_id": event_id,
        "feature_rows": int(len(features_df)),
        "sources": features_df["source"].value_counts().to_dict() if not features_df.empty else {},
    }
    write_json(features_dir / "summary.json", summary)
    write_json(features_dir / "dq_features.json", summary)
