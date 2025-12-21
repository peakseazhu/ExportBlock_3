import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from scripts.render_event_summary import render_event_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Create event bundle zip.")
    parser.add_argument("--event_id", required=True)
    args = parser.parse_args()

    event_dir = ROOT / "outputs" / "events" / args.event_id
    if not event_dir.exists():
        raise FileNotFoundError(f"Event directory not found: {event_dir}")

    render_event_summary(args.event_id, ROOT / "outputs", "md", event_dir=event_dir)

    bundle_path = event_dir / "event_bundle.zip"
    if bundle_path.exists():
        bundle_path.unlink()

    shutil.make_archive(str(event_dir / "event_bundle"), "zip", root_dir=event_dir)


if __name__ == "__main__":
    main()
