# Module Deep Dive: pipeline.raw

Purpose / Reader / Takeaways:
- Purpose: explain how raw indexes are created for queryable access to original files.
- Reader: developers working on raw query behavior or indexes.
- Takeaways: raw index schema and outputs.

## Responsibilities
- Scan source files (geomag, aef) and compute time bounds via `scan_iaga_file`.
- Build raw index for seismic traces from ingest metadata.
- Attach VLF catalog entries as raw index.
- Emit DQ and compression stats reports.
- [EVIDENCE] src/pipeline/raw.py:L40-L160

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `paths.*` | Roots for geomag/aef data. | - [EVIDENCE] src/pipeline/raw.py:L56-L88 |
| `outputs/ingest/seismic` | Seismic trace metadata from ingest. | - [EVIDENCE] src/pipeline/raw.py:L104-L120 |
| `outputs/raw/vlf_catalog.parquet` | VLF catalog built during ingest. | - [EVIDENCE] src/pipeline/raw.py:L131-L145 |
| `limits.max_files_per_source` | Optional file cap. | - [EVIDENCE] src/pipeline/raw.py:L50-L52 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| `outputs/raw/index/source=<source>` | Partitioned parquet index per source. | - [EVIDENCE] src/pipeline/raw.py:L54-L123 |
| `outputs/reports/dq_raw.json` | Raw index stats per source. | - [EVIDENCE] src/pipeline/raw.py:L151-L151 |
| `outputs/reports/compression.json` | Size stats for each index. | - [EVIDENCE] src/pipeline/raw.py:L153-L160 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `run_raw` | Main entry for raw index building. | - [EVIDENCE] src/pipeline/raw.py:L40-L160 |
| `_collect_files` | Apply file patterns and cap. | - [EVIDENCE] src/pipeline/raw.py:L15-L23 |
| `_write_index` | Writes partitioned parquet index. | - [EVIDENCE] src/pipeline/raw.py:L33-L37 |

## Error Handling / Edge Cases
- If ingest outputs are missing or empty, corresponding index is skipped.
  - [EVIDENCE] src/pipeline/raw.py:L104-L130
- Missing VLF catalog results in no VLF index output.
  - [EVIDENCE] src/pipeline/raw.py:L131-L150

## Performance Notes
- Index writes remove existing output directory to avoid stale data.
  - [EVIDENCE] src/pipeline/raw.py:L33-L37
- File size stats are computed by walking output directories.
  - [EVIDENCE] src/pipeline/raw.py:L153-L159

## Verification
- Raw index DQ file exists and lists per-source counts.
  - [EVIDENCE] src/pipeline/raw.py:L151-L151
  - [EVIDENCE] outputs/reports/dq_raw.json:L1-L27
