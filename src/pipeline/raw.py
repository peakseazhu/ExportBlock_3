from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from src.dq.reporting import basic_stats, write_dq_report
from src.store.parquet import read_parquet, write_parquet_configured
from src.utils import ensure_dir, write_json


def _copy_files(src_dir: Path, dest_dir: Path, patterns: list[str]) -> None:
    ensure_dir(dest_dir)
    for pattern in patterns:
        for path in src_dir.glob(pattern):
            if path.is_file():
                shutil.copy2(path, dest_dir / path.name)


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
    stats = {}

    # Geomag
    geomag_ingest = output_paths.ingest / "geomag"
    if geomag_ingest.exists():
        geomag_df = read_parquet(geomag_ingest)
        geomag_df["proc_stage"] = "raw"
        geomag_df["proc_version"] = pipeline_version
        geomag_df["params_hash"] = params_hash
        write_parquet_configured(geomag_df, output_paths.raw / "geomag", config, partition_cols=["source"])
        stats["geomag"] = basic_stats(geomag_df)

    # AEF
    aef_ingest = output_paths.ingest / "aef"
    if aef_ingest.exists():
        aef_df = read_parquet(aef_ingest)
        aef_df["proc_stage"] = "raw"
        aef_df["proc_version"] = pipeline_version
        aef_df["params_hash"] = params_hash
        write_parquet_configured(aef_df, output_paths.raw / "aef", config, partition_cols=["source"])
        stats["aef"] = basic_stats(aef_df)

    # Seismic trace index + raw files
    seismic_ingest = output_paths.ingest / "seismic"
    if seismic_ingest.exists():
        trace_df = read_parquet(seismic_ingest)
        trace_df["proc_stage"] = "raw"
        trace_df["proc_version"] = pipeline_version
        trace_df["params_hash"] = params_hash
        write_parquet_configured(trace_df, output_paths.raw / "seismic", config, partition_cols=None)
        stats["seismic"] = {
            "trace_count": int(len(trace_df)),
            "station_count": int(trace_df["station"].nunique()) if not trace_df.empty else 0,
        }

    # Copy original waveform files and stationxml for raw storage
    seismic_cfg = config.get("paths", {}).get("seismic", {})
    seismic_root = base_dir / seismic_cfg.get("root", "")
    raw_seismic_files = output_paths.raw / "seismic_files"
    if seismic_root.exists():
        _copy_files(seismic_root, raw_seismic_files, ["*.mseed", "*.seed", "*.sac", "*.xml"])

    # VLF data already stored by ingest; ensure catalog available
    vlf_catalog = output_paths.raw / "vlf_catalog"
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
        source_path = output_paths.raw / source
        if source_path.exists():
            total_bytes = sum(p.stat().st_size for p in source_path.rglob("*") if p.is_file())
            compression[source] = {"bytes": total_bytes}
    write_json(output_paths.reports / "compression.json", compression)
    write_json(output_paths.reports / "compression_stats.json", compression)
