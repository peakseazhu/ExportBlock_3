import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.config import compute_params_hash, load_config
from src.pipeline.runner import STAGE_ORDER, run_stages
from src.store.paths import OutputPaths
from src.utils import ensure_dir, write_json


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multi-source pipeline stages.")
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--stages", required=True, help="Comma-separated stages.")
    parser.add_argument("--event_id", default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--list-stages", action="store_true")
    args = parser.parse_args()

    if args.list_stages:
        print(",".join(STAGE_ORDER))
        return

    base_dir = ROOT
    config_path = base_dir / args.config
    config = load_config(config_path)

    params_hash = compute_params_hash(config)
    run_id = _utc_run_id()

    output_root = base_dir / config.get("outputs", {}).get("root", "outputs")
    output_paths = OutputPaths(output_root)
    output_paths.ensure()

    snapshot_path = output_paths.reports / "config_snapshot.yaml"
    ensure_dir(snapshot_path.parent)
    with snapshot_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            {
                "run_id": run_id,
                "params_hash": params_hash,
                "config_path": str(config_path),
                "config": config,
            },
            handle,
            allow_unicode=True,
            sort_keys=False,
        )

    stages = [stage.strip() for stage in args.stages.split(",") if stage.strip()]
    run_started = datetime.now(timezone.utc)
    tick = time.perf_counter()
    stage_timings = run_stages(
        stages=stages,
        base_dir=base_dir,
        config=config,
        output_paths=output_paths,
        run_id=run_id,
        params_hash=params_hash,
        strict=args.strict,
        event_id=args.event_id,
    )
    run_ended = datetime.now(timezone.utc)
    total_s = round(time.perf_counter() - tick, 3)
    timing_report = {
        "run_id": run_id,
        "start_utc": run_started.isoformat().replace("+00:00", "Z"),
        "end_utc": run_ended.isoformat().replace("+00:00", "Z"),
        "duration_s": total_s,
        "stages": stage_timings,
    }
    write_json(output_paths.reports / "runtime_report.json", timing_report)
    print(f"Run started: {timing_report['start_utc']}")
    print(f"Run ended:   {timing_report['end_utc']}")
    print(f"Duration:    {timing_report['duration_s']}s (details in outputs/reports/runtime_report.json)")


if __name__ == "__main__":
    main()
