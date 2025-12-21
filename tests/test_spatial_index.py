import pandas as pd
import pytest

from src.pipeline.spatial import SpatialIndex


@pytest.mark.unit
def test_spatial_query_radius():
    df = pd.DataFrame(
        [
            {"station_id": "A", "lat": 0.0, "lon": 0.0, "elev": 0.0},
            {"station_id": "B", "lat": 20.0, "lon": 20.0, "elev": 0.0},
        ]
    )
    index = SpatialIndex(df)
    result = index.query_radius(0.0, 0.0, 500)
    assert "A" in result["station_id"].tolist()
    assert "B" not in result["station_id"].tolist()
