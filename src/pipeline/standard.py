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
import pywt
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


def _source_preprocess_cfg(config: Dict[str, Any], source: str) -> Dict[str, Any]:
    return config.get("preprocess", {}).get(source, {}) or {}


def _resolve_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _resolve_overlap(config: Dict[str, Any], source: str) -> int:
    source_cfg = _source_preprocess_cfg(config, source)
    interp_cfg = source_cfg.get("interpolate", config.get("preprocess", {}).get("interpolate", {}))
    lowpass_cfg = source_cfg.get("lowpass", config.get("preprocess", {}).get("filter", {}))
    highpass_cfg = source_cfg.get("highpass", {})
    despike_cfg = source_cfg.get("despike", {})
    interp_limit = _resolve_int(
        interp_cfg.get("max_gap_points", interp_cfg.get("max_gap_minutes")), 10
    )
    lowpass_window = _resolve_int(
        lowpass_cfg.get("window_points", lowpass_cfg.get("window")), 0
    )
    highpass_window = _resolve_int(highpass_cfg.get("window_points"), 0)
    despike_window = _resolve_int(despike_cfg.get("window_points"), 0)
    return max(interp_limit, lowpass_window, highpass_window, despike_window)


def _resolve_minute_expansion(config: Dict[str, Any], source: str) -> Dict[str, Any] | None:
    preprocess_cfg = config.get("preprocess", {}) or {}
    source_cfg = preprocess_cfg.get(source, {}).get("expand_minute_to_seconds")
    if not source_cfg:
        expand_cfg = preprocess_cfg.get("expand_minute_to_seconds", {})
        source_cfg = expand_cfg.get(source)
    if not source_cfg:
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


def _mad_outlier_mask(
    values: pd.Series, threshold: float, mean: float | None, std: float | None
) -> pd.Series:
    series = values.astype(float)
    median = float(series.median())
    mad = float(np.median(np.abs(series - median)))
    if mad > 0:
        z = 0.6745 * (series - median) / mad
        return z.abs() > threshold
    if std is None or std == 0 or math.isnan(std):
        return pd.Series([False] * len(series), index=series.index)
    mean = float(mean) if mean is not None else float(series.mean())
    z = (series - mean) / float(std)
    return z.abs() > threshold


def _hampel_mask(values: pd.Series, window: int, threshold: float) -> pd.Series:
    if window <= 1:
        return pd.Series([False] * len(values), index=values.index)
    series = values.astype(float)
    rolling_median = series.rolling(window, center=True, min_periods=1).median()
    deviation = (series - rolling_median).abs()
    rolling_mad = deviation.rolling(window, center=True, min_periods=1).median()
    scaled = 0.6745 * deviation / rolling_mad.replace(0, np.nan)
    return scaled > threshold


def _detrend_linear(values: pd.Series, ts_ms: pd.Series) -> pd.Series:
    mask = values.notna()
    if mask.sum() < 2:
        return values
    x = ts_ms[mask].to_numpy(dtype=float)
    x = x - x[0]
    y = values[mask].to_numpy(dtype=float)
    coeff = np.polyfit(x, y, 1)
    trend = coeff[0] * (ts_ms.to_numpy(dtype=float) - x[0]) + coeff[1]
    return values - trend


def _highpass_rolling(values: pd.Series, window: int, method: str) -> pd.Series:
    if window <= 1:
        return values
    series = values.astype(float)
    if method == "rolling_mean":
        baseline = series.rolling(window, center=True, min_periods=1).mean()
    else:
        baseline = series.rolling(window, center=True, min_periods=1).median()
    return series - baseline


def _wavelet_denoise(values: pd.Series, cfg: Dict[str, Any]) -> pd.Series:
    series = values.astype(float)
    if series.dropna().shape[0] < 8:
        return series
    wavelet = str(cfg.get("name", "db4"))
    mode = str(cfg.get("mode", "soft"))
    threshold_scale = float(cfg.get("threshold_scale", 1.0))
    max_level = int(
        cfg.get(
            "level",
            pywt.dwt_max_level(series.dropna().shape[0], pywt.Wavelet(wavelet).dec_len),
        )
    )
    max_level = max(max_level, 1)
    mask = series.isna()
    filled = series.copy()
    filled = filled.interpolate(limit_direction="both")
    filled = filled.fillna(method="bfill").fillna(method="ffill")
    coeffs = pywt.wavedec(filled.to_numpy(), wavelet, mode="periodization", level=max_level)
    detail = coeffs[-1]
    sigma = float(np.median(np.abs(detail)) / 0.6745) if detail.size else 0.0
    if sigma > 0:
        uthresh = threshold_scale * sigma * math.sqrt(2 * math.log(len(filled)))
        coeffs[1:] = [pywt.threshold(c, value=uthresh, mode=mode) for c in coeffs[1:]]
    reconstructed = pywt.waverec(coeffs, wavelet, mode="periodization")[: len(filled)]
    output = pd.Series(reconstructed, index=series.index)
    output[mask] = np.nan
    return output


def _apply_geomag_aef_preprocess(
    values: pd.Series, ts_ms: pd.Series, source_cfg: Dict[str, Any]
) -> tuple[pd.Series, Dict[str, Any]]:
    preprocess_meta: Dict[str, Any] = {}
    detrend_cfg = source_cfg.get("detrend", {})
    detrend_method = str(detrend_cfg.get("method", "linear")).lower()
    if detrend_method in {"linear", "constant"}:
        if detrend_method == "linear":
            values = _detrend_linear(values, ts_ms)
        else:
            values = values - values.mean()
        preprocess_meta["detrend"] = {"method": detrend_method}
    highpass_cfg = source_cfg.get("highpass", {})
    highpass_window = _resolve_int(highpass_cfg.get("window_points"), 0)
    if highpass_window > 1:
        values = _highpass_rolling(
            values, highpass_window, str(highpass_cfg.get("method", "rolling_median"))
        )
        preprocess_meta["highpass"] = {
            "window_points": highpass_window,
            "method": highpass_cfg.get("method", "rolling_median"),
        }
    wavelet_cfg = source_cfg.get("wavelet", {})
    if wavelet_cfg:
        values = _wavelet_denoise(values, wavelet_cfg)
        preprocess_meta["wavelet"] = {
            "name": wavelet_cfg.get("name", "db4"),
            "level": wavelet_cfg.get("level"),
            "threshold_scale": wavelet_cfg.get("threshold_scale", 1.0),
            "mode": wavelet_cfg.get("mode", "soft"),
        }
    return values, preprocess_meta


def _clean_timeseries_group(
    df: pd.DataFrame,
    config: Dict[str, Any],
    source: str,
    mean: float | None,
    std: float | None,
) -> Tuple[pd.DataFrame, np.ndarray]:
    if df.empty:
        return df, np.array([])

    df = df.copy()
    df["quality_flags"] = _parse_flags(df["quality_flags"])
    source_cfg = _source_preprocess_cfg(config, source)
    preprocess_meta: Dict[str, Any] = {}

    values = pd.to_numeric(df["value"], errors="coerce")
    if source in {"geomag", "aef"}:
        values, preprocess_meta = _apply_geomag_aef_preprocess(values, df["ts_ms"], source_cfg)
    df["value"] = values

    if source == "aef":
        despike_cfg = source_cfg.get("despike", {})
        despike_window = _resolve_int(despike_cfg.get("window_points"), 0)
        despike_threshold = float(despike_cfg.get("zscore_mad_threshold", 6.0))
        if despike_window > 1:
            despike_mask = _hampel_mask(df["value"], despike_window, despike_threshold)
            for idx in df.index[despike_mask]:
                flags = df.at[idx, "quality_flags"]
                flags["is_outlier"] = True
                flags["outlier_method"] = "hampel"
                flags["threshold"] = despike_threshold
                df.at[idx, "quality_flags"] = flags
            df.loc[despike_mask, "value"] = np.nan
            preprocess_meta["despike"] = {
                "window_points": despike_window,
                "threshold": despike_threshold,
            }

    outlier_cfg = source_cfg.get("outlier", config.get("preprocess", {}).get("outlier", {}))
    threshold = float(outlier_cfg.get("threshold", 6.0))
    outlier_mask = _mad_outlier_mask(df["value"], threshold, mean, std)
    for idx in df.index[outlier_mask]:
        flags = df.at[idx, "quality_flags"]
        flags["is_outlier"] = True
        flags["outlier_method"] = "mad"
        flags["threshold"] = threshold
        df.at[idx, "quality_flags"] = flags
    df.loc[outlier_mask, "value"] = np.nan
    preprocess_meta["outlier"] = {"method": "mad", "threshold": threshold}

    interp_cfg = source_cfg.get("interpolate", config.get("preprocess", {}).get("interpolate", {}))
    interp_limit = _resolve_int(
        interp_cfg.get("max_gap_points", interp_cfg.get("max_gap_minutes")), 10
    )
    df["value"] = df["value"].interpolate(limit=interp_limit, limit_direction="both")
    preprocess_meta["interpolate"] = {
        "max_gap_points": interp_limit,
        "method": interp_cfg.get("method", "linear"),
    }
    for idx, val in df["value"].items():
        flags = df.at[idx, "quality_flags"]
        flags["preprocess"] = preprocess_meta
        if math.isnan(val):
            flags["is_missing"] = True
            flags["missing_reason"] = flags.get("missing_reason") or "gap"
        else:
            if flags.get("is_missing"):
                flags["is_interpolated"] = True
                flags["interp_method"] = interp_cfg.get("method", "linear")
        df.at[idx, "quality_flags"] = flags

    before_values = df["value"].astype(float).to_numpy(copy=True)

    lowpass_cfg = source_cfg.get("lowpass", config.get("preprocess", {}).get("filter", {}))
    lowpass_window = _resolve_int(
        lowpass_cfg.get("window_points", lowpass_cfg.get("window")), 0
    )
    if lowpass_window > 1:
        df["value"] = df["value"].rolling(window=lowpass_window, min_periods=1).mean()
        preprocess_meta["lowpass"] = {"window_points": lowpass_window}
        for idx in df.index:
            flags = df.at[idx, "quality_flags"]
            flags["is_filtered"] = True
            flags["filter_type"] = "rolling_mean"
            flags["filter_params"] = {"window": lowpass_window}
            flags["preprocess"] = preprocess_meta
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


def _apply_seismic_preprocess(trace, config: Dict[str, Any]) -> tuple[object, Dict[str, Any]]:
    cfg = config.get("preprocess", {}).get("seismic_bandpass", {}) or {}
    meta: Dict[str, Any] = {"detrend": ["demean", "linear"]}
    trace = trace.copy()
    try:
        trace.detrend("demean")
        trace.detrend("linear")
    except Exception:
        meta["detrend_error"] = "failed"

    taper_pct = float(cfg.get("taper_max_percentage", 0.05))
    if taper_pct > 0:
        try:
            trace.taper(max_percentage=taper_pct, type="cosine")
        except Exception:
            meta["taper_error"] = "failed"

    sr = float(trace.stats.sampling_rate or 0.0)
    freqmin = float(cfg.get("freqmin_hz", 0.5))
    freqmax_user = float(cfg.get("freqmax_user_hz", 20.0))
    nyquist_ratio = float(cfg.get("freqmax_nyquist_ratio", 0.45))
    freqmax = min(freqmax_user, nyquist_ratio * sr) if sr > 0 else freqmax_user
    meta["bandpass"] = {
        "freqmin_hz": freqmin,
        "freqmax_used_hz": freqmax,
        "freqmax_user_hz": freqmax_user,
        "nyquist_ratio": nyquist_ratio,
        "corners": int(cfg.get("corners", 4)),
        "zerophase": bool(cfg.get("zerophase", True)),
    }
    if freqmax > freqmin and sr > 0:
        try:
            trace.filter(
                "bandpass",
                freqmin=freqmin,
                freqmax=freqmax,
                corners=int(cfg.get("corners", 4)),
                zerophase=bool(cfg.get("zerophase", True)),
            )
            meta["bandpass_skipped"] = False
        except Exception:
            meta["bandpass_error"] = "failed"
    else:
        meta["bandpass_skipped"] = True

    notch_cfg = cfg.get("notch", {}) or {}
    base_list = notch_cfg.get("base_hz", [50, 60])
    half_width = float(notch_cfg.get("half_width_hz", 0.5))
    harmonics = int(notch_cfg.get("harmonics", 0))
    meta["notch"] = {
        "base_hz": base_list,
        "half_width_hz": half_width,
        "harmonics": harmonics,
    }
    if sr > 0 and harmonics > 0 and half_width > 0:
        nyquist = sr / 2.0
        for base in base_list:
            for harmonic in range(1, harmonics + 1):
                center = float(base) * harmonic
                if center + half_width >= nyquist or center - half_width <= 0:
                    continue
                try:
                    trace.filter(
                        "bandstop",
                        freqmin=center - half_width,
                        freqmax=center + half_width,
                        corners=2,
                        zerophase=True,
                    )
                except Exception:
                    meta["notch_error"] = "failed"
                    break
    return trace, meta


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
                processed, preprocess_meta = _apply_seismic_preprocess(trace, config)
                data = processed.data.astype(float)
                sr = float(processed.stats.sampling_rate)
                window = int(sr * interval_sec)
                start_time = processed.stats.starttime.datetime
                quality_flags = {
                    "is_filtered": True,
                    "filter_type": "seismic_preprocess",
                    "filter_params": preprocess_meta,
                }
                for idx in range(0, len(data), window):
                    segment = data[idx : idx + window]
                    if len(segment) < window:
                        break
                    ts = pd.Timestamp(start_time, tz="UTC") + pd.Timedelta(seconds=idx / sr)
                    station_id = (
                        f"{processed.stats.network}.{processed.stats.station}."
                        f"{processed.stats.location or ''}.{processed.stats.channel}"
                    )
                    records.append(
                        {
                            "ts_ms": int(ts.value // 1_000_000),
                            "source": "seismic",
                            "station_id": station_id,
                            "channel": f"{processed.stats.channel}_rms",
                            "value": float(np.sqrt(np.mean(segment**2))),
                            "quality_flags": quality_flags,
                        }
                    )
                    records.append(
                        {
                            "ts_ms": int(ts.value // 1_000_000),
                            "source": "seismic",
                            "station_id": station_id,
                            "channel": f"{processed.stats.channel}_mean_abs",
                            "value": float(np.mean(np.abs(segment))),
                            "quality_flags": quality_flags,
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
    if "quality_flags" not in df.columns:
        df["quality_flags"] = [{} for _ in range(len(df))]
    else:
        df["quality_flags"] = df["quality_flags"].apply(
            lambda item: item if isinstance(item, dict) else {}
        )
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
    preprocess_cfg = config.get("preprocess", {}).get("vlf_preprocess", {}) or {}
    standard_cfg = preprocess_cfg.get("standardize", {}) or {}
    band_edges = standard_cfg.get("bands_hz") or config.get("vlf", {}).get(
        "band_edges_hz", [10, 1000, 3000, 10000]
    )

    def _normalize_bands(edges: Any) -> List[Tuple[float, float]]:
        if not edges:
            return []
        if all(isinstance(item, (list, tuple)) and len(item) == 2 for item in edges):
            return [(float(item[0]), float(item[1])) for item in edges]
        pairs = []
        for start, end in zip(edges[:-1], edges[1:]):
            pairs.append((float(start), float(end)))
        return pairs

    bands = _normalize_bands(band_edges)
    freq_agg = str(standard_cfg.get("freq_agg", "median")).lower()
    time_agg = str(standard_cfg.get("time_agg", "median")).lower()
    target_interval = str(standard_cfg.get("target_interval", "1min"))
    interval_ms = int(pd.Timedelta(target_interval).total_seconds() * 1000)
    time_median_window = _resolve_int(preprocess_cfg.get("time_median_window"), 1)
    line_mask_cfg = preprocess_cfg.get("freq_line_mask", {}) or {}
    bg_cfg = preprocess_cfg.get("background_subtract", {}) or {}

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

            mask = np.zeros_like(freq, dtype=bool)
            base_list = line_mask_cfg.get("base_hz", [50, 60])
            harmonics = int(line_mask_cfg.get("harmonics", 5))
            half_width = float(line_mask_cfg.get("half_width_hz", 0.5))
            if harmonics > 0 and half_width > 0:
                for base in base_list:
                    for harmonic in range(1, harmonics + 1):
                        center = float(base) * harmonic
                        mask |= (freq >= center - half_width) & (freq <= center + half_width)
            if mask.any():
                ch1 = ch1.copy()
                ch2 = ch2.copy()
                ch1[:, mask] = np.nan
                ch2[:, mask] = np.nan

            for i, ts_ns in enumerate(epoch_ns):
                ts_ms = int(ts_ns // 1_000_000)
                for band_start, band_end in bands:
                    band_mask = (freq >= band_start) & (freq < band_end)
                    band_vals_ch1 = ch1[i, band_mask]
                    band_vals_ch2 = ch2[i, band_mask]
                    if freq_agg == "mean":
                        band_power_ch1 = float(np.nanmean(band_vals_ch1))
                        band_power_ch2 = float(np.nanmean(band_vals_ch2))
                    else:
                        band_power_ch1 = float(np.nanmedian(band_vals_ch1))
                        band_power_ch2 = float(np.nanmedian(band_vals_ch2))
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
    if interval_ms > 0:
        df["ts_ms"] = (df["ts_ms"] // interval_ms) * interval_ms
        agg_func = np.nanmean if time_agg == "mean" else np.nanmedian
        df = (
            df.groupby(["ts_ms", "source", "station_id", "channel"], as_index=False)["value"]
            .agg(agg_func)
        )

    if time_median_window > 1 and not df.empty:
        df = df.sort_values("ts_ms")
        df["value"] = df.groupby(["station_id", "channel"], sort=False)["value"].transform(
            lambda series: series.rolling(
                time_median_window, center=True, min_periods=1
            ).median()
        )

    if bg_cfg:
        method = str(bg_cfg.get("method", "median")).lower()
        if method in {"median", "mean"}:
            baseline = (
                df.groupby(["station_id", "channel"])["value"].median()
                if method == "median"
                else df.groupby(["station_id", "channel"])["value"].mean()
            )
            df["value"] = df.apply(
                lambda row: row["value"]
                - baseline.get((row["station_id"], row["channel"]), 0.0),
                axis=1,
            )
            df["value"] = df["value"].clip(lower=0.0)

    preprocess_meta = {
        "freq_line_mask": {
            "base_hz": base_list,
            "harmonics": harmonics,
            "half_width_hz": half_width,
        },
        "freq_agg": freq_agg,
        "time_agg": time_agg,
        "target_interval": target_interval,
        "time_median_window": time_median_window,
        "background_subtract": bg_cfg or {},
    }

    df["quality_flags"] = [preprocess_meta for _ in range(len(df))]
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
    overlap = _resolve_overlap(config, source)
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
                cleaned, before_values = _clean_timeseries_group(
                    combined_raw, config, source, mean, std
                )
                if overlap > 0 and len(cleaned) > overlap:
                    to_write = cleaned.iloc[:-overlap].copy()
                    before_values = before_values[:-overlap]
                    tails[key] = combined_raw.iloc[-overlap:].copy()
                else:
                    to_write = cleaned.copy()
                    tails[key] = combined_raw.iloc[0:0].copy()

                if to_write.empty:
                    continue
                to_write = to_write.copy()
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
            cleaned, before_values = _clean_timeseries_group(
                tail_raw, config, source, mean, std
            )
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

    geomag_ingest = output_paths.ingest / "geomag"
    if geomag_ingest.exists():
        report, filter_effect = _process_standard_source(
            "geomag", geomag_ingest, output_paths, config, params_hash, max_rows
        )
        if report:
            reports["geomag"] = report
            filter_reports["geomag"] = filter_effect

    aef_ingest = output_paths.ingest / "aef"
    if aef_ingest.exists():
        report, filter_effect = _process_standard_source(
            "aef", aef_ingest, output_paths, config, params_hash, max_rows
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
