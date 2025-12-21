from pathlib import Path

import pandas as pd
import pytest

from src.io.iaga2002 import parse_iaga_file


@pytest.mark.unit
def test_iaga_parser_basic():
    fixture = Path("fixtures/iaga_sample.min")
    df = parse_iaga_file(fixture, "geomag", "testhash", "ingest", "0.0.0")
    assert len(df) == 8
    assert set(df["channel"]) == {"X", "Y", "Z", "G"}
    assert df["station_id"].unique().tolist() == ["KAK"]

    x_rows = df[df["channel"] == "X"]
    assert len(x_rows) == 2
    second_value = x_rows.iloc[1]["value"]
    assert pd.isna(second_value)
    assert x_rows.iloc[1]["quality_flags"]["is_missing"] is True
