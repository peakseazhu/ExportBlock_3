from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


def _parse_data_columns(line: str) -> List[str]:
    cleaned = line.replace("|", " ").strip()
    return [col for col in cleaned.split() if col]


def _build_quality_flags(is_missing: bool, missing_reason: str | None) -> Dict[str, Any]:
    is_missing = bool(is_missing)
    return {
        "is_missing": is_missing,
        "missing_reason": missing_reason if is_missing else None,
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
    }


def parse_iaga_file(
    path: Path, source: str, params_hash: str, proc_stage: str, proc_version: str
) -> pd.DataFrame:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    data_start = _find_data_start(lines)
    meta = _parse_header(lines[:data_start])

    df = pd.read_csv(path, sep=r"\s+", skiprows=data_start, header=0)
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
                "quality_flags": _build_quality_flags(is_missing, "sentinel"),
                "proc_stage": proc_stage,
                "proc_version": proc_version,
                "params_hash": params_hash,
            }
            records.append(record)

    return pd.DataFrame.from_records(records)


def resolve_iaga_patterns(cfg: Dict[str, Any]) -> List[str]:
    read_mode = str(cfg.get("read_mode", "")).lower()
    sec_patterns = cfg.get("sec_patterns")
    min_patterns = cfg.get("min_patterns")
    if sec_patterns or min_patterns:
        if read_mode == "min":
            return list(min_patterns or [])
        if read_mode == "both":
            return list((sec_patterns or []) + (min_patterns or []))
        return list(sec_patterns or [])
    patterns = cfg.get("patterns") or []
    return list(patterns)


def _read_header_and_columns(path: Path) -> Tuple[Dict[str, Any], List[str], Iterable[str]]:
    header_lines: List[str] = []
    handle = path.open("r", encoding="utf-8", errors="ignore")
    try:
        for line in handle:
            header_lines.append(line.rstrip("\n"))
            if line.strip().startswith("DATE") and "TIME" in line:
                break
        if not header_lines:
            raise ValueError("IAGA2002 header not found.")
        meta = _parse_header(header_lines[:-1])
        header_cols = _parse_data_columns(header_lines[-1])
        return meta, header_cols, handle
    except Exception:
        handle.close()
        raise


def _find_last_data_line(path: Path) -> Optional[str]:
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        buffer = b""
        while position > 0:
            read_size = min(4096, position)
            position -= read_size
            handle.seek(position)
            chunk = handle.read(read_size)
            buffer = chunk + buffer
            if b"\n" in chunk:
                lines = buffer.splitlines()
                for raw_line in reversed(lines):
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    parts = _parse_data_columns(line)
                    if len(parts) >= 2 and parts[0][0].isdigit():
                        return line
        if buffer:
            line = buffer.decode("utf-8", errors="ignore").strip()
            return line or None
    return None


def scan_iaga_file(path: Path) -> Dict[str, Any]:
    meta, header_cols, handle = _read_header_and_columns(path)
    value_cols = [col for col in header_cols if col not in {"DATE", "TIME", "DOY"}]
    station_id = meta.get("station_id") or (value_cols[0][:3].upper() if value_cols else None)

    first_ts = None
    second_ts = None
    try:
        for line in handle:
            parts = _parse_data_columns(line)
            if len(parts) < 2:
                continue
            ts = pd.to_datetime(f"{parts[0]} {parts[1]}", utc=True, errors="coerce")
            if pd.isna(ts):
                continue
            if first_ts is None:
                first_ts = ts
            elif second_ts is None:
                second_ts = ts
                break
    finally:
        handle.close()

    last_line = _find_last_data_line(path)
    last_ts = None
    if last_line:
        parts = _parse_data_columns(last_line)
        if len(parts) >= 2:
            last_ts = pd.to_datetime(f"{parts[0]} {parts[1]}", utc=True, errors="coerce")

    interval_s = None
    if first_ts is not None and second_ts is not None:
        interval_s = float((second_ts - first_ts).total_seconds())

    return {
        "station_id": station_id,
        "lat": meta.get("lat"),
        "lon": meta.get("lon"),
        "elev": meta.get("elev"),
        "reported": meta.get("reported"),
        "start_ms": int(first_ts.value // 1_000_000) if first_ts is not None else None,
        "end_ms": int(last_ts.value // 1_000_000) if last_ts is not None else None,
        "interval_s": interval_s,
        "file_type": path.suffix.lower().lstrip("."),
        "file_path": str(path),
    }


def read_iaga_window(
    path: Path,
    source: str,
    start_ms: Optional[int],
    end_ms: Optional[int],
    limit: Optional[int],
) -> pd.DataFrame:
    meta, header_cols, handle = _read_header_and_columns(path)
    value_cols = [col for col in header_cols if col not in {"DATE", "TIME", "DOY"}]
    station_id = meta.get("station_id") or (value_cols[0][:3].upper() if value_cols else None)
    lat = meta.get("lat")
    lon = meta.get("lon")
    elev = meta.get("elev")

    records: List[Dict[str, Any]] = []
    try:
        for line in handle:
            parts = _parse_data_columns(line)
            if len(parts) < 2:
                continue
            ts = pd.to_datetime(f"{parts[0]} {parts[1]}", utc=True, errors="coerce")
            if pd.isna(ts):
                continue
            ts_ms = int(ts.value // 1_000_000)
            if start_ms is not None and ts_ms < start_ms:
                continue
            if end_ms is not None and ts_ms > end_ms:
                break
            values = parts[3:]
            if len(values) < len(value_cols):
                continue
            for col, value_text in zip(value_cols, values):
                channel = col[-1].upper()
                value = pd.to_numeric(value_text, errors="coerce")
                is_missing = _is_sentinel(value)
                records.append(
                    {
                        "ts_ms": ts_ms,
                        "source": source,
                        "station_id": station_id,
                        "channel": channel,
                        "value": None if is_missing else float(value),
                        "lat": lat,
                        "lon": lon,
                        "elev": elev,
                        "quality_flags": _build_quality_flags(is_missing, "sentinel"),
                    }
                )
                if limit is not None and len(records) >= limit:
                    return pd.DataFrame.from_records(records)
    finally:
        handle.close()
    return pd.DataFrame.from_records(records)
