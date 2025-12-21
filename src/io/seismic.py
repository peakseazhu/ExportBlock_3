from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd
from obspy import read, read_inventory


@dataclass
class StationMeta:
    lat: float
    lon: float
    elev: float


def load_station_metadata(stationxml_path: Path) -> Dict[Tuple[str, str, str, str], StationMeta]:
    inventory = read_inventory(str(stationxml_path))
    meta: Dict[Tuple[str, str, str, str], StationMeta] = {}
    for network in inventory:
        for station in network:
            for channel in station:
                key = (network.code, station.code, channel.location_code or "", channel.code)
                meta[key] = StationMeta(channel.latitude, channel.longitude, channel.elevation)
    return meta


def extract_trace_metadata(paths: Iterable[Path]) -> pd.DataFrame:
    records: List[Dict[str, object]] = []
    for path in paths:
        stream = read(str(path))
        for trace in stream:
            stats = trace.stats
            records.append(
                {
                    "network": stats.network,
                    "station": stats.station,
                    "location": stats.location or "",
                    "channel": stats.channel,
                    "station_id": f"{stats.network}.{stats.station}.{stats.location or ''}.{stats.channel}",
                    "starttime": stats.starttime.datetime,
                    "endtime": stats.endtime.datetime,
                    "sampling_rate": float(stats.sampling_rate),
                    "npts": int(stats.npts),
                    "file_path": str(path),
                }
            )
    return pd.DataFrame.from_records(records)


def join_station_metadata(
    traces: pd.DataFrame, meta: Dict[Tuple[str, str, str, str], StationMeta]
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    if traces.empty:
        return traces, {"matched_ratio": 0, "trace_count": 0, "unmatched_keys_topN": []}

    def match_row(row: pd.Series) -> Tuple[str, StationMeta | None]:
        key = (row["network"], row["station"], row["location"], row["channel"])
        if key in meta:
            return "exact", meta[key]
        downgraded_key = (row["network"], row["station"], "", row["channel"])
        if downgraded_key in meta:
            return "downgrade", meta[downgraded_key]
        return "unmatched", None

    matches: List[str] = []
    lat: List[float] = []
    lon: List[float] = []
    elev: List[float] = []
    for _, row in traces.iterrows():
        status, station = match_row(row)
        matches.append(status)
        if station is None:
            lat.append(float("nan"))
            lon.append(float("nan"))
            elev.append(float("nan"))
        else:
            lat.append(station.lat)
            lon.append(station.lon)
            elev.append(station.elev)

    traces = traces.copy()
    traces["lat"] = lat
    traces["lon"] = lon
    traces["elev"] = elev
    traces["station_match"] = matches

    trace_count = len(traces)
    matched_ratio = float(sum(m != "unmatched" for m in matches) / trace_count)
    unmatched_keys = (
        traces.loc[traces["station_match"] == "unmatched", ["network", "station", "location", "channel"]]
        .value_counts()
        .head(10)
        .reset_index()
        .values.tolist()
    )
    report = {
        "trace_count": trace_count,
        "matched_ratio": matched_ratio,
        "unmatched_keys_topN": unmatched_keys,
    }
    return traces, report
