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
    raw_index_dir = output_root / "raw" / "index" / "source=geomag"
    standard_dir = output_root / "standard" / "source=geomag"
    raw_index_dir.mkdir(parents=True, exist_ok=True)
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
    write_parquet_partitioned(df, standard_dir, config)

    sample_path = tmp_path / "sample.sec"
    sample_path.write_text(
        " Format                 IAGA-2002                                    |\n"
        " Station Name           Kakioka                                      |\n"
        " IAGA Code              KAK                                          |\n"
        " Geodetic Latitude      36.232                                       |\n"
        " Geodetic Longitude     140.186                                      |\n"
        " Elevation              36                                           |\n"
        " Reported               XYZG                                         |\n"
        "DATE       TIME         DOY     KAKX      KAKY      KAKZ      KAKG   |\n"
        "2020-01-01 00:00:00.000 001     100.00    200.00    300.00    400.00\n"
        "2020-01-01 00:00:01.000 001     101.00    201.00    301.00    401.00\n",
        encoding="utf-8",
    )
    start_ms = int(pd.Timestamp("2020-01-01T00:00:00Z").value // 1_000_000)
    end_ms = int(pd.Timestamp("2020-01-01T00:00:01Z").value // 1_000_000)
    index_df = pd.DataFrame(
        [
            {
                "source": "geomag",
                "station_id": "KAK",
                "lat": 36.232,
                "lon": 140.186,
                "elev": 36.0,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "file_path": str(sample_path),
                "proc_version": "0.1.0",
                "params_hash": "testhash",
            }
        ]
    )
    index_df.to_parquet(raw_index_dir / "data.parquet", index=False)

    os.environ["OUTPUT_ROOT"] = str(output_root)
    import src.api.app as app_module

    reload(app_module)
    client = TestClient(app_module.app)
    assert client.get("/health").status_code == 200
    raw_resp = client.get("/raw/query", params={"source": "geomag"})
    assert raw_resp.status_code == 200
    assert len(raw_resp.json()) > 0
    assert client.get("/standard/query", params={"source": "geomag"}).status_code == 200
