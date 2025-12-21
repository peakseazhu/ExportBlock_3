import os
from importlib import reload
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.mark.smoke
def test_api_smoke(tmp_path: Path):
    output_root = tmp_path / "outputs"
    raw_dir = output_root / "raw" / "geomag"
    standard_dir = output_root / "standard" / "geomag"
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
    df.to_parquet(raw_dir / "data.parquet", index=False)
    df.to_parquet(standard_dir / "data.parquet", index=False)

    os.environ["OUTPUT_ROOT"] = str(output_root)
    import src.api.app as app_module

    reload(app_module)
    client = TestClient(app_module.app)
    assert client.get("/health").status_code == 200
    assert client.get("/raw/query", params={"source": "geomag"}).status_code == 200
    assert client.get("/standard/query", params={"source": "geomag"}).status_code == 200
