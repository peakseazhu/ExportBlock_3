from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from obspy import read

from src.dq.reporting import basic_stats, write_dq_report
from src.store.parquet import read_parquet, write_parquet
from src.utils import ensure_dir, write_json


def _parse_flags(series: pd.Series) -> List[Dict[str, Any]]:
    parsed = []
    for item in series.tolist():
        if isinstance(item, dict):
            parsed.append(item)
        elif isinstance(item, str):
            try:
                parsed.append(json.loads(item))
            except Exception:
                parsed.append({})
        else:
            parsed.append({})
    return parsed


def _clean_timeseries(df: pd.DataFrame, config: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if df.empty:
        return df, {}

    df = df.copy()
    df["quality_flags"] = _parse_flags(df["quality_flags"])
    outlier_cfg = config.get("preprocess", {}).get("outlier", {})
    threshold = float(outlier_cfg.get("threshold", 4.0))

    def apply_group(group: pd.DataFrame) -> pd.DataFrame:
        values = group["value"].astype(float)
        mean = values.mean()
        std = values.std() if values.std() != 0 else 1.0
        z = (values - mean) / std
        outlier_mask = z.abs() > threshold
        for idx in group.index[outlier_mask]:
            flags = group.at[idx, "quality_flags"]
            flags["is_outlier"] = True
            flags["outlier_method"] = "zscore"
            flags["threshold"] = threshold
            group.at[idx, "quality_flags"] = flags
        group.loc[outlier_mask, "value"] = np.nan

        group["value"] = group["value"].interpolate(
            limit=int(config.get("preprocess", {}).get("interpolate", {}).get("max_gap_minutes", 10)),
            limit_direction="both",
        )
        for idx, val in group["value"].items():
            flags = group.at[idx, "quality_flags"]
            if math.isnan(val):
                flags["is_missing"] = True
                flags["missing_reason"] = flags.get("missing_reason") or "gap"
            else:
                if flags.get("is_missing"):
                    flags["is_interpolated"] = True
                    flags["interp_method"] = config.get("preprocess", {}).get("interpolate", {}).get(
                        "method", "linear"
                    )
            group.at[idx, "quality_flags"] = flags
        return group

    df = df.groupby(["station_id", "channel"], group_keys=False).apply(apply_group)

    filter_cfg = config.get("preprocess", {}).get("filter", {})
    filter_enabled = filter_cfg.get("enabled", False)
    before_std = float(df["value"].std()) if not df["value"].isna().all() else None
    if filter_enabled:
        window = int(filter_cfg.get("window", 5))
        df["value"] = df["value"].rolling(window=window, min_periods=1).mean()
        for idx in df.index:
            flags = df.at[idx, "quality_flags"]
            flags["is_filtered"] = True
            flags["filter_type"] = filter_cfg.get("method", "rolling_mean")
            flags["filter_params"] = {"window": window}
            df.at[idx, "quality_flags"] = flags
    after_std = float(df["value"].std()) if not df["value"].isna().all() else None
    filter_effect = {"before_std": before_std, "after_std": after_std}
    return df, filter_effect


def _seismic_features(
    base_dir: Path,
    config: Dict[str, Any],
    raw_dir: Path,
    max_rows: int | None,
    params_hash: str,
) -> pd.DataFrame:
    interval_sec = 60
    records: List[Dict[str, Any]] = []
    trace_index = None
    trace_index_path = raw_dir / "seismic"
    if trace_index_path.exists():
        trace_index = read_parquet(trace_index_path)

    file_dir = raw_dir / "seismic_files"
    for mseed_file in file_dir.glob("*.mseed"):
        stream = read(str(mseed_file))
        for trace in stream:
            data = trace.data.astype(float)
            sr = float(trace.stats.sampling_rate)
            window = int(sr * interval_sec)
            start_time = trace.stats.starttime.datetime
            for idx in range(0, len(data), window):
                segment = data[idx : idx + window]
                if len(segment) < window:
                    break
                ts = pd.Timestamp(start_time) + pd.Timedelta(seconds=idx / sr)
                station_id = f"{trace.stats.network}.{trace.stats.station}.{trace.stats.location or ''}.{trace.stats.channel}"
                records.append(
                    {
                        "ts_ms": int(ts.value // 1_000_000),
                        "source": "seismic",
                        "station_id": station_id,
                        "channel": f"{trace.stats.channel}_rms",
                        "value": float(np.sqrt(np.mean(segment**2))),
                    }
                )
                records.append(
                    {
                        "ts_ms": int(ts.value // 1_000_000),
                        "source": "seismic",
                        "station_id": station_id,
                        "channel": f"{trace.stats.channel}_mean_abs",
                        "value": float(np.mean(np.abs(segment))),
                    }
                )
                if max_rows and len(records) >= max_rows:
                    break
            if max_rows and len(records) >= max_rows:
                break
        if max_rows and len(records) >= max_rows:
            break

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame.from_records(records)
    df["quality_flags"] = [{} for _ in range(len(df))]
    df["proc_stage"] = "standard"
    df["proc_version"] = config.get("pipeline", {}).get("version", "0.0.0")
    df["params_hash"] = params_hash

    if trace_index is not None and not trace_index.empty:
        meta = trace_index[["station_id", "lat", "lon", "elev"]].drop_duplicates()
        df = df.merge(meta, on="station_id", how="left")
    else:
        df["lat"] = np.nan
        df["lon"] = np.nan
        df["elev"] = np.nan
    return df


def _vlf_features(config: Dict[str, Any], raw_dir: Path, max_rows: int | None, params_hash: str) -> pd.DataFrame:
    band_edges = config.get("vlf", {}).get("band_edges_hz", [10, 1000, 3000, 10000])
    records: List[Dict[str, Any]] = []

    for station_dir in (raw_dir / "vlf").glob("*"):
        for run_dir in station_dir.glob("*"):
            zarr_path = run_dir / "spectrogram.zarr"
            if not zarr_path.exists():
                continue
            root = zarr.open(str(zarr_path), mode="r")
            epoch_ns = root["epoch_ns"][:]
            freq = root["freq_hz"][:]
            ch1 = root["ch1"][:]
            ch2 = root["ch2"][:]

            for i, ts_ns in enumerate(epoch_ns):
                ts_ms = int(ts_ns // 1_000_000)
                for band_start, band_end in zip(band_edges[:-1], band_edges[1:]):
                    mask = (freq >= band_start) & (freq < band_end)
                    band_power_ch1 = float(np.nanmean(ch1[i, mask]))
                    band_power_ch2 = float(np.nanmean(ch2[i, mask]))
                    records.append(
                        {
                            "ts_ms": ts_ms,
                            "source": "vlf",
                            "station_id": station_dir.name,
                            "channel": f"ch1_band_{band_start}_{band_end}",
                            "value": band_power_ch1,
                        }
                    )
                    records.append(
                        {
                            "ts_ms": ts_ms,
                            "source": "vlf",
                            "station_id": station_dir.name,
                            "channel": f"ch2_band_{band_start}_{band_end}",
                            "value": band_power_ch2,
                        }
                    )
                peak_freq_ch1 = float(freq[np.nanargmax(ch1[i])]) if np.any(~np.isnan(ch1[i])) else np.nan
                peak_freq_ch2 = float(freq[np.nanargmax(ch2[i])]) if np.any(~np.isnan(ch2[i])) else np.nan
                records.append(
                    {
                        "ts_ms": ts_ms,
                        "source": "vlf",
                        "station_id": station_dir.name,
                        "channel": "ch1_peak_freq",
                        "value": peak_freq_ch1,
                    }
                )
                records.append(
                    {
                        "ts_ms": ts_ms,
                        "source": "vlf",
                        "station_id": station_dir.name,
                        "channel": "ch2_peak_freq",
                        "value": peak_freq_ch2,
                    }
                )
                if max_rows and len(records) >= max_rows:
                    break
            if max_rows and len(records) >= max_rows:
                break
        if max_rows and len(records) >= max_rows:
            break

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame.from_records(records)
    df["quality_flags"] = [{} for _ in range(len(df))]
    df["proc_stage"] = "standard"
    df["proc_version"] = config.get("pipeline", {}).get("version", "0.0.0")
    df["params_hash"] = params_hash
    df["lat"] = np.nan
    df["lon"] = np.nan
    df["elev"] = np.nan
    return df


def run_standard(
    base_dir: Path,
    config: Dict[str, Any],
    output_paths,
    run_id: str,
    params_hash: str,
    strict: bool,
    event_id: str | None,
) -> None:
    limits = config.get("limits", {}) or {}
    max_rows = limits.get("max_rows_per_source")

    reports = {}
    filter_reports = {}

    geomag_raw = output_paths.raw / "geomag"
    if geomag_raw.exists():
        geomag_df = read_parquet(geomag_raw)
        cleaned, filter_effect = _clean_timeseries(geomag_df, config)
        cleaned["proc_stage"] = "standard"
        cleaned["proc_version"] = config.get("pipeline", {}).get("version", "0.0.0")
        cleaned["params_hash"] = params_hash
        write_parquet(cleaned, output_paths.standard / "geomag", partition_cols=["source"])
        reports["geomag"] = basic_stats(cleaned)
        filter_reports["geomag"] = filter_effect

    aef_raw = output_paths.raw / "aef"
    if aef_raw.exists():
        aef_df = read_parquet(aef_raw)
        cleaned, filter_effect = _clean_timeseries(aef_df, config)
        cleaned["proc_stage"] = "standard"
        cleaned["proc_version"] = config.get("pipeline", {}).get("version", "0.0.0")
        cleaned["params_hash"] = params_hash
        write_parquet(cleaned, output_paths.standard / "aef", partition_cols=["source"])
        reports["aef"] = basic_stats(cleaned)
        filter_reports["aef"] = filter_effect

    seismic_df = _seismic_features(base_dir, config, output_paths.raw, max_rows, params_hash)
    if not seismic_df.empty:
        write_parquet(seismic_df, output_paths.standard / "seismic", partition_cols=["source"])
        reports["seismic"] = basic_stats(seismic_df)

    vlf_df = _vlf_features(config, output_paths.raw, max_rows, params_hash)
    if not vlf_df.empty:
        write_parquet(vlf_df, output_paths.standard / "vlf", partition_cols=["source"])
        reports["vlf"] = basic_stats(vlf_df)

    write_dq_report(output_paths.reports / "dq_standard.json", {"sources": reports})
    write_json(output_paths.reports / "filter_effect.json", filter_reports)
