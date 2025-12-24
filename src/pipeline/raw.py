from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.dq.reporting import write_dq_report
from src.io.iaga2002 import resolve_iaga_patterns, scan_iaga_file
from src.store.parquet import read_parquet, write_parquet_configured
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


def _relativize_path(path: Path, base_dir: Path) -> str:
    try:
        return str(path.relative_to(base_dir))
    except ValueError:
        return str(path)


def _write_index(df: pd.DataFrame, output_dir: Path, config: Dict[str, Any]) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    ensure_dir(output_dir)
    write_parquet_configured(df, output_dir, config, partition_cols=None)


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
    max_files = limits.get("max_files_per_source")
    stats = {}

    raw_index_root = output_paths.raw_index

    paths_cfg = config.get("paths", {})

    # Geomag index
    geomag_cfg = paths_cfg.get("geomag", {})
    geomag_root = base_dir / geomag_cfg.get("root", "")
    geomag_files = _collect_files(geomag_root, resolve_iaga_patterns(geomag_cfg), max_files)
    geomag_records = []
    for path in geomag_files:
        info = scan_iaga_file(path)
        info["file_path"] = _relativize_path(Path(info["file_path"]), base_dir)
        info["source"] = "geomag"
        info["proc_stage"] = "raw_index"
        info["proc_version"] = pipeline_version
        info["params_hash"] = params_hash
        geomag_records.append(info)
    if geomag_records:
        geomag_df = pd.DataFrame.from_records(geomag_records)
        _write_index(geomag_df, raw_index_root / "source=geomag", config)
        stats["geomag"] = {
            "files": int(len(geomag_df)),
            "stations": int(geomag_df["station_id"].nunique()),
            "ts_min": int(geomag_df["start_ms"].min()) if geomag_df["start_ms"].notna().any() else None,
            "ts_max": int(geomag_df["end_ms"].max()) if geomag_df["end_ms"].notna().any() else None,
        }

    # AEF index
    aef_cfg = paths_cfg.get("aef", {})
    aef_root = base_dir / aef_cfg.get("root", "")
    aef_files = _collect_files(aef_root, resolve_iaga_patterns(aef_cfg), max_files)
    aef_records = []
    for path in aef_files:
        info = scan_iaga_file(path)
        info["file_path"] = _relativize_path(Path(info["file_path"]), base_dir)
        info["source"] = "aef"
        info["proc_stage"] = "raw_index"
        info["proc_version"] = pipeline_version
        info["params_hash"] = params_hash
        aef_records.append(info)
    if aef_records:
        aef_df = pd.DataFrame.from_records(aef_records)
        _write_index(aef_df, raw_index_root / "source=aef", config)
        stats["aef"] = {
            "files": int(len(aef_df)),
            "stations": int(aef_df["station_id"].nunique()),
            "ts_min": int(aef_df["start_ms"].min()) if aef_df["start_ms"].notna().any() else None,
            "ts_max": int(aef_df["end_ms"].max()) if aef_df["end_ms"].notna().any() else None,
        }

    # Seismic trace index
    seismic_ingest = output_paths.ingest / "seismic"
    if seismic_ingest.exists():
        trace_df = read_parquet(seismic_ingest)
        if not trace_df.empty:
            index_df = trace_df.copy()
            index_df["source"] = "seismic"
            index_df["proc_stage"] = "raw_index"
            index_df["proc_version"] = pipeline_version
            index_df["params_hash"] = params_hash
            index_df["start_ms"] = (
                pd.to_datetime(index_df["starttime"], utc=True).astype("int64") // 1_000_000
            )
            index_df["end_ms"] = (
                pd.to_datetime(index_df["endtime"], utc=True).astype("int64") // 1_000_000
            )
            index_df["file_path"] = index_df["file_path"].apply(
                lambda value: _relativize_path(Path(value), base_dir)
            )
            _write_index(index_df, raw_index_root / "source=seismic", config)
            stats["seismic"] = {
                "traces": int(len(index_df)),
                "stations": int(index_df["station_id"].nunique()),
                "ts_min": int(index_df["start_ms"].min()),
                "ts_max": int(index_df["end_ms"].max()),
            }

    # VLF index (catalog)
    vlf_catalog = output_paths.raw / "vlf_catalog.parquet"
    if vlf_catalog.exists():
        vlf_df = read_parquet(vlf_catalog)
        if not vlf_df.empty:
            vlf_df = vlf_df.copy()
            vlf_df["source"] = "vlf"
            vlf_df["proc_stage"] = "raw_index"
            vlf_df["proc_version"] = pipeline_version
            vlf_df["params_hash"] = params_hash
            if "file" in vlf_df.columns:
                vlf_df["file_path"] = vlf_df["file"].apply(
                    lambda value: _relativize_path(Path(value), base_dir)
                )
            _write_index(vlf_df, raw_index_root / "source=vlf", config)
            stats["vlf"] = {
                "files": int(len(vlf_df)),
                "stations": int(vlf_df["station_id"].nunique()),
            }

    write_dq_report(output_paths.reports / "dq_raw.json", {"sources": stats})

    index_sizes = {}
    for source in stats.keys():
        source_path = raw_index_root / f"source={source}"
        if source_path.exists():
            total_bytes = sum(p.stat().st_size for p in source_path.rglob("*") if p.is_file())
            index_sizes[source] = {"index_bytes": total_bytes}
    write_json(output_paths.reports / "compression.json", index_sizes)
    write_json(output_paths.reports / "compression_stats.json", index_sizes)
