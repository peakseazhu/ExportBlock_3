import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.render_event_summary import render_event_summary


@pytest.mark.integ
def test_render_event_summary(tmp_path: Path):
    output_root = tmp_path / "outputs"
    event_id = "event_demo"
    event_dir = output_root / "events" / event_id
    (event_dir / "reports").mkdir(parents=True, exist_ok=True)
    (event_dir / "plots" / "html").mkdir(parents=True, exist_ok=True)
    (event_dir / "features").mkdir(parents=True, exist_ok=True)
    (event_dir / "linked").mkdir(parents=True, exist_ok=True)

    (event_dir / "event.json").write_text(
        json.dumps({"event_id": event_id, "origin_time_utc": "2020-01-01T00:00:00Z", "params_hash": "hash"}), "utf-8"
    )
    (event_dir / "linked" / "summary.json").write_text(json.dumps({"join_coverage": 0.5}), "utf-8")
    for name in ["dq_event_link.json", "dq_event_features.json", "dq_plots.json", "filter_effect.json"]:
        (event_dir / "reports" / name).write_text(json.dumps({"ok": True}), "utf-8")

    for name in ["plot_aligned_timeseries.html", "plot_station_map.html", "plot_filter_effect.html"]:
        (event_dir / "plots" / "html" / name).write_text("<html></html>", "utf-8")

    anomalies = pd.DataFrame(
        [{"rank": 1, "source": "geomag", "station_id": "A", "feature": "mean", "score": 3.2}]
    )
    anomalies.to_parquet(event_dir / "features" / "anomaly.parquet", index=False)

    md_path = render_event_summary(event_id, output_root, "md", event_dir=event_dir)
    content = md_path.read_text(encoding="utf-8")
    assert "0. 事件基本信息" in content
    assert "params_hash" in content
