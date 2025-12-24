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
import pyarrow.dataset as ds
import zarr

from src.dq.reporting import basic_stats, write_dq_report
from src.store.parquet import read_parquet, write_parquet_partitioned
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


def _resolve_minute_expansion(config: Dict[str, Any], source: str) -> Dict[str, Any] | None:
    expand_cfg = config.get("preprocess", {}).get("expand_minute_to_seconds", {})
    source_cfg = expand_cfg.get(source)
    if not source_cfg:
        return None
    if not source_cfg.get("enabled", False):
        return None
    seconds = int(source_cfg.get("seconds", 60))
    seconds = max(seconds, 1)
    mode = str(source_cfg.get("mode", "centered")).lower()
    chunk_rows = int(source_cfg.get("chunk_rows", 2000))
    chunk_rows = max(chunk_rows, 1)
    return {"seconds": seconds, "mode": mode, "chunk_rows": chunk_rows}


def _iter_expand_minute_to_seconds(
    df: pd.DataFrame, seconds: int, mode: str, chunk_rows: int
):
    if df.empty:
        return

    if mode == "centered":
        half = seconds // 2
        offsets = np.arange(-half, seconds - half)
    else:
        offsets = np.arange(0, seconds)
    offsets_ms = offsets.astype("int64") * 1000

    for start in range(0, len(df), chunk_rows):
        chunk = df.iloc[start : start + chunk_rows].copy()
        repeated = chunk.loc[chunk.index.repeat(len(offsets))].copy()
        repeated["ts_ms"] = np.repeat(chunk["ts_ms"].to_numpy(), len(offsets)) + np.tile(
            offsets_ms, len(chunk)
        )
        flags = repeated["quality_flags"].tolist()
        updated_flags = []
        for flag in flags:
            if isinstance(flag, dict):
                flag = dict(flag)
            else:
                flag = {}
            flag["is_interpolated"] = True
            flag["interp_method"] = "minute_expand"
            flag["note"] = flag.get("note") or "expanded_from_minute"
            updated_flags.append(flag)
        repeated["quality_flags"] = updated_flags
        yield repeated


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
    config: Dict[str, Any],
    output_paths,
    max_rows: int | None,
    params_hash: str,
) -> pd.DataFrame:
    interval_sec = int(config.get("seismic", {}).get("feature_interval_sec", 60))
    interval_sec = max(interval_sec, 1)
    records: List[Dict[str, Any]] = []
    trace_index = None
    trace_index_path = output_paths.ingest / "seismic"
    if trace_index_path.exists():
        trace_index = read_parquet(trace_index_path)

    file_dir = output_paths.ingest / "seismic_files"
    if not file_dir.exists():
        return pd.DataFrame()
    seismic_cfg = config.get("paths", {}).get("seismic", {})
    mseed_patterns = list(seismic_cfg.get("mseed_patterns", ["*.seed", "*.mseed"]))
    seen_files = set()
    for pattern in mseed_patterns:
        for mseed_file in file_dir.glob(pattern):
            if mseed_file in seen_files:
                continue
            seen_files.add(mseed_file)
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
                    ts = pd.Timestamp(start_time, tz="UTC") + pd.Timedelta(seconds=idx / sr)
                    station_id = (
                        f"{trace.stats.network}.{trace.stats.station}.{trace.stats.location or ''}."
                        f"{trace.stats.channel}"
                    )
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
    expand_cfg = _resolve_minute_expansion(config, source)
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

    output_base = output_paths.standard / f"source={source}"
    if output_base.exists():
        shutil.rmtree(output_base)
    ensure_dir(output_base)

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
    part_counters: Dict[Path, int] = {}
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
                    to_write = cleaned.iloc[:-overlap].copy()
                    before_values = before_values[:-overlap]
                    tails[key] = combined_raw.iloc[-overlap:].copy()
                else:
                    to_write = cleaned.copy()
                    tails[key] = combined_raw.iloc[0:0].copy()

                if to_write.empty:
                    continue
                to_write["proc_stage"] = "standard"
                to_write["proc_version"] = config.get("pipeline", {}).get("version", "0.0.0")
                to_write["params_hash"] = params_hash

                if expand_cfg:
                    for expanded in _iter_expand_minute_to_seconds(
                        to_write,
                        expand_cfg["seconds"],
                        expand_cfg["mode"],
                        expand_cfg["chunk_rows"],
                    ):
                        if expanded.empty:
                            continue
                        part_counters = write_parquet_partitioned(
                            expanded,
                            output_base,
                            config,
                            part_counters=part_counters,
                        )
                        ts_min = int(expanded["ts_ms"].min())
                        ts_max = int(expanded["ts_ms"].max())
                        report["ts_min"] = (
                            ts_min if report["ts_min"] is None else min(report["ts_min"], ts_min)
                        )
                        report["ts_max"] = (
                            ts_max if report["ts_max"] is None else max(report["ts_max"], ts_max)
                        )
                    report["rows"] += int(len(to_write) * expand_cfg["seconds"])
                else:
                    ts_min = int(to_write["ts_ms"].min())
                    ts_max = int(to_write["ts_ms"].max())
                    report["ts_min"] = ts_min if report["ts_min"] is None else min(report["ts_min"], ts_min)
                    report["ts_max"] = ts_max if report["ts_max"] is None else max(report["ts_max"], ts_max)
                    report["rows"] += int(len(to_write))
                station_ids.add(key[0])

                missing_scale = expand_cfg["seconds"] if expand_cfg else 1
                missing_count += int(to_write["value"].isna().sum()) * missing_scale
                outlier_count += sum(
                    1
                    for flags in to_write["quality_flags"].tolist()
                    if isinstance(flags, dict) and flags.get("is_outlier")
                ) * missing_scale

                before_vals = before_values[~np.isnan(before_values)]
                _update_sum_stats(before_stats, before_vals)
                after_vals = to_write["value"].to_numpy(dtype=float, copy=False)
                after_vals = after_vals[~np.isnan(after_vals)]
                _update_sum_stats(after_stats, after_vals)

                if not expand_cfg:
                    part_counters = write_parquet_partitioned(
                        to_write,
                        output_base,
                        config,
                        part_counters=part_counters,
                    )
            gc.collect()

        for key, tail_raw in tails.items():
            if tail_raw.empty:
                continue
            mean, std = mean_std.get(key, (None, None))
            cleaned, before_values = _clean_timeseries_group(tail_raw, config, mean, std)
            if cleaned.empty:
                continue
            cleaned = cleaned.copy()
            cleaned["proc_stage"] = "standard"
            cleaned["proc_version"] = config.get("pipeline", {}).get("version", "0.0.0")
            cleaned["params_hash"] = params_hash
            if expand_cfg:
                for expanded in _iter_expand_minute_to_seconds(
                    cleaned,
                    expand_cfg["seconds"],
                    expand_cfg["mode"],
                    expand_cfg["chunk_rows"],
                ):
                    if expanded.empty:
                        continue
                    part_counters = write_parquet_partitioned(
                        expanded,
                        output_base,
                        config,
                        part_counters=part_counters,
                    )
                    ts_min = int(expanded["ts_ms"].min())
                    ts_max = int(expanded["ts_ms"].max())
                    report["ts_min"] = (
                        ts_min if report["ts_min"] is None else min(report["ts_min"], ts_min)
                    )
                    report["ts_max"] = (
                        ts_max if report["ts_max"] is None else max(report["ts_max"], ts_max)
                    )
                report["rows"] += int(len(cleaned) * expand_cfg["seconds"])
            else:
                ts_min = int(cleaned["ts_ms"].min())
                ts_max = int(cleaned["ts_ms"].max())
                report["ts_min"] = ts_min if report["ts_min"] is None else min(report["ts_min"], ts_min)
                report["ts_max"] = ts_max if report["ts_max"] is None else max(report["ts_max"], ts_max)
                report["rows"] += int(len(cleaned))
            station_ids.add(key[0])
            missing_scale = expand_cfg["seconds"] if expand_cfg else 1
            missing_count += int(cleaned["value"].isna().sum()) * missing_scale
            outlier_count += sum(
                1
                for flags in cleaned["quality_flags"].tolist()
                if isinstance(flags, dict) and flags.get("is_outlier")
            ) * missing_scale
            before_vals = before_values[~np.isnan(before_values)]
            _update_sum_stats(before_stats, before_vals)
            after_vals = cleaned["value"].to_numpy(dtype=float, copy=False)
            after_vals = after_vals[~np.isnan(after_vals)]
            _update_sum_stats(after_stats, after_vals)
            if not expand_cfg:
                part_counters = write_parquet_partitioned(
                    cleaned,
                    output_base,
                    config,
                    part_counters=part_counters,
                )
    finally:
        pass

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

    geomag_raw = output_paths.raw / "source=geomag"
    if geomag_raw.exists():
        report, filter_effect = _process_standard_source(
            "geomag", geomag_raw, output_paths, config, params_hash, max_rows
        )
        if report:
            reports["geomag"] = report
            filter_reports["geomag"] = filter_effect

    aef_raw = output_paths.raw / "source=aef"
    if aef_raw.exists():
        report, filter_effect = _process_standard_source(
            "aef", aef_raw, output_paths, config, params_hash, max_rows
        )
        if report:
            reports["aef"] = report
            filter_reports["aef"] = filter_effect

    seismic_df = _seismic_features(config, output_paths, max_rows, params_hash)
    if not seismic_df.empty:
        seismic_dir = output_paths.standard / "source=seismic"
        if seismic_dir.exists():
            shutil.rmtree(seismic_dir)
        write_parquet_partitioned(seismic_df, seismic_dir, config)
        reports["seismic"] = basic_stats(seismic_df)

    vlf_df = _vlf_features(config, output_paths.raw, max_rows, params_hash)
    if not vlf_df.empty:
        vlf_dir = output_paths.standard / "source=vlf"
        if vlf_dir.exists():
            shutil.rmtree(vlf_dir)
        write_parquet_partitioned(vlf_df, vlf_dir, config)
        reports["vlf"] = basic_stats(vlf_df)

    write_dq_report(output_paths.reports / "dq_standard.json", {"sources": reports})
    write_json(output_paths.reports / "filter_effect.json", filter_reports)
