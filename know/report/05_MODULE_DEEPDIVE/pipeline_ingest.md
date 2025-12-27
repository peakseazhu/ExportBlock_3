# Module Deep Dive: pipeline.ingest

Purpose / Reader / Takeaways:
- Purpose: describe how raw data files are parsed into ingest-level storage.
- Reader: developers adding data sources or validating ingest outputs.
- Takeaways: ingest outputs, VLF Zarr layout, and DQ report generation.

## Responsibilities
- Parse IAGA2002 geomag/AEF files into parquet.
- Extract seismic trace metadata and join StationXML coordinates.
- Convert VLF CDF files into Zarr spectrogram cubes and catalog.
- Emit ingest DQ reports + station matching report.
- [EVIDENCE] src/pipeline/ingest.py:L45-L195

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `paths.geomag/aef/seismic/vlf` | Source roots and patterns. | - [EVIDENCE] src/pipeline/ingest.py:L59-L64 |
| `limits.max_files_per_source` | File scan cap. | - [EVIDENCE] src/pipeline/ingest.py:L55-L57 |
| `limits.max_rows_per_source` | Row cap after ingest. | - [EVIDENCE] src/pipeline/ingest.py:L57-L84 |
| `vlf.preview.*` | Max bins for preview images. | - [EVIDENCE] src/pipeline/ingest.py:L127-L129 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| `outputs/ingest/geomag` | Geomag parquet (long-table). | - [EVIDENCE] src/pipeline/ingest.py:L65-L75 |
| `outputs/ingest/aef` | AEF parquet (long-table). | - [EVIDENCE] src/pipeline/ingest.py:L77-L85 |
| `outputs/ingest/seismic` | Seismic trace metadata parquet. | - [EVIDENCE] src/pipeline/ingest.py:L88-L119 |
| `outputs/ingest/seismic_files` | Cache of mseed files for later stages. | - [EVIDENCE] src/pipeline/ingest.py:L94-L100 |
| `outputs/raw/vlf/<station>/<run>/spectrogram.zarr` | VLF spectrogram arrays. | - [EVIDENCE] src/pipeline/ingest.py:L138-L151 |
| `outputs/raw/vlf_catalog.parquet` | VLF catalog for indexing/queries. | - [EVIDENCE] src/pipeline/ingest.py:L180-L183 |
| `outputs/reports/dq_ingest_*.json` | DQ reports for ingest. | - [EVIDENCE] src/pipeline/ingest.py:L75-L86<br>- [EVIDENCE] src/pipeline/ingest.py:L118-L120<br>- [EVIDENCE] src/pipeline/ingest.py:L184-L194 |
| `outputs/reports/station_match.json` | StationXML join quality. | - [EVIDENCE] src/pipeline/ingest.py:L102-L120 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `run_ingest` | Orchestrates all ingest steps. | - [EVIDENCE] src/pipeline/ingest.py:L45-L203 |
| `_write_preview_png` | Generates log-scaled VLF preview image. | - [EVIDENCE] src/pipeline/ingest.py:L34-L42 |

## Error Handling / Edge Cases
- StationXML enrichment is optional; if missing or empty, a default report is written.
  - [EVIDENCE] src/pipeline/ingest.py:L102-L120
- Empty datasets produce empty DQ reports (rows=0, etc.).
  - [EVIDENCE] src/dq/reporting.py:L11-L37
- VLF gap report handles <2 samples by returning zeros.
  - [EVIDENCE] src/io/vlf.py:L49-L52

## Performance Notes
- Ingest concatenates dataframes in memory per source; large inputs may require limits.
  - [EVIDENCE] src/pipeline/ingest.py:L68-L84
- VLF ingest writes Zarr arrays for each file; I/O bound for large spectrograms.
  - [EVIDENCE] src/pipeline/ingest.py:L138-L165

## Verification
- DQ reports should exist under `outputs/reports/` with `generated_at_utc`.
  - [EVIDENCE] src/dq/reporting.py:L40-L43
  - [EVIDENCE] outputs/reports/dq_ingest_iaga.json:L1-L19
  - [EVIDENCE] outputs/reports/dq_ingest_vlf.json:L1-L12
