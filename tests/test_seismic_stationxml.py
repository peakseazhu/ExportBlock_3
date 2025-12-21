from pathlib import Path

import numpy as np
import pytest
from obspy import Stream, Trace, UTCDateTime
from obspy.core.inventory import Channel, Inventory, Network, Site, Station

from src.io.seismic import extract_trace_metadata, join_station_metadata, load_station_metadata


@pytest.mark.unit
def test_stationxml_join(tmp_path: Path):
    data = np.random.randn(1000).astype("float32")
    trace = Trace(data=data)
    trace.stats.network = "XX"
    trace.stats.station = "AAA"
    trace.stats.location = ""
    trace.stats.channel = "BHZ"
    trace.stats.starttime = UTCDateTime(2020, 1, 1)
    stream = Stream([trace])

    mseed_path = tmp_path / "test.mseed"
    stream.write(str(mseed_path), format="MSEED")

    channel = Channel(
        code="BHZ",
        location_code="",
        latitude=10.0,
        longitude=20.0,
        elevation=0.5,
        depth=0.0,
        sample_rate=trace.stats.sampling_rate,
    )
    station = Station(
        code="AAA",
        latitude=10.0,
        longitude=20.0,
        elevation=0.5,
        site=Site(name="Test"),
        channels=[channel],
    )
    network = Network(code="XX", stations=[station])
    inventory = Inventory(networks=[network], source="pytest")
    stationxml_path = tmp_path / "stations.xml"
    inventory.write(str(stationxml_path), format="STATIONXML")

    traces = extract_trace_metadata([mseed_path])
    meta = load_station_metadata(stationxml_path)
    joined, report = join_station_metadata(traces, meta)

    assert report["matched_ratio"] == 1.0
    assert joined.iloc[0]["lat"] == 10.0
