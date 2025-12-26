from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import yaml

from src.config import get_event
from src.utils import ensure_dir, write_json


def _association_config(config: Dict[str, Any]) -> Dict[str, Any]:
    assoc_cfg = config.get("features", {}).get("association", {}) or {}
    return {
        "change_threshold": float(assoc_cfg.get("change_threshold", 3.0)),
        "min_sources": int(assoc_cfg.get("min_sources", 2)),
        "corr_threshold": float(assoc_cfg.get("corr_threshold", 0.6)),
        "max_lag_minutes": int(assoc_cfg.get("max_lag_minutes", 30)),
        "lag_step_minutes": int(assoc_cfg.get("lag_step_minutes", 1)),
        "min_overlap": int(assoc_cfg.get("min_overlap", 30)),
        "min_points": int(assoc_cfg.get("min_points", 20)),
        "topn_pairs": int(assoc_cfg.get("topn_pairs", 50)),
    }


def _series_map(aligned_df: pd.DataFrame) -> Dict[Tuple[str, str], pd.Series]:
    df = aligned_df[["ts_ms", "source", "channel", "value"]].copy()
    df = df.dropna(subset=["ts_ms", "source", "channel"])
    if df.empty:
        return {}
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    if df.empty:
        return {}
    grouped = (
        df.groupby(["source", "channel", "ts_ms"], as_index=False)["value"]
        .median()
        .sort_values("ts_ms")
    )
    series_map: Dict[Tuple[str, str], pd.Series] = {}
    for (source, channel), group in grouped.groupby(["source", "channel"]):
        series = pd.Series(group["value"].to_numpy(), index=group["ts_ms"].to_numpy())
        series_map[(source, channel)] = series.sort_index()
    return series_map


def _zscore_series(series: pd.Series, min_points: int) -> pd.Series | None:
    values = series.dropna()
    if len(values) < min_points:
        return None
    mean = float(values.mean())
    std = float(values.std())
    if std == 0 or math.isnan(std):
        return None
    return (series - mean) / std


def _corr_with_lag(
    series_a: pd.Series, series_b: pd.Series, lag_ms: int, min_overlap: int
) -> Tuple[float | None, int]:
    if lag_ms:
        shifted = series_b.copy()
        shifted.index = shifted.index + lag_ms
    else:
        shifted = series_b
    joined = pd.concat([series_a, shifted], axis=1, join="inner").dropna()
    if len(joined) < min_overlap:
        return None, len(joined)
    corr = float(np.corrcoef(joined.iloc[:, 0], joined.iloc[:, 1])[0, 1])
    if not math.isfinite(corr):
        return None, len(joined)
    return corr, len(joined)


def _compute_association(
    config: Dict[str, Any],
    output_paths,
    event_id: str,
    params_hash: str,
) -> Tuple[Dict[str, Any], pd.DataFrame, pd.DataFrame] | None:
    linked_dir = output_paths.linked / event_id
    aligned_path = linked_dir / "aligned.parquet"
    if not aligned_path.exists():
        return None
    aligned_df = pd.read_parquet(aligned_path)
    if aligned_df.empty:
        return None
    event = get_event(config, event_id)
    origin_ms = int(pd.Timestamp(event["origin_time_utc"]).value // 1_000_000)
    assoc_cfg = _association_config(config)
    series_map = _series_map(aligned_df)
    if not series_map:
        return None

    change_rows: List[Dict[str, Any]] = []
    change_sources = set()
    for (source, channel), series in series_map.items():
        pre = series[series.index < origin_ms]
        post = series[series.index >= origin_ms]
        if pre.empty or post.empty:
            continue
        pre_mean = float(pre.mean())
        post_mean = float(post.mean())
        pre_std = float(pre.std())
        post_std = float(post.std())
        delta_mean = post_mean - pre_mean
        denom = pre_std if pre_std > 0 else 1.0
        change_score = abs(delta_mean) / denom
        flag = change_score >= assoc_cfg["change_threshold"]
        if flag:
            change_sources.add(source)
        change_rows.append(
            {
                "event_id": event_id,
                "source": source,
                "channel": channel,
                "pre_mean": pre_mean,
                "pre_std": pre_std,
                "post_mean": post_mean,
                "post_std": post_std,
                "delta_mean": delta_mean,
                "change_score": change_score,
                "change_flag": flag,
                "params_hash": params_hash,
            }
        )
    change_df = pd.DataFrame.from_records(change_rows)

    lag_step = max(1, assoc_cfg["lag_step_minutes"])
    max_lag = max(0, assoc_cfg["max_lag_minutes"])
    lag_values = list(range(-max_lag, max_lag + 1, lag_step))
    similarity_rows: List[Dict[str, Any]] = []
    keys = list(series_map.keys())
    for idx, key_a in enumerate(keys):
        for key_b in keys[idx + 1 :]:
            source_a, channel_a = key_a
            source_b, channel_b = key_b
            if source_a == source_b:
                continue
            series_a = _zscore_series(series_map[key_a], assoc_cfg["min_points"])
            series_b = _zscore_series(series_map[key_b], assoc_cfg["min_points"])
            if series_a is None or series_b is None:
                continue
            best_corr = None
            best_lag = 0
            best_n = 0
            for lag_min in lag_values:
                corr, n_overlap = _corr_with_lag(
                    series_a, series_b, lag_min * 60_000, assoc_cfg["min_overlap"]
                )
                if corr is None:
                    continue
                if best_corr is None or abs(corr) > abs(best_corr):
                    best_corr = corr
                    best_lag = lag_min
                    best_n = n_overlap
            if best_corr is None:
                continue
            similarity_rows.append(
                {
                    "event_id": event_id,
                    "source_a": source_a,
                    "channel_a": channel_a,
                    "source_b": source_b,
                    "channel_b": channel_b,
                    "corr": float(best_corr),
                    "lag_minutes": int(best_lag),
                    "overlap_points": int(best_n),
                    "similarity_flag": abs(best_corr) >= assoc_cfg["corr_threshold"],
                    "params_hash": params_hash,
                }
            )
    similarity_df = pd.DataFrame.from_records(similarity_rows)
    if not similarity_df.empty:
        similarity_df = similarity_df.sort_values(
            "corr", key=lambda s: s.abs(), ascending=False
        ).head(assoc_cfg["topn_pairs"])

    co_occurrence = len(change_sources) >= assoc_cfg["min_sources"]
    similarity_flag = (
        bool(similarity_df["similarity_flag"].any()) if not similarity_df.empty else False
    )
    association_flag = co_occurrence or similarity_flag
    summary = {
        "event_id": event_id,
        "origin_time_utc": event["origin_time_utc"],
        "change_threshold": assoc_cfg["change_threshold"],
        "corr_threshold": assoc_cfg["corr_threshold"],
        "change_sources": sorted(change_sources),
        "change_rows": int(len(change_df)),
        "similarity_rows": int(len(similarity_df)),
        "co_occurrence": co_occurrence,
        "similarity_flag": similarity_flag,
        "association_flag": association_flag,
        "params_hash": params_hash,
    }
    return summary, change_df, similarity_df


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

    association = _compute_association(config, output_paths, event_id, params_hash)
    if association is not None:
        summary, change_df, similarity_df = association
        if not change_df.empty:
            change_df.to_parquet(features_dir / "association_changes.parquet", index=False)
        else:
            pd.DataFrame(
                columns=[
                    "event_id",
                    "source",
                    "channel",
                    "pre_mean",
                    "pre_std",
                    "post_mean",
                    "post_std",
                    "delta_mean",
                    "change_score",
                    "change_flag",
                    "params_hash",
                ]
            ).to_parquet(features_dir / "association_changes.parquet", index=False)
        if not similarity_df.empty:
            similarity_df.to_parquet(features_dir / "association_similarity.parquet", index=False)
        else:
            pd.DataFrame(
                columns=[
                    "event_id",
                    "source_a",
                    "channel_a",
                    "source_b",
                    "channel_b",
                    "corr",
                    "lag_minutes",
                    "overlap_points",
                    "similarity_flag",
                    "params_hash",
                ]
            ).to_parquet(features_dir / "association_similarity.parquet", index=False)
        write_json(features_dir / "association.json", summary)

    rulebook = {"anomaly_threshold": threshold, "topn": topn, "params_hash": params_hash}
    ensure_dir(output_paths.models)
    with (output_paths.models / "rulebook.yaml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(rulebook, handle, allow_unicode=True, sort_keys=False)

    dq = {"event_id": event_id, "anomalies": int(len(anomaly_df)), "threshold": threshold}
    write_json(features_dir / "dq_anomaly.json", dq)
