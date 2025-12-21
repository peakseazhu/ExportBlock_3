from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd

from src.utils import utc_now_iso, write_json


def basic_stats(df: pd.DataFrame, value_col: str = "value") -> Dict[str, Any]:
    if df.empty:
        return {
            "rows": 0,
            "ts_min": None,
            "ts_max": None,
            "missing_rate": None,
            "outlier_rate": None,
            "station_count": 0,
        }
    ts_min = int(df["ts_ms"].min())
    ts_max = int(df["ts_ms"].max())
    missing_rate = float(df[value_col].isna().mean()) if value_col in df else None
    outlier_rate = None
    if "quality_flags" in df:
        outlier_rate = float(
            df["quality_flags"].apply(lambda x: x.get("is_outlier") if isinstance(x, dict) else False).mean()
        )
    station_count = int(df["station_id"].nunique()) if "station_id" in df else 0
    return {
        "rows": int(len(df)),
        "ts_min": ts_min,
        "ts_max": ts_max,
        "missing_rate": missing_rate,
        "outlier_rate": outlier_rate,
        "station_count": station_count,
    }


def write_dq_report(path: Path, payload: Dict[str, Any]) -> None:
    payload = dict(payload)
    payload["generated_at_utc"] = utc_now_iso()
    write_json(path, payload)
