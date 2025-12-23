import os
from importlib import reload
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.store.parquet import write_parquet_partitioned

@pytest.mark.smoke
def test_api_smoke(tmp_path: Path):
    output_root = tmp_path / "outputs"
    raw_dir = output_root / "raw" / "source=geomag"
    standard_dir = output_root / "standard" / "source=geomag"
    raw_dir.mkdir(parents=True, exist_ok=True)
    standard_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        [
            {
                "ts_ms": 0,
                "source": "geomag",
                "station_id": "KAK",
                "channel": "X",
                "value": 1.0,
                "lat": 0.0,
                "lon": 0.0,
                "elev": 0.0,
                "quality_flags": {},
            }
        ]
    )
    config = {"storage": {"parquet": {"partition_cols": ["station_id", "date"], "batch_rows": 100000}}}
    write_parquet_partitioned(df, raw_dir, config)
    write_parquet_partitioned(df, standard_dir, config)

    os.environ["OUTPUT_ROOT"] = str(output_root)
    import src.api.app as app_module

    reload(app_module)
    client = TestClient(app_module.app)
    assert client.get("/health").status_code == 200
    assert client.get("/raw/query", params={"source": "geomag"}).status_code == 200
    assert client.get("/standard/query", params={"source": "geomag"}).status_code == 200
