from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from obspy import read

import pandas as pd

from src.dq.reporting import basic_stats, write_dq_report
from src.store.parquet import read_parquet, write_parquet_partitioned
from src.utils import ensure_dir, write_json


def _resolve_seismic_raw_config(config: Dict[str, Any]) -> Tuple[int, str]:
    cfg = config.get("seismic", {}) or {}
    interval_sec = int(cfg.get("raw_interval_sec", 1))
    interval_sec = max(interval_sec, 1)
    value_mode = str(cfg.get("raw_value_mode", "rms")).lower()
    return interval_sec, value_mode


def _aggregate_trace_window(data: np.ndarray, mode: str) -> float:
    if mode == "mean_abs":
        return float(np.mean(np.abs(data)))
    if mode == "max_abs":
        return float(np.max(np.abs(data)))
    return float(np.sqrt(np.mean(data * data)))


def run_raw(
    base_dir: Path,
    config: Dict[str, Any],
    output_paths,
    run_id: str,
    params_hash: str,
    strict: bool,
    event_id: str | None,
) -> None:
    pipeline_version = config.get("pipeline", {}).get("version", "0.0.0")
    limits = config.get("limits", {}) or {}
    max_rows = limits.get("max_rows_per_source")
    stats = {}

    # Geomag
    geomag_ingest = output_paths.ingest / "geomag"
    if geomag_ingest.exists():
        geomag_df = read_parquet(geomag_ingest)
        geomag_df["proc_stage"] = "raw"
        geomag_df["proc_version"] = pipeline_version
        geomag_df["params_hash"] = params_hash
        geomag_dir = output_paths.raw / "source=geomag"
        if geomag_dir.exists():
            shutil.rmtree(geomag_dir)
        write_parquet_partitioned(geomag_df, geomag_dir, config)
        stats["geomag"] = basic_stats(geomag_df)

    # AEF
    aef_ingest = output_paths.ingest / "aef"
    if aef_ingest.exists():
        aef_df = read_parquet(aef_ingest)
        aef_df["proc_stage"] = "raw"
        aef_df["proc_version"] = pipeline_version
        aef_df["params_hash"] = params_hash
        aef_dir = output_paths.raw / "source=aef"
        if aef_dir.exists():
            shutil.rmtree(aef_dir)
        write_parquet_partitioned(aef_df, aef_dir, config)
        stats["aef"] = basic_stats(aef_df)

    # Seismic trace index + raw files
    seismic_ingest = output_paths.ingest / "seismic"
    seismic_files = output_paths.ingest / "seismic_files"
    if seismic_ingest.exists() and seismic_files.exists():
        trace_df = read_parquet(seismic_ingest)
        if not trace_df.empty and "source" not in trace_df.columns:
            trace_df["source"] = "seismic"
        meta = (
            trace_df[["station_id", "lat", "lon", "elev"]]
            .drop_duplicates(subset=["station_id"])
            .set_index("station_id")
            if not trace_df.empty
            else pd.DataFrame()
        )

        seismic_cfg = config.get("paths", {}).get("seismic", {})
        mseed_patterns = list(seismic_cfg.get("mseed_patterns", ["*.seed", "*.mseed"]))
        interval_sec, value_mode = _resolve_seismic_raw_config(config)

        seismic_dir = output_paths.raw / "source=seismic"
        if seismic_dir.exists():
            shutil.rmtree(seismic_dir)
        ensure_dir(seismic_dir)

        part_counters = {}
        station_ids = set()
        rows_written = 0
        ts_min = None
        ts_max = None
        seen_files = set()

        for pattern in mseed_patterns:
            for path in seismic_files.glob(pattern):
                if path in seen_files:
                    continue
                seen_files.add(path)
                stream = read(str(path))
                for trace in stream:
                    data = trace.data.astype(float)
                    sr = float(trace.stats.sampling_rate)
                    window = int(sr * interval_sec)
                    if window <= 0 or len(data) < window:
                        continue
                    station_id = (
                        f"{trace.stats.network}.{trace.stats.station}.{trace.stats.location or ''}."
                        f"{trace.stats.channel}"
                    )
                    station_ids.add(station_id)
                    lat = meta.at[station_id, "lat"] if station_id in meta.index else np.nan
                    lon = meta.at[station_id, "lon"] if station_id in meta.index else np.nan
                    elev = meta.at[station_id, "elev"] if station_id in meta.index else np.nan
                    start_ms = int(
                        pd.Timestamp(trace.stats.starttime.datetime, tz="UTC").value // 1_000_000
                    )

                    records: List[Dict[str, Any]] = []
                    for offset in range(0, len(data) - window + 1, window):
                        ts_ms = start_ms + int((offset / sr) * 1000)
                        value = _aggregate_trace_window(data[offset : offset + window], value_mode)
                        records.append(
                            {
                                "ts_ms": ts_ms,
                                "source": "seismic",
                                "station_id": station_id,
                                "channel": f"{trace.stats.channel}_{value_mode}",
                                "value": value,
                                "lat": lat,
                                "lon": lon,
                                "elev": elev,
                                "quality_flags": {},
                                "proc_stage": "raw",
                                "proc_version": pipeline_version,
                                "params_hash": params_hash,
                            }
                        )
                        rows_written += 1
                        ts_min = ts_ms if ts_min is None else min(ts_min, ts_ms)
                        ts_max = ts_ms if ts_max is None else max(ts_max, ts_ms)
                        if max_rows is not None and rows_written >= max_rows:
                            break
                    if records:
                        df_records = pd.DataFrame.from_records(records)
                        part_counters = write_parquet_partitioned(
                            df_records,
                            seismic_dir,
                            config,
                            part_counters=part_counters,
                        )
                    if max_rows is not None and rows_written >= max_rows:
                        break
                if max_rows is not None and rows_written >= max_rows:
                    break
            if max_rows is not None and rows_written >= max_rows:
                break

        stats["seismic"] = {
            "rows": int(rows_written),
            "station_count": int(len(station_ids)),
            "ts_min": ts_min,
            "ts_max": ts_max,
        }

    # VLF data already stored by ingest; ensure catalog available
    vlf_catalog = output_paths.raw / "vlf_catalog.parquet"
    if vlf_catalog.exists():
        vlf_df = read_parquet(vlf_catalog)
        stats["vlf"] = {
            "files": int(len(vlf_df)),
            "stations": int(vlf_df["station_id"].nunique()),
        }

    write_dq_report(output_paths.reports / "dq_raw.json", {"sources": stats})

    # Compression stats (simple size ratio)
    compression = {}
    for source, report in stats.items():
        source_path = output_paths.raw / f"source={source}"
        if source_path.exists():
            total_bytes = sum(p.stat().st_size for p in source_path.rglob("*") if p.is_file())
            compression[source] = {"bytes": total_bytes}
    write_json(output_paths.reports / "compression.json", compression)
    write_json(output_paths.reports / "compression_stats.json", compression)
