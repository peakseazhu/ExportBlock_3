import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from scripts.render_event_summary import render_event_summary
from src.utils import ensure_dir, write_json


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _copytree(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    ensure_dir(dest)
    for path in src.rglob("*"):
        if path.is_file():
            target = dest / path.relative_to(src)
            ensure_dir(target.parent)
            shutil.copy2(path, target)


def _build_manifest(event_dir: Path, required_files: list[str], optional_files: list[str]) -> dict:
    def file_info(rel_path: str) -> dict:
        path = event_dir / rel_path
        exists = path.exists()
        return {
            "path": rel_path,
            "exists": exists,
            "bytes": path.stat().st_size if exists else 0,
            "mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace(
                "+00:00", "Z"
            )
            if exists
            else None,
        }

    required = [file_info(p) for p in required_files]
    optional = [file_info(p) for p in optional_files]
    missing_required = [item["path"] for item in required if not item["exists"]]
    completeness = 1.0 - len(missing_required) / len(required) if required else 0.0
    return {
        "required_files": required,
        "optional_files": optional,
        "missing_required": missing_required,
        "completeness_ratio_required": completeness,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize event directory into outputs/events/<event_id>.")
    parser.add_argument("--event_id", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    event_id = args.event_id
    output_root = ROOT / "outputs"
    tmp_dir = output_root / "events" / f".tmp_{event_id}_{_utc_run_id()}"
    final_dir = output_root / "events" / event_id

    linked_dir = output_root / "linked" / event_id
    features_dir = output_root / "features" / event_id
    plots_dir = output_root / "plots"

    ensure_dir(tmp_dir / "reports")
    _copytree(linked_dir, tmp_dir / "linked")
    _copytree(features_dir, tmp_dir / "features")
    _copytree(plots_dir / "html" / event_id, tmp_dir / "plots" / "html")
    _copytree(plots_dir / "spec" / event_id, tmp_dir / "plots" / "spec")

    if (linked_dir / "event.json").exists():
        shutil.copy2(linked_dir / "event.json", tmp_dir / "event.json")

    # Copy event-level DQ reports if available
    for name, src in {
        "dq_event_link.json": linked_dir / "dq_linked.json",
        "dq_event_features.json": features_dir / "dq_features.json",
        "dq_plots.json": plots_dir / "spec" / event_id / "dq_plots.json",
        "filter_effect.json": output_root / "reports" / "filter_effect.json",
    }.items():
        if src.exists():
            shutil.copy2(src, tmp_dir / "reports" / name)

    # Render summary after required assets are in place
    render_event_summary(event_id, output_root, "md", event_dir=tmp_dir)

    required_files = [
        "event.json",
        "linked/summary.json",
        "linked/aligned.parquet",
        "linked/stations.json",
        "features/summary.json",
        "features/features.parquet",
        "features/anomaly.parquet",
        "plots/html/plot_aligned_timeseries.html",
        "plots/html/plot_station_map.html",
        "plots/html/plot_filter_effect.html",
        "reports/dq_event_link.json",
        "reports/dq_event_features.json",
        "reports/dq_plots.json",
        "reports/filter_effect.json",
        "reports/event_summary.md",
    ]
    optional_files = ["plots/html/plot_vlf_spectrogram.html"]
    manifest = _build_manifest(tmp_dir, required_files, optional_files)
    write_json(tmp_dir / "reports" / "artifacts_manifest.json", manifest)

    if manifest["missing_required"] and args.strict:
        fail_payload = {
            "missing_required": manifest["missing_required"],
            "run_id": tmp_dir.name,
        }
        write_json(tmp_dir / "reports" / "finalize_fail.json", fail_payload)
        (tmp_dir / "FAIL").touch()
        failed_dir = final_dir.parent / f".failed_{tmp_dir.name}"
        if failed_dir.exists():
            shutil.rmtree(failed_dir)
        tmp_dir.rename(failed_dir)
        sys.exit(1)

    # Move tmp to final
    if final_dir.exists():
        shutil.rmtree(final_dir)
    tmp_dir.rename(final_dir)
    (final_dir / "DONE").touch()


if __name__ == "__main__":
    main()
