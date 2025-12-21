from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import yaml

from src.utils import ensure_dir, write_json


def run_model(
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
    features_dir = output_paths.features / event_id
    features_path = features_dir / "features.parquet"
    if not features_path.exists():
        raise FileNotFoundError(f"features.parquet not found: {features_path}")

    features_df = pd.read_parquet(features_path)
    threshold = float(config.get("features", {}).get("anomaly_threshold", 3.0))
    topn = int(config.get("features", {}).get("topn_anomalies", 50))

    anomaly_df = pd.DataFrame()
    if not features_df.empty:
        features_df["value"] = pd.to_numeric(features_df["value"], errors="coerce")
        features_df["score"] = 0.0
        for name, group in features_df.groupby(["source", "channel", "feature"]):
            mean = group["value"].mean()
            std = group["value"].std() or 1.0
            score = (group["value"] - mean) / std
            features_df.loc[group.index, "score"] = score

        anomalies = features_df.loc[features_df["score"].abs() >= threshold].copy()
        anomalies = anomalies.sort_values("score", key=lambda s: s.abs(), ascending=False).head(topn)
        anomalies.insert(0, "rank", range(1, len(anomalies) + 1))
        anomaly_df = anomalies[["rank", "source", "station_id", "feature", "score"]]

    ensure_dir(features_dir)
    if not anomaly_df.empty:
        anomaly_df.to_parquet(features_dir / "anomaly.parquet", index=False)
    else:
        pd.DataFrame(columns=["rank", "source", "station_id", "feature", "score"]).to_parquet(
            features_dir / "anomaly.parquet", index=False
        )

    rulebook = {"anomaly_threshold": threshold, "topn": topn, "params_hash": params_hash}
    ensure_dir(output_paths.models)
    with (output_paths.models / "rulebook.yaml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(rulebook, handle, allow_unicode=True, sort_keys=False)

    dq = {"event_id": event_id, "anomalies": int(len(anomaly_df)), "threshold": threshold}
    write_json(features_dir / "dq_anomaly.json", dq)
