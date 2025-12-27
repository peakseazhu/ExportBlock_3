# Module Deep Dive: io.seismic

Purpose / Reader / Takeaways:
- Purpose: document MiniSEED reading and StationXML metadata handling.
- Reader: developers working on seismic data ingestion or raw queries.
- Takeaways: station_id format, metadata join, and windowed reads.

## Responsibilities
- Extract trace metadata from MiniSEED files.
- Load StationXML and enrich traces with lat/lon/elev.
- Serve windowed waveform samples for raw API queries.
- [EVIDENCE] src/io/seismic.py:L12-L158

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| MiniSEED files | Parsed with ObsPy `read`. | - [EVIDENCE] src/io/seismic.py:L33-L35 |
| StationXML | Parsed with ObsPy `read_inventory`. | - [EVIDENCE] src/io/seismic.py:L19-L27 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| Metadata DataFrame | Includes station_id, start/end time, sampling_rate, file_path. | - [EVIDENCE] src/io/seismic.py:L30-L49 |
| Windowed samples | Rows with `ts_ms`, `station_id`, `value`, and lat/lon/elev. | - [EVIDENCE] src/io/seismic.py:L53-L104 |
| Station match report | `matched_ratio`, `trace_count`, `unmatched_keys_topN`. | - [EVIDENCE] src/io/seismic.py:L107-L157 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `load_station_metadata` | Build StationXML metadata map. | - [EVIDENCE] src/io/seismic.py:L19-L27 |
| `extract_trace_metadata` | Extract metadata from MiniSEED traces. | - [EVIDENCE] src/io/seismic.py:L30-L50 |
| `read_mseed_window` | Windowed waveform sampling for API. | - [EVIDENCE] src/io/seismic.py:L53-L104 |
| `join_station_metadata` | Join metadata and compute match stats. | - [EVIDENCE] src/io/seismic.py:L107-L157 |

## Error Handling / Edge Cases
- `read_mseed_window` skips empty traces and stops when limit reached.
  - [EVIDENCE] src/io/seismic.py:L74-L103
- If no traces provided, `join_station_metadata` returns empty report.
  - [EVIDENCE] src/io/seismic.py:L110-L112

## Performance Notes
- Windowed read uses downsampling (`step`) when `limit` is set.
  - [EVIDENCE] src/io/seismic.py:L77-L83

## Verification
- Unit test validates StationXML join and coordinate enrichment.
  - [EVIDENCE] tests/test_seismic_stationxml.py:L11-L52
