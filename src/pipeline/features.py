from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.config import get_event
from src.store.parquet import read_parquet
from src.utils import ensure_dir, write_json


def _gradient_stats(group: pd.DataFrame) -> Optional[Tuple[float, float]]:
    subset = group[["ts_ms", "value"]].dropna().sort_values("ts_ms")
    if len(subset) < 2:
        return None
    dt_s = subset["ts_ms"].diff() / 1000.0
    dv = subset["value"].diff()
    valid = dt_s > 0
    if valid.sum() == 0:
        return None
    grad = (dv[valid] / dt_s[valid]).abs()
    if grad.empty:
        return None
    return float(grad.mean()), float(grad.max())


def _arrival_offset_s(group: pd.DataFrame, origin_ms: int) -> Optional[float]:
    subset = group.dropna(subset=["ts_ms", "value"]).sort_values("ts_ms")
    if subset.empty:
        return None
    idx = subset["value"].astype(float).idxmax()
    ts_ms = int(subset.loc[idx, "ts_ms"])
    return (ts_ms - origin_ms) / 1000.0


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
    event = get_event(config, event_id)
    origin_ms = int(pd.Timestamp(event["origin_time_utc"]).value // 1_000_000)
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
                "variance": float(values.var()),
                "min": float(values.min()),
                "max": float(values.max()),
                "peak": float(values.max()),
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
            if source == "geomag":
                grad_stats = _gradient_stats(group)
                if grad_stats is not None:
                    grad_mean, grad_max = grad_stats
                    for feature, value in {
                        "gradient_abs_mean": grad_mean,
                        "gradient_abs_max": grad_max,
                    }.items():
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
            if source == "seismic":
                if channel.endswith("_rms"):
                    offset = _arrival_offset_s(group, origin_ms)
                    if offset is not None:
                        feature_records.append(
                            {
                                "event_id": event_id,
                                "source": source,
                                "station_id": station_id,
                                "channel": channel,
                                "feature": "p_arrival_offset_s",
                                "value": offset,
                            }
                        )
                if channel.endswith("_mean_abs"):
                    offset = _arrival_offset_s(group, origin_ms)
                    if offset is not None:
                        feature_records.append(
                            {
                                "event_id": event_id,
                                "source": source,
                                "station_id": station_id,
                                "channel": channel,
                                "feature": "s_arrival_offset_s",
                                "value": offset,
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
