from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from src.dq.reporting import write_dq_report
from src.store.parquet import read_parquet, write_parquet


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


class SpatialIndex:
    def __init__(self, stations: pd.DataFrame) -> None:
        self.stations = stations.dropna(subset=["lat", "lon"]).copy()

    def query_radius(self, lat: float, lon: float, radius_km: float) -> pd.DataFrame:
        if self.stations.empty:
            return self.stations
        distances = self.stations.apply(
            lambda row: haversine_km(lat, lon, row["lat"], row["lon"]), axis=1
        )
        result = self.stations[distances <= radius_km].copy()
        result["distance_km"] = distances[distances <= radius_km].values
        return result


def run_spatial(
    base_dir: Path,
    config: Dict[str, Any],
    output_paths,
    run_id: str,
    params_hash: str,
    strict: bool,
    event_id: str | None,
) -> None:
    stations = []
    seismic_raw = output_paths.raw / "seismic"
    if seismic_raw.exists():
        trace_df = read_parquet(seismic_raw)
        if not trace_df.empty:
            stations.append(trace_df[["station_id", "lat", "lon", "elev"]].drop_duplicates())

    if stations:
        station_df = pd.concat(stations, ignore_index=True)
    else:
        station_df = pd.DataFrame(columns=["station_id", "lat", "lon", "elev"])

    write_parquet(station_df, output_paths.reports / "spatial_index", partition_cols=None)
    report = {
        "station_count": int(len(station_df)),
        "index_type": "bruteforce",
    }
    write_dq_report(output_paths.reports / "dq_spatial.json", report)
