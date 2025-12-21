from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Tuple

import cdflib
import numpy as np
import pandas as pd


def _station_from_name(name: str) -> str:
    match = re.search(r"vlf_([a-z0-9]+)_", name.lower())
    if match:
        return match.group(1).upper()
    return "UNKNOWN"


def read_vlf_cdf(path: Path) -> Dict[str, Any]:
    cdf = cdflib.CDF(str(path))
    epoch = cdf.varget("epoch_vlf")
    freq = cdf.varget("freq_vlf")
    ch1 = cdf.varget("ch1")
    ch2 = cdf.varget("ch2")

    epoch_dt = cdflib.cdfepoch.to_datetime(epoch)
    epoch_ns = np.array([int(pd.Timestamp(t).value) for t in epoch_dt], dtype="int64")

    pad = None
    try:
        pad = cdf.varinq("ch1").get("PadValue")
    except Exception:
        pad = None

    if pad is not None:
        ch1 = np.where(ch1 == pad, np.nan, ch1).astype("float64")
        ch2 = np.where(ch2 == pad, np.nan, ch2).astype("float64")

    station_id = _station_from_name(path.name)
    return {
        "station_id": station_id,
        "epoch_ns": epoch_ns,
        "freq_hz": np.asarray(freq, dtype="float64"),
        "ch1": np.asarray(ch1, dtype="float64"),
        "ch2": np.asarray(ch2, dtype="float64"),
    }


def compute_gap_report(epoch_ns: np.ndarray) -> Dict[str, Any]:
    if len(epoch_ns) < 2:
        return {"gap_count": 0, "gap_indices": [], "dt_median_s": None}
    diffs = np.diff(epoch_ns) / 1e9
    dt_median = float(np.median(diffs))
    gap_indices = np.where(diffs > dt_median * 2)[0].tolist()
    return {
        "gap_count": len(gap_indices),
        "gap_indices": gap_indices,
        "dt_median_s": dt_median,
    }
