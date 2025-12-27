# Module Deep Dive: pipeline.spatial

Purpose / Reader / Takeaways:
- Purpose: describe spatial indexing and distance filtering utilities.
- Reader: developers working on station geo filtering.
- Takeaways: bruteforce haversine index and output reports.

## Responsibilities
- Compute haversine distances and query stations within radius.
- Build station index from ingest seismic metadata.
- Emit spatial DQ report.
- [EVIDENCE] src/pipeline/spatial.py:L14-L66

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `outputs/ingest/seismic` | Source of station lat/lon/elev. | - [EVIDENCE] src/pipeline/spatial.py:L50-L55 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| `outputs/reports/spatial_index` | Parquet station index. | - [EVIDENCE] src/pipeline/spatial.py:L61-L62 |
| `outputs/reports/dq_spatial.json` | DQ report with station count + index type. | - [EVIDENCE] src/pipeline/spatial.py:L62-L66 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `haversine_km` | Computes great-circle distance. | - [EVIDENCE] src/pipeline/spatial.py:L14-L22 |
| `SpatialIndex.query_radius` | Brute-force radius filter. | - [EVIDENCE] src/pipeline/spatial.py:L25-L37 |
| `run_spatial` | Builds station index and report. | - [EVIDENCE] src/pipeline/spatial.py:L40-L66 |

## Error Handling / Edge Cases
- If no stations are available, an empty DataFrame is written and station_count=0.
  - [EVIDENCE] src/pipeline/spatial.py:L56-L66

## Performance Notes
- Index type is brute-force (no spatial tree). Complexity is O(N) per query.
  - [EVIDENCE] src/pipeline/spatial.py:L25-L37
  - [EVIDENCE] outputs/reports/dq_spatial.json:L1-L5

## Verification
- Check `outputs/reports/dq_spatial.json` for station_count and index_type.
  - [EVIDENCE] outputs/reports/dq_spatial.json:L1-L5
