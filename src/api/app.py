import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow.dataset as ds
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.store.parquet import read_parquet_filtered

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


def _resolve_source_path(stage: str, source: str) -> Path:
    source_dir = OUTPUT_ROOT / stage / f"source={source}"
    if source_dir.exists():
        return source_dir
    return OUTPUT_ROOT / stage / source


def _build_partition_filter(
    source_path: Path,
    start_ms: Optional[int],
    end_ms: Optional[int],
    station_id: Optional[str],
) -> Optional[ds.Expression]:
    if not source_path.exists():
        return None
    dataset = ds.dataset(source_path, format="parquet", partitioning="hive")
    fields = set(dataset.schema.names)
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
    source_path = _resolve_source_path("raw", source)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Raw source not found: {source}")
    start_ms = _parse_time(start)
    end_ms = _parse_time(end)
    filters = _build_partition_filter(source_path, start_ms, end_ms, station_id)
    df = read_parquet_filtered(source_path, filters=filters)
    summary = _summarize_df(
        read_parquet_filtered(source_path, filters=filters, columns=["ts_ms", "starttime", "endtime"])
    )
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
    source_path = _resolve_source_path("standard", source)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Standard source not found: {source}")
    start_ms = _parse_time(start)
    end_ms = _parse_time(end)
    filters = _build_partition_filter(source_path, start_ms, end_ms, station_id)
    df = read_parquet_filtered(source_path, filters=filters)
    summary = _summarize_df(
        read_parquet_filtered(source_path, filters=filters, columns=["ts_ms", "starttime", "endtime"])
    )
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
    source_path = _resolve_source_path("raw", source)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Raw source not found: {source}")
    df = read_parquet_filtered(source_path, columns=["ts_ms", "starttime", "endtime"])
    summary = _summarize_df(df)
    summary["source"] = source
    summary["stage"] = "raw"
    return summary


@app.get("/standard/summary")
def standard_summary(source: str = Query(..., description="geomag|aef|seismic|vlf")):
    source_path = _resolve_source_path("standard", source)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail=f"Standard source not found: {source}")
    df = read_parquet_filtered(source_path, columns=["ts_ms", "starttime", "endtime"])
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


@app.get("/events/{event_id}/export")
def export_event(
    event_id: str,
    format: str = Query("csv", description="csv|hdf5"),
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    path = OUTPUT_ROOT / "linked" / event_id / "aligned.parquet"
    if not path.exists():
        raise HTTPException(status_code=404, detail="aligned.parquet not found")
    df = pd.read_parquet(path)
    records = _query_df(df, start, end, None, None, None, None, None, 0)
    export_dir = OUTPUT_ROOT / "events" / event_id / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    if format == "hdf5":
        export_path = export_dir / "export.h5"
        pd.DataFrame(records).to_hdf(export_path, key="data", mode="w")
    else:
        export_path = export_dir / "export.csv"
        pd.DataFrame(records).to_csv(export_path, index=False)
    return FileResponse(export_path)


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
