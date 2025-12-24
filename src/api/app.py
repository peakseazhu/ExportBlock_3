import json
import math
import os
import zipfile
from pathlib import Path
from typing import List, Optional

import pandas as pd
import pyarrow.dataset as ds
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.io.iaga2002 import read_iaga_window
from src.io.seismic import StationMeta, read_mseed_window
from src.store.parquet import read_parquet, read_parquet_filtered

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = Path(os.getenv("OUTPUT_ROOT", ROOT / "outputs"))

app = FastAPI(title="ExportBlock-3 API")
app.mount("/outputs", StaticFiles(directory=OUTPUT_ROOT), name="outputs")

templates = Jinja2Templates(directory=str(ROOT / "templates"))


def _parse_time(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit() and len(text) in (10, 13):
        ts = int(text)
        if len(text) == 10:
            ts *= 1000
        return ts
    return int(pd.Timestamp(text).value // 1_000_000)


def _filter_df(
    df: pd.DataFrame,
    start: Optional[str],
    end: Optional[str],
    station_id: Optional[str],
    lat_min: Optional[float],
    lat_max: Optional[float],
    lon_min: Optional[float],
    lon_max: Optional[float],
    limit: int,
):
    if df.empty:
        return df
    start_ms = _parse_time(start)
    end_ms = _parse_time(end)
    if "ts_ms" in df.columns:
        if start_ms is not None:
            df = df[df["ts_ms"] >= start_ms]
        if end_ms is not None:
            df = df[df["ts_ms"] <= end_ms]
    elif "starttime" in df.columns and "endtime" in df.columns:
        start_ts = pd.to_datetime(start_ms, unit="ms", utc=True) if start_ms is not None else None
        end_ts = pd.to_datetime(end_ms, unit="ms", utc=True) if end_ms is not None else None
        if start_ts is not None:
            df = df[df["endtime"] >= start_ts]
        if end_ts is not None:
            df = df[df["starttime"] <= end_ts]
    if station_id:
        df = df[df["station_id"] == station_id]
    if lat_min is not None and "lat" in df.columns:
        df = df[df["lat"] >= lat_min]
    if lat_max is not None and "lat" in df.columns:
        df = df[df["lat"] <= lat_max]
    if lon_min is not None and "lon" in df.columns:
        df = df[df["lon"] >= lon_min]
    if lon_max is not None and "lon" in df.columns:
        df = df[df["lon"] <= lon_max]
    if limit:
        df = df.head(limit)
    return df


def _query_df(
    df: pd.DataFrame,
    start: Optional[str],
    end: Optional[str],
    station_id: Optional[str],
    lat_min: Optional[float],
    lat_max: Optional[float],
    lon_min: Optional[float],
    lon_max: Optional[float],
    limit: int,
):
    return _filter_df(df, start, end, station_id, lat_min, lat_max, lon_min, lon_max, limit).to_dict(
        orient="records"
    )


def _format_utc(value: pd.Timestamp) -> str:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.isoformat().replace("+00:00", "Z")


def _summarize_df(df: pd.DataFrame) -> dict:
    summary = {"rows": int(len(df)), "columns": list(df.columns)}
    if df.empty:
        return summary
    if "ts_ms" in df.columns:
        ts_min = pd.to_datetime(df["ts_ms"].min(), unit="ms", utc=True)
        ts_max = pd.to_datetime(df["ts_ms"].max(), unit="ms", utc=True)
        summary["ts_min_utc"] = _format_utc(ts_min)
        summary["ts_max_utc"] = _format_utc(ts_max)
    if "starttime" in df.columns and "endtime" in df.columns:
        summary["start_min_utc"] = _format_utc(df["starttime"].min())
        summary["end_max_utc"] = _format_utc(df["endtime"].max())
    return summary


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_partition_filter(
    fields: set[str],
    start_ms: Optional[int],
    end_ms: Optional[int],
    station_id: Optional[str],
) -> Optional[ds.Expression]:
    expr = None
    if station_id and "station_id" in fields:
        expr = ds.field("station_id") == station_id
    if (start_ms is not None or end_ms is not None) and "date" in fields:
        start_date = (
            pd.to_datetime(start_ms, unit="ms", utc=True).strftime("%Y-%m-%d") if start_ms is not None else None
        )
        end_date = (
            pd.to_datetime(end_ms, unit="ms", utc=True).strftime("%Y-%m-%d") if end_ms is not None else None
        )
        if start_date:
            expr = (expr & (ds.field("date") >= start_date)) if expr is not None else ds.field("date") >= start_date
        if end_date:
            expr = (expr & (ds.field("date") <= end_date)) if expr is not None else ds.field("date") <= end_date
    return expr


def _raw_index_dir(source: str) -> Path:
    return OUTPUT_ROOT / "raw" / "index" / f"source={source}"


def _load_raw_index(source: str, station_id: Optional[str] = None) -> pd.DataFrame:
    index_dir = _raw_index_dir(source)
    if not index_dir.exists():
        raise HTTPException(status_code=404, detail=f"Raw index not found: {source}")
    if station_id:
        return read_parquet_filtered(index_dir, filters=ds.field("station_id") == station_id)
    return read_parquet(index_dir)


def _resolve_raw_file(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _filter_index(
    df: pd.DataFrame,
    start_ms: Optional[int],
    end_ms: Optional[int],
    station_id: Optional[str],
    lat_min: Optional[float],
    lat_max: Optional[float],
    lon_min: Optional[float],
    lon_max: Optional[float],
) -> pd.DataFrame:
    if df.empty:
        return df
    filtered = df.copy()
    if station_id and "station_id" in filtered.columns:
        filtered = filtered[filtered["station_id"] == station_id]
    if "start_ms" in filtered.columns and "end_ms" in filtered.columns:
        if start_ms is not None:
            filtered = filtered[filtered["end_ms"] >= start_ms]
        if end_ms is not None:
            filtered = filtered[filtered["start_ms"] <= end_ms]
    if lat_min is not None and "lat" in filtered.columns:
        filtered = filtered[filtered["lat"] >= lat_min]
    if lat_max is not None and "lat" in filtered.columns:
        filtered = filtered[filtered["lat"] <= lat_max]
    if lon_min is not None and "lon" in filtered.columns:
        filtered = filtered[filtered["lon"] >= lon_min]
    if lon_max is not None and "lon" in filtered.columns:
        filtered = filtered[filtered["lon"] <= lon_max]
    return filtered


def _build_row_filter(
    fields: set[str],
    start_ms: Optional[int],
    end_ms: Optional[int],
    station_id: Optional[str],
    lat_min: Optional[float],
    lat_max: Optional[float],
    lon_min: Optional[float],
    lon_max: Optional[float],
) -> Optional[ds.Expression]:
    expr = None
    if station_id and "station_id" in fields:
        expr = ds.field("station_id") == station_id
    if (start_ms is not None or end_ms is not None) and "ts_ms" in fields:
        if start_ms is not None:
            expr = (expr & (ds.field("ts_ms") >= start_ms)) if expr is not None else ds.field("ts_ms") >= start_ms
        if end_ms is not None:
            expr = (expr & (ds.field("ts_ms") <= end_ms)) if expr is not None else ds.field("ts_ms") <= end_ms
    if (start_ms is not None or end_ms is not None) and {"starttime", "endtime"}.issubset(fields):
        start_ts = pd.to_datetime(start_ms, unit="ms", utc=True) if start_ms is not None else None
        end_ts = pd.to_datetime(end_ms, unit="ms", utc=True) if end_ms is not None else None
        if start_ts is not None:
            expr = (expr & (ds.field("endtime") >= start_ts)) if expr is not None else ds.field("endtime") >= start_ts
        if end_ts is not None:
            expr = (expr & (ds.field("starttime") <= end_ts)) if expr is not None else ds.field("starttime") <= end_ts
    if lat_min is not None and "lat" in fields:
        expr = (expr & (ds.field("lat") >= lat_min)) if expr is not None else ds.field("lat") >= lat_min
    if lat_max is not None and "lat" in fields:
        expr = (expr & (ds.field("lat") <= lat_max)) if expr is not None else ds.field("lat") <= lat_max
    if lon_min is not None and "lon" in fields:
        expr = (expr & (ds.field("lon") >= lon_min)) if expr is not None else ds.field("lon") >= lon_min
    if lon_max is not None and "lon" in fields:
        expr = (expr & (ds.field("lon") <= lon_max)) if expr is not None else ds.field("lon") <= lon_max
    return expr


def _combine_filters(*filters: Optional[ds.Expression]) -> Optional[ds.Expression]:
    expr = None
    for item in filters:
        if item is None:
            continue
        expr = (expr & item) if expr is not None else item
    return expr


def _dataset_fields(path: Path) -> set[str]:
    dataset = ds.dataset(path, format="parquet", partitioning="hive")
    return set(dataset.schema.names)


def _summarize_vlf_catalog(df: pd.DataFrame) -> dict:
    summary = {"rows": int(len(df)), "columns": list(df.columns)}
    if df.empty:
        return summary
    if "ts_start_ns" in df.columns and "ts_end_ns" in df.columns:
        ts_min = pd.to_datetime(df["ts_start_ns"].min(), unit="ns", utc=True)
        ts_max = pd.to_datetime(df["ts_end_ns"].max(), unit="ns", utc=True)
        summary["ts_min_utc"] = _format_utc(ts_min)
        summary["ts_max_utc"] = _format_utc(ts_max)
    return summary


def _event_window_ms(
    event_id: str, start: Optional[str], end: Optional[str]
) -> tuple[int, int, dict]:
    event_path = OUTPUT_ROOT / "linked" / event_id / "event.json"
    if not event_path.exists():
        raise HTTPException(status_code=404, detail="event.json not found")
    event = _load_json(event_path)
    start_ms = _parse_time(start)
    end_ms = _parse_time(end)
    if start_ms is None or end_ms is None:
        origin = pd.Timestamp(event["origin_time_utc"])
        window = event.get("window", {}) or {}
        pre_hours = float(window.get("pre_hours", 72))
        post_hours = float(window.get("post_hours", 24))
        default_start = origin - pd.Timedelta(hours=pre_hours)
        default_end = origin + pd.Timedelta(hours=post_hours)
        if start_ms is None:
            start_ms = int(default_start.value // 1_000_000)
        if end_ms is None:
            end_ms = int(default_end.value // 1_000_000)
    return start_ms, end_ms, event


def _collect_seismic_raw(
    start_ms: Optional[int], end_ms: Optional[int], station_id: Optional[str], limit: int
) -> pd.DataFrame:
    index_df = _load_raw_index("seismic", station_id)
    filtered_index = _filter_index(index_df, start_ms, end_ms, station_id, None, None, None, None)
    if filtered_index.empty:
        return pd.DataFrame()
    station_meta = {}
    for _, row in filtered_index.drop_duplicates(subset=["station_id"]).iterrows():
        station_meta[row["station_id"]] = StationMeta(
            float(row.get("lat", float("nan"))),
            float(row.get("lon", float("nan"))),
            float(row.get("elev", float("nan"))),
        )
    remaining = int(limit) if limit else None
    chunks: List[pd.DataFrame] = []
    for file_path, group in filtered_index.groupby("file_path"):
        if remaining is not None and remaining <= 0:
            break
        station_ids = set(group["station_id"].tolist())
        df = read_mseed_window(
            _resolve_raw_file(file_path),
            start_ms,
            end_ms,
            station_ids,
            remaining,
            station_meta,
        )
        if df.empty:
            continue
        df["proc_stage"] = "raw"
        df["proc_version"] = group["proc_version"].iloc[0] if "proc_version" in group.columns else None
        df["params_hash"] = group["params_hash"].iloc[0] if "params_hash" in group.columns else None
        chunks.append(df)
        if remaining is not None:
            remaining -= len(df)
    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)


def _vlf_zarr_path(station_id: str, file_path: str) -> Path:
    stem = Path(file_path).stem
    return OUTPUT_ROOT / "raw" / "vlf" / station_id / stem / "spectrogram.zarr"


def _slice_vlf_zarr(
    zarr_path: Path,
    start_ns: Optional[int],
    end_ns: Optional[int],
    freq_min: Optional[float],
    freq_max: Optional[float],
    max_time: int,
    max_freq: int,
) -> Optional[dict]:
    if not zarr_path.exists():
        return None
    import numpy as np
    import zarr

    root = zarr.open(str(zarr_path), mode="r")
    epoch_ns = np.asarray(root["epoch_ns"][:])
    freq_hz = np.asarray(root["freq_hz"][:])
    if epoch_ns.size == 0 or freq_hz.size == 0:
        return None
    t_start = 0
    t_end = int(len(epoch_ns))
    if start_ns is not None:
        t_start = int(np.searchsorted(epoch_ns, start_ns, side="left"))
    if end_ns is not None:
        t_end = int(np.searchsorted(epoch_ns, end_ns, side="right"))
    f_start = 0
    f_end = int(len(freq_hz))
    if freq_min is not None:
        f_start = int(np.searchsorted(freq_hz, freq_min, side="left"))
    if freq_max is not None:
        f_end = int(np.searchsorted(freq_hz, freq_max, side="right"))
    if t_end <= t_start or f_end <= f_start:
        return None
    time_step = 1
    if max_time and max_time > 0:
        time_step = max(1, int(math.ceil((t_end - t_start) / max_time)))
    freq_step = 1
    if max_freq and max_freq > 0:
        freq_step = max(1, int(math.ceil((f_end - f_start) / max_freq)))
    time_slice = slice(t_start, t_end, time_step)
    freq_slice = slice(f_start, f_end, freq_step)
    epoch_sel = epoch_ns[time_slice]
    freq_sel = freq_hz[freq_slice]
    ch1 = root["ch1"][time_slice, freq_slice]
    ch2 = root["ch2"][time_slice, freq_slice] if "ch2" in root.array_keys() else None
    return {
        "epoch_ns": epoch_sel.tolist(),
        "freq_hz": freq_sel.tolist(),
        "ch1": ch1.tolist(),
        "ch2": ch2.tolist() if ch2 is not None else None,
    }


def _collect_vlf_slice(
    index_df: pd.DataFrame,
    station_id: Optional[str],
    start_ns: Optional[int],
    end_ns: Optional[int],
    freq_min: Optional[float],
    freq_max: Optional[float],
    max_time: int,
    max_freq: int,
    max_files: int,
) -> Optional[dict]:
    df = index_df.copy()
    if station_id:
        df = df[df["station_id"] == station_id]
    if start_ns is not None:
        df = df[df["ts_end_ns"] >= start_ns]
    if end_ns is not None:
        df = df[df["ts_start_ns"] <= end_ns]
    if df.empty:
        return None
    df = df.sort_values("ts_start_ns")
    if max_files and max_files > 0:
        df = df.head(max_files)
    payloads = []
    files = []
    for _, row in df.iterrows():
        file_path = row.get("file_path") or row.get("file")
        if not file_path:
            continue
        files.append(str(file_path))
        zarr_path = _vlf_zarr_path(row["station_id"], str(file_path))
        payload = _slice_vlf_zarr(
            zarr_path, start_ns, end_ns, freq_min, freq_max, max_time, max_freq
        )
        if payload:
            payloads.append(payload)
    if not payloads:
        return None
    if len(payloads) == 1:
        payload = payloads[0]
        payload["station_id"] = station_id or df.iloc[0]["station_id"]
        payload["files"] = files
        return payload
    import numpy as np

    freq_ref = np.asarray(payloads[0]["freq_hz"])
    epochs = []
    ch1s = []
    ch2s = []
    for payload in payloads:
        freq = np.asarray(payload["freq_hz"])
        if freq.shape != freq_ref.shape or not np.allclose(freq, freq_ref):
            payload = payloads[0]
            payload["station_id"] = station_id or df.iloc[0]["station_id"]
            payload["files"] = files
            payload["note"] = "multiple files matched; returned first due to freq mismatch"
            return payload
        epochs.append(np.asarray(payload["epoch_ns"]))
        ch1s.append(np.asarray(payload["ch1"]))
        if payload.get("ch2") is not None:
            ch2s.append(np.asarray(payload["ch2"]))
    epoch_ns = np.concatenate(epochs, axis=0) if epochs else np.array([])
    ch1 = np.concatenate(ch1s, axis=0) if ch1s else np.array([])
    ch2 = np.concatenate(ch2s, axis=0) if ch2s else None
    return {
        "station_id": station_id or df.iloc[0]["station_id"],
        "files": files,
        "epoch_ns": epoch_ns.tolist(),
        "freq_hz": freq_ref.tolist(),
        "ch1": ch1.tolist(),
        "ch2": ch2.tolist() if ch2 is not None else None,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/raw/query")
def raw_query(
    source: str = Query(..., description="geomag|aef|seismic|vlf"),
    start: Optional[str] = None,
    end: Optional[str] = None,
    station_id: Optional[str] = None,
    lat_min: Optional[float] = None,
    lat_max: Optional[float] = None,
    lon_min: Optional[float] = None,
    lon_max: Optional[float] = None,
    limit: int = 5000,
    response: Response = None,
):
    start_ms = _parse_time(start)
    end_ms = _parse_time(end)

    index_df = _load_raw_index(source, station_id)

    if source == "vlf":
        df = index_df
        if station_id:
            df = df[df["station_id"] == station_id]
        if start_ms is not None:
            start_ns = start_ms * 1_000_000
            df = df[df["ts_end_ns"] >= start_ns]
        if end_ms is not None:
            end_ns = end_ms * 1_000_000
            df = df[df["ts_start_ns"] <= end_ns]
        if limit:
            df = df.head(limit)
        summary = _summarize_vlf_catalog(df)
        filtered = df
    else:
        filtered_index = _filter_index(index_df, start_ms, end_ms, station_id, lat_min, lat_max, lon_min, lon_max)
        if filtered_index.empty:
            summary = {"rows": 0, "columns": []}
            filtered = pd.DataFrame()
        else:
            filtered_index = filtered_index.sort_values("start_ms")
            remaining = int(limit) if limit else None
            chunks: List[pd.DataFrame] = []
            if source in {"geomag", "aef"}:
                for _, row in filtered_index.iterrows():
                    if remaining is not None and remaining <= 0:
                        break
                    df = read_iaga_window(
                        _resolve_raw_file(row["file_path"]),
                        source,
                        start_ms,
                        end_ms,
                        remaining,
                    )
                    if df.empty:
                        continue
                    df["proc_stage"] = "raw"
                    df["proc_version"] = row.get("proc_version")
                    df["params_hash"] = row.get("params_hash")
                    chunks.append(df)
                    if remaining is not None:
                        remaining -= len(df)
            elif source == "seismic":
                station_meta = {}
                for _, row in filtered_index.drop_duplicates(subset=["station_id"]).iterrows():
                    station_meta[row["station_id"]] = StationMeta(
                        float(row.get("lat", float("nan"))),
                        float(row.get("lon", float("nan"))),
                        float(row.get("elev", float("nan"))),
                    )
                for file_path, group in filtered_index.groupby("file_path"):
                    if remaining is not None and remaining <= 0:
                        break
                    station_ids = set(group["station_id"].tolist())
                    df = read_mseed_window(
                        _resolve_raw_file(file_path),
                        start_ms,
                        end_ms,
                        station_ids,
                        remaining,
                        station_meta,
                    )
                    if df.empty:
                        continue
                    df["proc_stage"] = "raw"
                    df["proc_version"] = group["proc_version"].iloc[0] if "proc_version" in group.columns else None
                    df["params_hash"] = group["params_hash"].iloc[0] if "params_hash" in group.columns else None
                    chunks.append(df)
                    if remaining is not None:
                        remaining -= len(df)
            if chunks:
                df = pd.concat(chunks, ignore_index=True)
                filtered = _filter_df(df, start, end, station_id, lat_min, lat_max, lon_min, lon_max, limit)
                summary = _summarize_df(df)
            else:
                filtered = pd.DataFrame()
                summary = {"rows": 0, "columns": []}
    if response is not None:
        response.headers["X-Result-Count"] = str(len(filtered))
        response.headers["X-Source-Rows"] = str(summary["rows"])
        if summary.get("ts_min_utc") and summary.get("ts_max_utc"):
            response.headers["X-Source-Time-Range"] = f"{summary['ts_min_utc']}..{summary['ts_max_utc']}"
        elif summary.get("start_min_utc") and summary.get("end_max_utc"):
            response.headers["X-Source-Time-Range"] = (
                f"{summary['start_min_utc']}..{summary['end_max_utc']}"
            )
    return filtered.to_dict(orient="records")


@app.get("/raw/vlf/slice")
def raw_vlf_slice(
    station_id: str = Query(..., description="station id (e.g., KAK)"),
    start: Optional[str] = None,
    end: Optional[str] = None,
    freq_min: Optional[float] = None,
    freq_max: Optional[float] = None,
    max_time: int = 400,
    max_freq: int = 256,
    max_files: int = 1,
):
    start_ms = _parse_time(start)
    end_ms = _parse_time(end)
    start_ns = start_ms * 1_000_000 if start_ms is not None else None
    end_ns = end_ms * 1_000_000 if end_ms is not None else None
    index_df = _load_raw_index("vlf", station_id)
    payload = _collect_vlf_slice(
        index_df,
        station_id,
        start_ns,
        end_ns,
        freq_min,
        freq_max,
        max_time,
        max_freq,
        max_files,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="No VLF slice data found")
    return payload


@app.get("/standard/query")
def standard_query(
    source: str = Query(..., description="geomag|aef|seismic|vlf"),
    start: Optional[str] = None,
    end: Optional[str] = None,
    station_id: Optional[str] = None,
    lat_min: Optional[float] = None,
    lat_max: Optional[float] = None,
    lon_min: Optional[float] = None,
    lon_max: Optional[float] = None,
    limit: int = 5000,
    response: Response = None,
):
    source_path = OUTPUT_ROOT / "standard" / f"source={source}"
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Standard source not found: {source}")
    start_ms = _parse_time(start)
    end_ms = _parse_time(end)
    fields = _dataset_fields(source_path)
    partition_filter = _build_partition_filter(fields, start_ms, end_ms, station_id)
    row_filter = _build_row_filter(
        fields, start_ms, end_ms, station_id, lat_min, lat_max, lon_min, lon_max
    )
    combined = _combine_filters(partition_filter, row_filter)
    df = read_parquet_filtered(source_path, filters=combined, limit=limit)
    summary = _summarize_df(df)
    filtered = _filter_df(df, start, end, station_id, lat_min, lat_max, lon_min, lon_max, limit)
    if response is not None:
        response.headers["X-Result-Count"] = str(len(filtered))
        response.headers["X-Source-Rows"] = str(summary["rows"])
        if summary.get("ts_min_utc") and summary.get("ts_max_utc"):
            response.headers["X-Source-Time-Range"] = f"{summary['ts_min_utc']}..{summary['ts_max_utc']}"
        elif summary.get("start_min_utc") and summary.get("end_max_utc"):
            response.headers["X-Source-Time-Range"] = (
                f"{summary['start_min_utc']}..{summary['end_max_utc']}"
            )
    return filtered.to_dict(orient="records")


@app.get("/raw/summary")
def raw_summary(source: str = Query(..., description="geomag|aef|seismic|vlf")):
    df = _load_raw_index(source)
    if source == "vlf":
        summary = _summarize_vlf_catalog(df)
    else:
        summary = {"rows": int(len(df)), "columns": list(df.columns)}
        if not df.empty and {"start_ms", "end_ms"}.issubset(df.columns):
            ts_min = pd.to_datetime(df["start_ms"].min(), unit="ms", utc=True)
            ts_max = pd.to_datetime(df["end_ms"].max(), unit="ms", utc=True)
            summary["ts_min_utc"] = _format_utc(ts_min)
            summary["ts_max_utc"] = _format_utc(ts_max)
    summary["source"] = source
    summary["stage"] = "raw"
    return summary


@app.get("/standard/summary")
def standard_summary(source: str = Query(..., description="geomag|aef|seismic|vlf")):
    source_path = OUTPUT_ROOT / "standard" / f"source={source}"
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Standard source not found: {source}")
    fields = _dataset_fields(source_path)
    summary_cols = [col for col in ["ts_ms", "starttime", "endtime"] if col in fields]
    df = read_parquet_filtered(source_path, columns=summary_cols)
    summary = _summarize_df(df)
    summary["source"] = source
    summary["stage"] = "standard"
    return summary


@app.get("/events")
def list_events(include_incomplete: bool = False):
    events = []
    event_root = OUTPUT_ROOT / "events"
    if not event_root.exists():
        return events
    for event_dir in event_root.iterdir():
        if not event_dir.is_dir():
            continue
        done = (event_dir / "DONE").exists()
        fail = (event_dir / "FAIL").exists()
        if not include_incomplete and (not done or fail):
            continue
        events.append({"event_id": event_dir.name, "ready": done and not fail})
    return events


@app.get("/events/{event_id}/linked")
def get_linked(event_id: str, limit: int = 5000):
    path = OUTPUT_ROOT / "linked" / event_id / "aligned.parquet"
    if not path.exists():
        raise HTTPException(status_code=404, detail="aligned.parquet not found")
    df = pd.read_parquet(path)
    return df.head(limit).to_dict(orient="records")


@app.get("/events/{event_id}/features")
def get_features(event_id: str):
    path = OUTPUT_ROOT / "features" / event_id / "features.parquet"
    if not path.exists():
        raise HTTPException(status_code=404, detail="features.parquet not found")
    df = pd.read_parquet(path)
    return df.to_dict(orient="records")


@app.get("/events/{event_id}/anomaly")
def get_anomaly(event_id: str):
    path = OUTPUT_ROOT / "features" / event_id / "anomaly.parquet"
    if not path.exists():
        raise HTTPException(status_code=404, detail="anomaly.parquet not found")
    df = pd.read_parquet(path)
    return df.to_dict(orient="records")


@app.get("/events/{event_id}/plots")
def get_plot(event_id: str, kind: str):
    path = OUTPUT_ROOT / "plots" / "spec" / event_id / f"plot_{kind}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="plot spec not found")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/events/{event_id}/seismic/export")
def export_event_seismic(
    event_id: str,
    format: str = Query("csv", description="csv|hdf5|json"),
    start: Optional[str] = None,
    end: Optional[str] = None,
    station_id: Optional[str] = None,
    limit: int = 20000,
):
    start_ms, end_ms, _ = _event_window_ms(event_id, start, end)
    df = _collect_seismic_raw(start_ms, end_ms, station_id, limit)
    if df.empty:
        raise HTTPException(status_code=404, detail="No seismic raw data for event window")
    export_dir = OUTPUT_ROOT / "events" / event_id / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    if format == "hdf5":
        export_path = export_dir / "seismic_raw.h5"
        df.to_hdf(export_path, key="data", mode="w")
    elif format == "json":
        export_path = export_dir / "seismic_raw.json"
        export_path.write_text(df.to_json(orient="records"), encoding="utf-8")
    else:
        export_path = export_dir / "seismic_raw.csv"
        df.to_csv(export_path, index=False)
    return FileResponse(export_path)


@app.get("/events/{event_id}/vlf/export")
def export_event_vlf(
    event_id: str,
    station_id: str = Query(..., description="station id (e.g., KAK)"),
    format: str = Query("json", description="json|npz"),
    start: Optional[str] = None,
    end: Optional[str] = None,
    freq_min: Optional[float] = None,
    freq_max: Optional[float] = None,
    max_time: int = 400,
    max_freq: int = 256,
    max_files: int = 1,
):
    start_ms, end_ms, _ = _event_window_ms(event_id, start, end)
    start_ns = start_ms * 1_000_000 if start_ms is not None else None
    end_ns = end_ms * 1_000_000 if end_ms is not None else None
    index_df = _load_raw_index("vlf", station_id)
    payload = _collect_vlf_slice(
        index_df,
        station_id,
        start_ns,
        end_ns,
        freq_min,
        freq_max,
        max_time,
        max_freq,
        max_files,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="No VLF data for event window")
    export_dir = OUTPUT_ROOT / "events" / event_id / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    if format == "npz":
        import numpy as np

        export_path = export_dir / "vlf_raw.npz"
        np.savez(
            export_path,
            epoch_ns=payload["epoch_ns"],
            freq_hz=payload["freq_hz"],
            ch1=payload["ch1"],
            ch2=payload["ch2"] if payload.get("ch2") is not None else [],
        )
    else:
        export_path = export_dir / "vlf_raw.json"
        export_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return FileResponse(export_path)


@app.get("/events/{event_id}/export")
def export_event(
    event_id: str,
    format: str = Query("csv", description="csv|hdf5"),
    start: Optional[str] = None,
    end: Optional[str] = None,
    include_raw: bool = False,
    raw_limit: int = 20000,
    raw_seismic_format: str = Query("csv", description="csv|hdf5|json"),
    raw_vlf_format: str = Query("json", description="json|npz"),
    raw_vlf_station_id: Optional[str] = None,
    raw_vlf_max_time: int = 400,
    raw_vlf_max_freq: int = 256,
    raw_vlf_max_files: int = 1,
):
    path = OUTPUT_ROOT / "linked" / event_id / "aligned.parquet"
    if not path.exists():
        raise HTTPException(status_code=404, detail="aligned.parquet not found")
    df = pd.read_parquet(path)
    start_ms = _parse_time(start)
    end_ms = _parse_time(end)
    if include_raw or start_ms is None or end_ms is None:
        try:
            start_ms, end_ms, _ = _event_window_ms(event_id, start, end)
        except HTTPException:
            if "ts_ms" in df.columns:
                start_ms = int(df["ts_ms"].min())
                end_ms = int(df["ts_ms"].max())
            else:
                start_ms = _parse_time(start)
                end_ms = _parse_time(end)
    start_text = start or (_format_utc(pd.to_datetime(start_ms, unit="ms", utc=True)) if start_ms else None)
    end_text = end or (_format_utc(pd.to_datetime(end_ms, unit="ms", utc=True)) if end_ms else None)
    records = _query_df(df, start_text, end_text, None, None, None, None, None, 0)
    export_dir = OUTPUT_ROOT / "events" / event_id / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    if format == "hdf5":
        export_path = export_dir / "aligned.h5"
        pd.DataFrame(records).to_hdf(export_path, key="data", mode="w")
    else:
        export_path = export_dir / "aligned.csv"
        pd.DataFrame(records).to_csv(export_path, index=False)
    if not include_raw:
        return FileResponse(export_path)

    bundle_path = export_dir / "export_bundle.zip"
    manifest = {"aligned": export_path.name, "seismic_raw": None, "vlf_raw": None, "notes": []}

    seismic_df = pd.DataFrame()
    try:
        seismic_df = _collect_seismic_raw(start_ms, end_ms, None, raw_limit)
    except HTTPException:
        manifest["notes"].append("seismic raw index not found; skip seismic raw")
    if not seismic_df.empty:
        if raw_seismic_format == "hdf5":
            seismic_path = export_dir / "seismic_raw.h5"
            seismic_df.to_hdf(seismic_path, key="data", mode="w")
        elif raw_seismic_format == "json":
            seismic_path = export_dir / "seismic_raw.json"
            seismic_path.write_text(seismic_df.to_json(orient="records"), encoding="utf-8")
        else:
            seismic_path = export_dir / "seismic_raw.csv"
            seismic_df.to_csv(seismic_path, index=False)
        manifest["seismic_raw"] = seismic_path.name
    else:
        manifest["notes"].append("no seismic raw data in event window")

    vlf_index = None
    if include_raw:
        try:
            vlf_index = _load_raw_index("vlf")
        except HTTPException:
            manifest["notes"].append("vlf raw index not found; skip vlf raw")
    vlf_payload = None
    if vlf_index is not None and raw_vlf_station_id is None:
        stations = vlf_index["station_id"].dropna().unique().tolist()
        if len(stations) == 1:
            raw_vlf_station_id = stations[0]
        elif stations:
            manifest["notes"].append("multiple VLF stations found; set raw_vlf_station_id to export")
    if vlf_index is not None and raw_vlf_station_id:
        start_ns = start_ms * 1_000_000 if start_ms is not None else None
        end_ns = end_ms * 1_000_000 if end_ms is not None else None
        vlf_payload = _collect_vlf_slice(
            vlf_index,
            raw_vlf_station_id,
            start_ns,
            end_ns,
            None,
            None,
            raw_vlf_max_time,
            raw_vlf_max_freq,
            raw_vlf_max_files,
        )
    if vlf_payload:
        if raw_vlf_format == "npz":
            import numpy as np

            vlf_path = export_dir / "vlf_raw.npz"
            np.savez(
                vlf_path,
                epoch_ns=vlf_payload["epoch_ns"],
                freq_hz=vlf_payload["freq_hz"],
                ch1=vlf_payload["ch1"],
                ch2=vlf_payload["ch2"] if vlf_payload.get("ch2") is not None else [],
            )
        else:
            vlf_path = export_dir / "vlf_raw.json"
            vlf_path.write_text(json.dumps(vlf_payload, ensure_ascii=False), encoding="utf-8")
        manifest["vlf_raw"] = vlf_path.name
    else:
        manifest["notes"].append("no vlf raw data exported (set raw_vlf_station_id)")

    manifest_path = export_dir / "export_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(export_path, arcname=export_path.name)
        bundle.write(manifest_path, arcname=manifest_path.name)
        if manifest["seismic_raw"]:
            bundle.write(export_dir / manifest["seismic_raw"], arcname=manifest["seismic_raw"])
        if manifest["vlf_raw"]:
            bundle.write(export_dir / manifest["vlf_raw"], arcname=manifest["vlf_raw"])
    return FileResponse(bundle_path)


@app.get("/ui", response_class=HTMLResponse)
def ui_index(request: Request):
    events = list_events(include_incomplete=False)
    return templates.TemplateResponse("ui_index.html", {"request": request, "events": events})


@app.get("/ui/events/{event_id}", response_class=HTMLResponse)
def ui_event(request: Request, event_id: str):
    event_dir = OUTPUT_ROOT / "events" / event_id
    if not event_dir.exists():
        raise HTTPException(status_code=404, detail="event not found")
    linked_summary = {}
    event_meta = {}
    summary_path = OUTPUT_ROOT / "linked" / event_id / "summary.json"
    if summary_path.exists():
        linked_summary = _load_json(summary_path)
    event_path = OUTPUT_ROOT / "linked" / event_id / "event.json"
    if event_path.exists():
        event_meta = _load_json(event_path)
    features_preview = []
    features_total = 0
    features_path = OUTPUT_ROOT / "features" / event_id / "features.parquet"
    if features_path.exists():
        df = pd.read_parquet(
            features_path, columns=["source", "station_id", "channel", "feature", "value"]
        )
        features_total = int(len(df))
        features_preview = df.head(50).to_dict(orient="records")
    anomalies_preview = []
    anomalies_total = 0
    anomaly_path = OUTPUT_ROOT / "features" / event_id / "anomaly.parquet"
    if anomaly_path.exists():
        df = pd.read_parquet(anomaly_path, columns=["rank", "source", "station_id", "feature", "score"])
        anomalies_total = int(len(df))
        anomalies_preview = df.head(20).to_dict(orient="records")
    plots = {
        "aligned_timeseries": f"/outputs/plots/html/{event_id}/plot_aligned_timeseries.html",
        "station_map": f"/outputs/plots/html/{event_id}/plot_station_map.html",
        "filter_effect": f"/outputs/plots/html/{event_id}/plot_filter_effect.html",
        "vlf_spectrogram": f"/outputs/plots/html/{event_id}/plot_vlf_spectrogram.html",
    }
    return templates.TemplateResponse(
        "ui_event.html",
        {
            "request": request,
            "event_id": event_id,
            "plots": plots,
            "linked_summary": linked_summary,
            "event_meta": event_meta,
            "features_preview": features_preview,
            "features_total": features_total,
            "anomalies_preview": anomalies_preview,
            "anomalies_total": anomalies_total,
        },
    )
