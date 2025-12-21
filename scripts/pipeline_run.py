import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.config import compute_params_hash, load_config
from src.pipeline.runner import STAGE_ORDER, run_stages
from src.store.paths import OutputPaths
from src.utils import ensure_dir


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
    run_stages(
        stages=stages,
        base_dir=base_dir,
        config=config,
        output_paths=output_paths,
        run_id=run_id,
        params_hash=params_hash,
        strict=args.strict,
        event_id=args.event_id,
    )


if __name__ == "__main__":
    main()
