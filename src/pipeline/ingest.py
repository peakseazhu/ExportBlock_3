from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import zarr

from src.config import get_event
from src.dq.reporting import basic_stats, write_dq_report
from src.io.iaga2002 import parse_iaga_file
from src.io.seismic import extract_trace_metadata, join_station_metadata, load_station_metadata
from src.io.vlf import compute_gap_report, read_vlf_cdf
from src.store.parquet import write_parquet_configured
from src.utils import ensure_dir, write_json


def _collect_files(root: Path, patterns: List[str], max_files: int | None) -> List[Path]:
    files: List[Path] = []
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file():
                files.append(path)
                if max_files and len(files) >= max_files:
                    return files
    return files


def _write_preview_png(path: Path, matrix: np.ndarray, max_time: int, max_freq: int) -> None:
    ensure_dir(path.parent)
    preview = matrix[:max_time, :max_freq]
    plt.figure(figsize=(6, 4))
    plt.imshow(np.log10(preview + 1e-12).T, aspect="auto", origin="lower")
    plt.colorbar(label="log10(V^2/Hz)")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def run_ingest(
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
    max_files = limits.get("max_files_per_source")
    max_rows = limits.get("max_rows_per_source")

    paths_cfg = config.get("paths", {})
    geomag_cfg = paths_cfg.get("geomag", {})
    aef_cfg = paths_cfg.get("aef", {})
    seismic_cfg = paths_cfg.get("seismic", {})
    vlf_cfg = paths_cfg.get("vlf", {})

    # IAGA2002 (geomag)
    geomag_root = base_dir / geomag_cfg.get("root", "")
    geomag_files = _collect_files(geomag_root, geomag_cfg.get("patterns", []), max_files)
    geomag_frames = [
        parse_iaga_file(path, "geomag", params_hash, "ingest", pipeline_version) for path in geomag_files
    ]
    geomag_df = pd.concat(geomag_frames, ignore_index=True) if geomag_frames else pd.DataFrame()
    if max_rows:
        geomag_df = geomag_df.head(max_rows)
    write_parquet_configured(geomag_df, output_paths.ingest / "geomag", config, partition_cols=None)
    dq_iaga = {"geomag": basic_stats(geomag_df)}

    # AEF
    aef_root = base_dir / aef_cfg.get("root", "")
    aef_files = _collect_files(aef_root, aef_cfg.get("patterns", []), max_files)
    aef_frames = [parse_iaga_file(path, "aef", params_hash, "ingest", pipeline_version) for path in aef_files]
    aef_df = pd.concat(aef_frames, ignore_index=True) if aef_frames else pd.DataFrame()
    if max_rows:
        aef_df = aef_df.head(max_rows)
    write_parquet_configured(aef_df, output_paths.ingest / "aef", config, partition_cols=None)
    dq_iaga["aef"] = basic_stats(aef_df)
    write_dq_report(output_paths.reports / "dq_ingest_iaga.json", dq_iaga)

    # MiniSEED + StationXML
    seismic_root = base_dir / seismic_cfg.get("root", "")
    mseed_patterns = list(seismic_cfg.get("mseed_patterns", []))
    mseed_files = _collect_files(seismic_root, mseed_patterns, max_files)
    trace_df = extract_trace_metadata(mseed_files) if mseed_files else pd.DataFrame()

    stationxml_path = seismic_cfg.get("stationxml")
    station_report = {"trace_count": 0, "matched_ratio": 0, "unmatched_keys_topN": []}
    if stationxml_path and Path(base_dir / stationxml_path).exists() and not trace_df.empty:
        meta = load_station_metadata(base_dir / stationxml_path)
        trace_df, station_report = join_station_metadata(trace_df, meta)

    write_parquet_configured(trace_df, output_paths.ingest / "seismic", config, partition_cols=None)
    if not trace_df.empty:
        ts_min = trace_df["starttime"].min()
        ts_max = trace_df["endtime"].max()
        dq_mseed = {
            "trace_count": int(len(trace_df)),
            "ts_min": int(pd.Timestamp(ts_min).value // 1_000_000),
            "ts_max": int(pd.Timestamp(ts_max).value // 1_000_000),
        }
    else:
        dq_mseed = {"trace_count": 0, "ts_min": None, "ts_max": None}
    write_dq_report(output_paths.reports / "dq_ingest_mseed.json", dq_mseed)
    write_json(output_paths.reports / "station_match.json", station_report)

    # VLF CDF ingest
    vlf_root = base_dir / vlf_cfg.get("root", "")
    vlf_files = _collect_files(vlf_root, vlf_cfg.get("patterns", []), max_files)
    vlf_records = []
    vlf_dt_medians = []
    preview_cfg = config.get("vlf", {}).get("preview", {})
    max_time_bins = int(preview_cfg.get("max_time_bins", 200))
    max_freq_bins = int(preview_cfg.get("max_freq_bins", 200))

    for path in vlf_files:
        payload = read_vlf_cdf(path)
        epoch_ns = payload["epoch_ns"]
        gap_report = compute_gap_report(epoch_ns)
        if gap_report.get("dt_median_s") is not None:
            vlf_dt_medians.append(gap_report["dt_median_s"])

        stem = path.stem
        vlf_dir = output_paths.raw / "vlf" / payload["station_id"] / stem
        ensure_dir(vlf_dir)
        zarr_path = vlf_dir / "spectrogram.zarr"
        root = zarr.open(str(zarr_path), mode="w")
        root.create_dataset("epoch_ns", data=epoch_ns, shape=epoch_ns.shape, dtype=epoch_ns.dtype)
        root.create_dataset(
            "freq_hz",
            data=payload["freq_hz"],
            shape=payload["freq_hz"].shape,
            dtype=payload["freq_hz"].dtype,
        )
        root.create_dataset("ch1", data=payload["ch1"], shape=payload["ch1"].shape, dtype=payload["ch1"].dtype)
        root.create_dataset("ch2", data=payload["ch2"], shape=payload["ch2"].shape, dtype=payload["ch2"].dtype)

        meta = {
            "station_id": payload["station_id"],
            "n_time": int(len(epoch_ns)),
            "n_freq": int(len(payload["freq_hz"])),
            "freq_min": float(payload["freq_hz"].min()),
            "freq_max": float(payload["freq_hz"].max()),
            "dt_median_s": gap_report.get("dt_median_s"),
            "units": "V^2/Hz",
            "source_file": str(path),
        }
        write_json(vlf_dir / "vlf_meta.json", meta)
        write_json(vlf_dir / "vlf_gap_report.json", gap_report)
        _write_preview_png(vlf_dir / "vlf_preview.png", payload["ch1"], max_time_bins, max_freq_bins)

        vlf_records.append(
            {
                "station_id": payload["station_id"],
                "file": str(path),
                "ts_start_ns": int(epoch_ns[0]) if len(epoch_ns) else None,
                "ts_end_ns": int(epoch_ns[-1]) if len(epoch_ns) else None,
                "n_time": int(len(epoch_ns)),
                "n_freq": int(len(payload["freq_hz"])),
                "freq_min": float(payload["freq_hz"].min()) if len(payload["freq_hz"]) else None,
                "freq_max": float(payload["freq_hz"].max()) if len(payload["freq_hz"]) else None,
            }
        )

    if vlf_records:
        vlf_catalog = pd.DataFrame.from_records(vlf_records)
        write_parquet_configured(vlf_catalog, output_paths.raw / "vlf_catalog.parquet", config, partition_cols=None)
        sample = vlf_records[0]
        dq_vlf = {
            "files": len(vlf_records),
            "stations": int(vlf_catalog["station_id"].nunique()),
            "dt_median_s": float(np.median(vlf_dt_medians)) if vlf_dt_medians else None,
            "sample_shape": [sample.get("n_time"), sample.get("n_freq")],
            "freq_min": sample.get("freq_min"),
            "freq_max": sample.get("freq_max"),
        }
    else:
        dq_vlf = {"files": 0, "stations": 0, "dt_median_s": None}
    write_dq_report(output_paths.reports / "dq_ingest_vlf.json", dq_vlf)

    # Preserve optional SAC files into ingest cache for later stages
    sac_patterns = list(seismic_cfg.get("sac_patterns", []))
    sac_files = _collect_files(seismic_root, sac_patterns, max_files)
    if sac_files:
        sac_dir = output_paths.ingest / "seismic_sac"
        ensure_dir(sac_dir)
        for path in sac_files:
            shutil.copy2(path, sac_dir / path.name)
