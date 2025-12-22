from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from src.config import get_event
from src.pipeline.spatial import haversine_km
from src.store.parquet import read_parquet
from src.utils import ensure_dir, write_json


def _align_ts(ts_ms: pd.Series, interval_ms: int) -> pd.Series:
    return (ts_ms // interval_ms) * interval_ms


def _filter_by_distance(df: pd.DataFrame, lat: float, lon: float, radius_km: float) -> pd.DataFrame:
    if df.empty or df["lat"].isna().all():
        return df
    distances = df.apply(lambda row: haversine_km(lat, lon, row["lat"], row["lon"]), axis=1)
    df = df.copy()
    df["distance_km"] = distances
    return df[df["distance_km"] <= radius_km]


def run_link(
    base_dir: Path,
    config: Dict[str, Any],
    output_paths,
    run_id: str,
    params_hash: str,
    strict: bool,
    event_id: str | None,
) -> None:
    event = get_event(config, event_id)
    origin = pd.Timestamp(event["origin_time_utc"])
    pre_hours = float(config.get("time", {}).get("event_window", {}).get("pre_hours", 72))
    post_hours = float(config.get("time", {}).get("event_window", {}).get("post_hours", 24))
    start = origin - pd.Timedelta(hours=pre_hours)
    end = origin + pd.Timedelta(hours=post_hours)

    interval = config.get("time", {}).get("align_interval", "1min")
    interval_ms = int(pd.Timedelta(interval).total_seconds() * 1000)
    link_cfg = config.get("link", {}) or {}
    radius_km = float(link_cfg.get("spatial_km", 200))
    require_location = bool(link_cfg.get("require_station_location", False))

    sources = ["geomag", "aef", "seismic", "vlf"]
    aligned_frames = []
    stations_summary = []
    for source in sources:
        source_path = output_paths.standard / source
        if not source_path.exists():
            continue
        df = read_parquet(source_path)
        if df.empty:
            continue
        df = df[(df["ts_ms"] >= int(start.value // 1_000_000)) & (df["ts_ms"] <= int(end.value // 1_000_000))]
        if df.empty:
            continue
        if require_location:
            df = df.dropna(subset=["lat", "lon"])
            if df.empty:
                continue
        df = _filter_by_distance(df, event["lat"], event["lon"], radius_km)
        if df.empty:
            continue
        df = df.copy()
        if "source" not in df.columns:
            df["source"] = source
        if "distance_km" not in df.columns:
            df["distance_km"] = np.nan
        df["ts_ms"] = _align_ts(df["ts_ms"], interval_ms)
        df["event_id"] = event["event_id"]
        aligned_frames.append(df)

        station_stats = (
            df.groupby("station_id")[["lat", "lon", "elev", "distance_km"]]
            .agg({"lat": "first", "lon": "first", "elev": "first", "distance_km": "min"})
            .reset_index()
        )
        station_stats["source"] = source
        station_stats["rows"] = df.groupby("station_id").size().values
        stations_summary.extend(station_stats.to_dict(orient="records"))

    aligned_df = pd.concat(aligned_frames, ignore_index=True) if aligned_frames else pd.DataFrame()
    linked_dir = output_paths.linked / event["event_id"]
    ensure_dir(linked_dir)
    aligned_path = linked_dir / "aligned.parquet"
    if not aligned_df.empty:
        aligned_df.to_parquet(aligned_path, index=False)
    else:
        pd.DataFrame(
            columns=["ts_ms", "source", "station_id", "channel", "value", "lat", "lon", "elev", "quality_flags"]
        ).to_parquet(aligned_path, index=False)

    stations_path = linked_dir / "stations.json"
    write_json(stations_path, {"stations": stations_summary})

    expected_bins = int((end - start) / pd.Timedelta(milliseconds=interval_ms))
    observed_bins = int(aligned_df["ts_ms"].nunique()) if not aligned_df.empty else 0
    join_coverage = float(observed_bins / expected_bins) if expected_bins else 0.0

    summary = {
        "event_id": event["event_id"],
        "origin_time_utc": event["origin_time_utc"],
        "time_window": {"start": str(start), "end": str(end)},
        "sources": aligned_df["source"].value_counts().to_dict() if not aligned_df.empty else {},
        "unique_bins": observed_bins,
        "expected_bins": expected_bins,
        "join_coverage": join_coverage,
    }
    write_json(linked_dir / "summary.json", summary)
    write_json(linked_dir / "dq_linked.json", summary)

    # Event metadata for finalize
    event_payload = {
        "event_id": event["event_id"],
        "name": event.get("name"),
        "origin_time_utc": event["origin_time_utc"],
        "lat": event["lat"],
        "lon": event["lon"],
        "depth_km": event.get("depth_km"),
        "magnitude": event.get("magnitude"),
        "pipeline_version": config.get("pipeline", {}).get("version", "0.0.0"),
        "params_hash": params_hash,
        "align_interval": interval,
        "window": {"pre_hours": pre_hours, "post_hours": post_hours},
        "spatial_km": radius_km,
    }
    write_json(linked_dir / "event.json", event_payload)
