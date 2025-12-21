from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import cdflib

from src.io.vlf import read_vlf_cdf


@pytest.mark.unit
def test_read_vlf_cdf(monkeypatch):
    epoch = cdflib.cdfepoch.compute_tt2000(
        [[2020, 1, 1, 0, 0, 0, 0], [2020, 1, 1, 0, 0, 1, 0]]
    )
    freq = np.array([10.0, 100.0])
    ch1 = np.array([[1.0, -1.0], [2.0, 3.0]])
    ch2 = np.array([[4.0, 5.0], [6.0, -1.0]])

    class FakeCDF:
        def __init__(self, *_args, **_kwargs):
            pass

        def varget(self, name):
            if name == "epoch_vlf":
                return epoch
            if name == "freq_vlf":
                return freq
            if name == "ch1":
                return ch1
            if name == "ch2":
                return ch2
            raise KeyError(name)

        def varinq(self, _name):
            return {"PadValue": -1.0}

    monkeypatch.setattr(cdflib, "CDF", FakeCDF)

    data = read_vlf_cdf(Path("isee_vlf_mos_2020090100_v01.cdf"))
    assert data["station_id"] == "MOS"
    assert data["ch1"].shape == (2, 2)
    assert np.isnan(data["ch1"][0, 1])
