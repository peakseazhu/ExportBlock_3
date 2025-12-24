from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from datetime import datetime, timezone

from src.io.iaga2002 import resolve_iaga_patterns
from src.utils import compute_sha256, utc_now_iso, write_json


def _collect_files(root: Path, patterns: List[str], max_files: int | None) -> List[Path]:
    files: List[Path] = []
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file():
                files.append(path)
                if max_files and len(files) >= max_files:
                    return files
    return files


def build_manifest(
    base_dir: Path,
    config: Dict[str, Any],
    output_path: Path,
    run_id: str,
    params_hash: str,
) -> Dict[str, Any]:
    paths_cfg = config.get("paths", {})
    limits = config.get("limits", {}) or {}
    max_files = limits.get("max_files_per_source")

    manifest_files = []
    for source, cfg in paths_cfg.items():
        root = base_dir / cfg.get("root", "")
        patterns = cfg.get("patterns") or []
        if source in {"geomag", "aef"}:
            patterns = resolve_iaga_patterns(cfg)
        if source == "seismic":
            patterns = list(cfg.get("mseed_patterns", [])) + list(cfg.get("sac_patterns", []))
            stationxml = cfg.get("stationxml")
            if stationxml:
                patterns += [Path(stationxml).name]
        for path in _collect_files(root, patterns, max_files):
            stat = path.stat()
            mtime_utc = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat().replace(
                "+00:00", "Z"
            )
            manifest_files.append(
                {
                    "source": source,
                    "path": str(path.relative_to(base_dir)),
                    "size_bytes": stat.st_size,
                    "mtime_utc": mtime_utc,
                    "sha256": compute_sha256(path),
                }
            )

    payload = {
        "run_id": run_id,
        "params_hash": params_hash,
        "generated_at_utc": utc_now_iso(),
        "total_files": len(manifest_files),
        "total_bytes": sum(item["size_bytes"] for item in manifest_files),
        "files": manifest_files,
    }
    write_json(output_path, payload)
    return payload
