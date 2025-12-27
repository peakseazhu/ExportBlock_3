# 11 Glossary

Purpose / Reader / Takeaways:
- Purpose: define key terms, abbreviations, and fields used in the project.
- Reader: new contributors and reviewers.
- Takeaways: shared vocabulary with evidence references.

| Term | Definition | Evidence |
| --- | --- | --- |
| IAGA2002 | Text format used for geomag/AEF (`*.sec`/`*.min`) input files. | - [EVIDENCE] README.md:L18-L21 |
| Geomag | Geomagnetic data source parsed from IAGA2002 files. | - [EVIDENCE] README.md:L18-L20 |
| AEF | Atmospheric electric field data, IAGA2002 minute files. | - [EVIDENCE] README.md:L20-L21 |
| VLF | Very Low Frequency spectrogram data stored from CDF files. | - [EVIDENCE] README.md:L22-L22
| MiniSEED | Seismic waveform format used for ingestion. | - [EVIDENCE] README.md:L21-L22 |
| StationXML | FDSN station metadata used to enrich seismic coordinates. | - [EVIDENCE] README.md:L21-L22
| `ts_ms` | UTC epoch milliseconds timestamp column in long tables. | - [EVIDENCE] docs/data_dictionary.md:L4-L5 |
| `epoch_ns` | VLF epoch timestamps in nanoseconds. | - [EVIDENCE] docs/data_dictionary.md:L17-L20 |
| `source` | Data source identifier (`geomag|aef|seismic|vlf`). | - [EVIDENCE] docs/data_dictionary.md:L5-L6 |
| `station_id` | Station identifier (IAGA code or `NET.STA.LOC.CHAN`). | - [EVIDENCE] docs/data_dictionary.md:L6-L9 |
| `channel` | Data channel (e.g., `X/Y/Z/F`, `BHZ_rms`). | - [EVIDENCE] docs/data_dictionary.md:L9-L10 |
| `quality_flags` | JSON map of missing/outlier/filter flags. | - [EVIDENCE] docs/data_dictionary.md:L12-L12
| `proc_stage` | Processing stage label (ingest/raw/standard/linked/features/model/plots). | - [EVIDENCE] docs/data_dictionary.md:L13-L13 |
| `proc_version` | Pipeline version label stored in outputs. | - [EVIDENCE] docs/data_dictionary.md:L14-L14 |
| `params_hash` | Config hash stored for reproducibility. | - [EVIDENCE] docs/data_dictionary.md:L15-L15 |
| Raw | Indexed representation of original data for `/raw/query`. | - [EVIDENCE] README.md:L65-L66 |
| Standard | Cleaned and standardized outputs per source. | - [EVIDENCE] README.md:L66-L67 |
| Linked | Event-aligned dataset created by `link` stage. | - [EVIDENCE] README.md:L68-L69 |
| Features | Per-event statistics and derived features. | - [EVIDENCE] README.md:L69-L70 |
| Anomaly | Z-score-based deviations stored in `anomaly.parquet`. | - [EVIDENCE] src/pipeline/model.py:L224-L245 |
| Association | Cross-source change/correlation summary for an event. | - [EVIDENCE] src/pipeline/model.py:L79-L199 |
| DQ (Data Quality) | Standard report with rows/time/missing/outlier stats. | - [EVIDENCE] src/dq/reporting.py:L11-L37 |
| Zarr | Storage format used for VLF spectrogram cubes. | - [EVIDENCE] src/pipeline/ingest.py:L138-L151 |
| Parquet | Columnar storage format for long-table outputs. | - [EVIDENCE] src/store/parquet.py:L174-L217 |
