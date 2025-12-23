from __future__ import annotations

import gc
import json
import math
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from obspy import read
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import zarr

from src.dq.reporting import basic_stats, write_dq_report
from src.store.parquet import read_parquet, write_parquet_configured
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


def _serialize_flags(series: pd.Series) -> pd.Series:
    return series.apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, dict) else x)


def _resolve_preprocess_batch_rows(config: Dict[str, Any]) -> int:
    value = config.get("preprocess", {}).get("batch_rows")
    if value is None:
        return 50_000
    value = int(value)
    return value if value > 0 else 50_000


def _resolve_overlap(config: Dict[str, Any]) -> int:
    interp_cfg = config.get("preprocess", {}).get("interpolate", {})
    filter_cfg = config.get("preprocess", {}).get("filter", {})
    interp_limit = int(interp_cfg.get("max_gap_minutes", 10))
    filter_window = int(filter_cfg.get("window", 5)) if filter_cfg.get("enabled", False) else 0
    return max(interp_limit, filter_window)


def _clean_timeseries_group(
    df: pd.DataFrame, config: Dict[str, Any], mean: float | None, std: float | None
) -> Tuple[pd.DataFrame, np.ndarray]:
    if df.empty:
        return df, np.array([])

    df = df.copy()
    df["quality_flags"] = _parse_flags(df["quality_flags"])
    outlier_cfg = config.get("preprocess", {}).get("outlier", {})
    threshold = float(outlier_cfg.get("threshold", 4.0))

    values = df["value"].astype(float)
    mean = float(mean) if mean is not None else float(values.mean())
    std = float(std) if std is not None else float(values.std() or 1.0)
    std = std if std != 0 else 1.0
    z = (values - mean) / std
    outlier_mask = z.abs() > threshold
    for idx in df.index[outlier_mask]:
        flags = df.at[idx, "quality_flags"]
        flags["is_outlier"] = True
        flags["outlier_method"] = "zscore"
        flags["threshold"] = threshold
        df.at[idx, "quality_flags"] = flags
    df.loc[outlier_mask, "value"] = np.nan

    interp_cfg = config.get("preprocess", {}).get("interpolate", {})
    df["value"] = df["value"].interpolate(
        limit=int(interp_cfg.get("max_gap_minutes", 10)),
        limit_direction="both",
    )
    for idx, val in df["value"].items():
        flags = df.at[idx, "quality_flags"]
        if math.isnan(val):
            flags["is_missing"] = True
            flags["missing_reason"] = flags.get("missing_reason") or "gap"
        else:
            if flags.get("is_missing"):
                flags["is_interpolated"] = True
                flags["interp_method"] = interp_cfg.get("method", "linear")
        df.at[idx, "quality_flags"] = flags

    before_values = df["value"].astype(float).to_numpy(copy=True)

    filter_cfg = config.get("preprocess", {}).get("filter", {})
    if filter_cfg.get("enabled", False):
        window = int(filter_cfg.get("window", 5))
        df["value"] = df["value"].rolling(window=window, min_periods=1).mean()
        for idx in df.index:
            flags = df.at[idx, "quality_flags"]
            flags["is_filtered"] = True
            flags["filter_type"] = filter_cfg.get("method", "rolling_mean")
            flags["filter_params"] = {"window": window}
            df.at[idx, "quality_flags"] = flags

    return df, before_values


def _update_sum_stats(
    stats: Dict[str, float], values: np.ndarray
) -> None:
    if values.size == 0:
        return
    stats["count"] += int(values.size)
    stats["sum"] += float(values.sum())
    stats["sum_sq"] += float((values * values).sum())


def _stats_from_sum(stats: Dict[str, float]) -> float | None:
    if stats["count"] <= 0:
        return None
    mean = stats["sum"] / stats["count"]
    var = stats["sum_sq"] / stats["count"] - mean * mean
    if var < 0:
        var = 0.0
    return float(math.sqrt(var)) if stats["count"] > 1 else 0.0


def _compute_group_stats(
    dataset: ds.Dataset,
    batch_rows: int,
    max_rows: int | None,
) -> Tuple[Dict[Tuple[str, str], Dict[str, float]], Dict[str, float]]:
    stats: Dict[Tuple[str, str], Dict[str, float]] = {}
    total = {"count": 0, "sum": 0.0, "sum_sq": 0.0}
    seen = 0
    scanner = dataset.scanner(columns=["station_id", "channel", "value"], batch_size=batch_rows)
    for batch in scanner.to_batches():
        df = batch.to_pandas()
        if df.empty:
            continue
        if max_rows is not None and seen >= max_rows:
            break
        if max_rows is not None and seen + len(df) > max_rows:
            df = df.iloc[: max_rows - seen]
        seen += len(df)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        grouped = df.groupby(["station_id", "channel"])["value"]
        for key, series in grouped:
            values = series.to_numpy(dtype=float, copy=False)
            values = values[~np.isnan(values)]
            if values.size == 0:
                continue
            entry = stats.get(key)
            if entry is None:
                entry = {"count": 0, "sum": 0.0, "sum_sq": 0.0}
                stats[key] = entry
            _update_sum_stats(entry, values)
            _update_sum_stats(total, values)
    return stats, total


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


def _write_parquet_batch(
    writer: pq.ParquetWriter | None,
    df: pd.DataFrame,
    file_path: Path,
    compression: str,
) -> pq.ParquetWriter:
    df = df.copy()
    if "quality_flags" in df.columns:
        df["quality_flags"] = _serialize_flags(df["quality_flags"])
    table = pa.Table.from_pandas(df)
    if writer is None:
        writer = pq.ParquetWriter(file_path, table.schema, compression=compression)
    writer.write_table(table)
    return writer


def _process_standard_source(
    source: str,
    raw_path: Path,
    output_paths,
    config: Dict[str, Any],
    params_hash: str,
    max_rows: int | None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    dataset = ds.dataset(raw_path, format="parquet", partitioning="hive")
    batch_rows = _resolve_preprocess_batch_rows(config)
    overlap = _resolve_overlap(config)
    if overlap >= batch_rows:
        batch_rows = max(overlap + 1, batch_rows)

    group_stats, _ = _compute_group_stats(dataset, batch_rows, max_rows)
    if not group_stats:
        return {}, {}

    mean_std = {
        key: (
            stats["sum"] / stats["count"],
            _stats_from_sum(stats) or 1.0,
        )
        for key, stats in group_stats.items()
        if stats["count"] > 0
    }

    output_base = output_paths.standard / source
    if output_base.exists():
        shutil.rmtree(output_base)
    partition_dir = output_base / f"source={source}"
    ensure_dir(partition_dir)
    file_path = partition_dir / "data.parquet"

    parquet_cfg = (config.get("storage") or {}).get("parquet") or {}
    compression = parquet_cfg.get("compression", "zstd")

    report = {
        "rows": 0,
        "ts_min": None,
        "ts_max": None,
        "missing_rate": None,
        "outlier_rate": None,
        "station_count": 0,
    }
    station_ids = set()
    missing_count = 0
    outlier_count = 0
    before_stats = {"count": 0, "sum": 0.0, "sum_sq": 0.0}
    after_stats = {"count": 0, "sum": 0.0, "sum_sq": 0.0}

    tails: Dict[Tuple[str, str], pd.DataFrame] = {}
    writer: pq.ParquetWriter | None = None
    seen = 0
    scanner = dataset.scanner(
        columns=[
            "ts_ms",
            "source",
            "station_id",
            "channel",
            "value",
            "lat",
            "lon",
            "elev",
            "quality_flags",
            "proc_stage",
            "proc_version",
            "params_hash",
        ],
        batch_size=batch_rows,
    )

    try:
        for batch in scanner.to_batches():
            df = batch.to_pandas()
            if df.empty:
                continue
            if max_rows is not None and seen >= max_rows:
                break
            if max_rows is not None and seen + len(df) > max_rows:
                df = df.iloc[: max_rows - seen]
            seen += len(df)
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            grouped = df.groupby(["station_id", "channel"], sort=False)
            for key, group in grouped:
                tail_raw = tails.get(key)
                if tail_raw is not None and not tail_raw.empty:
                    combined_raw = pd.concat([tail_raw, group], ignore_index=True)
                else:
                    combined_raw = group
                combined_raw = combined_raw.sort_values("ts_ms")
                mean, std = mean_std.get(key, (None, None))
                cleaned, before_values = _clean_timeseries_group(combined_raw, config, mean, std)
                if overlap > 0 and len(cleaned) > overlap:
                    to_write = cleaned.iloc[:-overlap]
                    before_values = before_values[:-overlap]
                    tails[key] = combined_raw.iloc[-overlap:].copy()
                else:
                    to_write = cleaned
                    tails[key] = combined_raw.iloc[0:0].copy()

                if to_write.empty:
                    continue
                to_write["proc_stage"] = "standard"
                to_write["proc_version"] = config.get("pipeline", {}).get("version", "0.0.0")
                to_write["params_hash"] = params_hash

                ts_min = int(to_write["ts_ms"].min())
                ts_max = int(to_write["ts_ms"].max())
                report["ts_min"] = ts_min if report["ts_min"] is None else min(report["ts_min"], ts_min)
                report["ts_max"] = ts_max if report["ts_max"] is None else max(report["ts_max"], ts_max)
                report["rows"] += int(len(to_write))
                station_ids.add(key[0])

                missing_count += int(to_write["value"].isna().sum())
                outlier_count += sum(
                    1
                    for flags in to_write["quality_flags"].tolist()
                    if isinstance(flags, dict) and flags.get("is_outlier")
                )

                before_vals = before_values[~np.isnan(before_values)]
                _update_sum_stats(before_stats, before_vals)
                after_vals = to_write["value"].to_numpy(dtype=float, copy=False)
                after_vals = after_vals[~np.isnan(after_vals)]
                _update_sum_stats(after_stats, after_vals)

                writer = _write_parquet_batch(writer, to_write, file_path, compression)
            gc.collect()

        for key, tail_raw in tails.items():
            if tail_raw.empty:
                continue
            mean, std = mean_std.get(key, (None, None))
            cleaned, before_values = _clean_timeseries_group(tail_raw, config, mean, std)
            if cleaned.empty:
                continue
            cleaned["proc_stage"] = "standard"
            cleaned["proc_version"] = config.get("pipeline", {}).get("version", "0.0.0")
            cleaned["params_hash"] = params_hash
            ts_min = int(cleaned["ts_ms"].min())
            ts_max = int(cleaned["ts_ms"].max())
            report["ts_min"] = ts_min if report["ts_min"] is None else min(report["ts_min"], ts_min)
            report["ts_max"] = ts_max if report["ts_max"] is None else max(report["ts_max"], ts_max)
            report["rows"] += int(len(cleaned))
            station_ids.add(key[0])
            missing_count += int(cleaned["value"].isna().sum())
            outlier_count += sum(
                1
                for flags in cleaned["quality_flags"].tolist()
                if isinstance(flags, dict) and flags.get("is_outlier")
            )
            before_vals = before_values[~np.isnan(before_values)]
            _update_sum_stats(before_stats, before_vals)
            after_vals = cleaned["value"].to_numpy(dtype=float, copy=False)
            after_vals = after_vals[~np.isnan(after_vals)]
            _update_sum_stats(after_stats, after_vals)
            writer = _write_parquet_batch(writer, cleaned, file_path, compression)
    finally:
        if writer is not None:
            writer.close()

    report["station_count"] = int(len(station_ids))
    report["missing_rate"] = float(missing_count / report["rows"]) if report["rows"] else None
    report["outlier_rate"] = float(outlier_count / report["rows"]) if report["rows"] else None
    filter_effect = {"before_std": _stats_from_sum(before_stats), "after_std": _stats_from_sum(after_stats)}
    return report, filter_effect


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
        report, filter_effect = _process_standard_source(
            "geomag", geomag_raw, output_paths, config, params_hash, max_rows
        )
        if report:
            reports["geomag"] = report
            filter_reports["geomag"] = filter_effect

    aef_raw = output_paths.raw / "aef"
    if aef_raw.exists():
        report, filter_effect = _process_standard_source(
            "aef", aef_raw, output_paths, config, params_hash, max_rows
        )
        if report:
            reports["aef"] = report
            filter_reports["aef"] = filter_effect

    seismic_df = _seismic_features(base_dir, config, output_paths.raw, max_rows, params_hash)
    if not seismic_df.empty:
        write_parquet_configured(seismic_df, output_paths.standard / "seismic", config, partition_cols=["source"])
        reports["seismic"] = basic_stats(seismic_df)

    vlf_df = _vlf_features(config, output_paths.raw, max_rows, params_hash)
    if not vlf_df.empty:
        write_parquet_configured(vlf_df, output_paths.standard / "vlf", config, partition_cols=["source"])
        reports["vlf"] = basic_stats(vlf_df)

    write_dq_report(output_paths.reports / "dq_standard.json", {"sources": reports})
    write_json(output_paths.reports / "filter_effect.json", filter_reports)
