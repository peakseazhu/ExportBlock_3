from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd


def _parse_header(lines: List[str]) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    for line in lines:
        cleaned = line.strip().strip("|").strip()
        lower = cleaned.lower()
        if lower.startswith("iaga code"):
            meta["station_id"] = cleaned.split()[-1].upper()
        elif lower.startswith("geodetic latitude"):
            meta["lat"] = float(cleaned.split()[-1])
        elif lower.startswith("geodetic longitude"):
            meta["lon"] = float(cleaned.split()[-1])
        elif lower.startswith("elevation"):
            meta["elev"] = float(cleaned.split()[-1])
        elif lower.startswith("reported"):
            meta["reported"] = cleaned.split()[-1].upper()
    return meta


def _find_data_start(lines: List[str]) -> int:
    for idx, line in enumerate(lines):
        if line.strip().startswith("DATE") and "TIME" in line:
            return idx
    raise ValueError("IAGA2002 header not found (DATE/TIME).")


def _is_sentinel(value: float) -> bool:
    if pd.isna(value):
        return True
    return value >= 88888


def parse_iaga_file(
    path: Path, source: str, params_hash: str, proc_stage: str, proc_version: str
) -> pd.DataFrame:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    data_start = _find_data_start(lines)
    meta = _parse_header(lines[:data_start])

    df = pd.read_csv(path, delim_whitespace=True, skiprows=data_start, header=0)
    df = df[[col for col in df.columns if col.strip() != "|"]]
    df["ts"] = pd.to_datetime(df["DATE"] + " " + df["TIME"], utc=True, errors="coerce")
    df["ts_ms"] = (df["ts"].astype("int64") // 1_000_000).astype("int64")

    value_cols = [col for col in df.columns if col not in {"DATE", "TIME", "DOY", "ts", "ts_ms"}]
    station_id = meta.get("station_id") or value_cols[0][:3].upper()
    lat = meta.get("lat")
    lon = meta.get("lon")
    elev = meta.get("elev")

    records: List[Dict[str, Any]] = []
    for col in value_cols:
        channel = col[-1].upper()
        series = pd.to_numeric(df[col], errors="coerce")
        for ts_ms, value in zip(df["ts_ms"].tolist(), series.tolist()):
            is_missing = _is_sentinel(value)
            record = {
                "ts_ms": ts_ms,
                "source": source,
                "station_id": station_id,
                "channel": channel,
                "value": None if is_missing else float(value),
                "lat": lat,
                "lon": lon,
                "elev": elev,
                "quality_flags": {
                    "is_missing": is_missing,
                    "missing_reason": "sentinel" if is_missing else None,
                    "is_interpolated": False,
                    "interp_method": None,
                    "is_outlier": False,
                    "outlier_method": None,
                    "threshold": None,
                    "is_filtered": False,
                    "filter_type": None,
                    "filter_params": None,
                    "station_match": "exact",
                    "note": None,
                },
                "proc_stage": proc_stage,
                "proc_version": proc_version,
                "params_hash": params_hash,
            }
            records.append(record)

    return pd.DataFrame.from_records(records)
