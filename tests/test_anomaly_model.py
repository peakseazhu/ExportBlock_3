import pandas as pd
import pytest
from pathlib import Path

from src.pipeline.model import run_model
from src.store.paths import OutputPaths


@pytest.mark.integ
def test_anomaly_model(tmp_path: Path):
    output_paths = OutputPaths(tmp_path / "outputs")
    output_paths.ensure()
    event_id = "event_test"
    features_dir = output_paths.features / event_id
    features_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        [
            {"event_id": event_id, "source": "geomag", "station_id": "A", "channel": "X", "feature": "mean", "value": 0},
            {"event_id": event_id, "source": "geomag", "station_id": "B", "channel": "X", "feature": "mean", "value": 10},
        ]
    )
    df.to_parquet(features_dir / "features.parquet", index=False)

    config = {"events": [{"event_id": event_id}], "features": {"anomaly_threshold": 0.5, "topn_anomalies": 10}}
    run_model(tmp_path, config, output_paths, "run", "hash", False, event_id)

    anomaly_path = features_dir / "anomaly.parquet"
    assert anomaly_path.exists()
    anomalies = pd.read_parquet(anomaly_path)
    assert len(anomalies) >= 1
