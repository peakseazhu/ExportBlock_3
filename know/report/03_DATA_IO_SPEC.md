# 03 Data I/O Spec

Purpose / Reader / Takeaways:
- Purpose: define the exact input/output formats, field meanings, units, time handling, and missing-data rules.
- Reader: engineers implementing new sources or validating outputs.
- Takeaways: canonical schemas and how raw data becomes standard/linked/features outputs.

## Canonical Long-Table Schema (Raw/Standard/Linked/Features)
Base columns are defined in code and documented in the data dictionary.
- [EVIDENCE] src/constants.py:L3-L16
- [EVIDENCE] docs/data_dictionary.md:L3-L15

| Field | Type | Meaning | Evidence |
| --- | --- | --- | --- |
| `ts_ms` | int64 | UTC epoch milliseconds for each sample/feature row. | - [EVIDENCE] src/io/iaga2002.py:L74-L76 |
| `source` | str | `geomag | aef | seismic | vlf`. | - [EVIDENCE] docs/data_dictionary.md:L5-L6 |
| `station_id` | str | IAGA code for geomag/AEF; `NET.STA.LOC.CHAN` for seismic. | - [EVIDENCE] docs/data_dictionary.md:L6-L9 |
| `channel` | str | Channel label (e.g., `X/Y/Z/F`, `BHZ_rms`). | - [EVIDENCE] docs/data_dictionary.md:L9-L10 |
| `value` | float | Primary value for the channel/feature. | - [EVIDENCE] docs/data_dictionary.md:L10-L10 |
| `lat/lon/elev` | float | Station coordinates (WGS84), may be NaN if unknown. | - [EVIDENCE] docs/data_dictionary.md:L11-L11 |
| `quality_flags` | json | Quality flags for missing/outliers/interpolation/filtering. | - [EVIDENCE] docs/data_dictionary.md:L12-L12 |
| `proc_stage` | str | `ingest|raw|standard|linked|features|model|plots`. | - [EVIDENCE] docs/data_dictionary.md:L13-L13 |
| `proc_version` | str | Pipeline version tag. | - [EVIDENCE] docs/data_dictionary.md:L14-L14 |
| `params_hash` | str | Config snapshot hash for reproducibility. | - [EVIDENCE] docs/data_dictionary.md:L15-L15 |

Quality flag keys are standardized in code.
- [EVIDENCE] src/constants.py:L18-L31

## Input Sources
### Geomag (IAGA2002)
- Files: `*.sec` and/or `*.min` per config `paths.geomag.*`.
  - [EVIDENCE] README.md:L18-L20
  - [EVIDENCE] configs/default.yaml:L4-L11
- Parsing: reads IAGA header for station_id/lat/lon/elev/reported and data columns after `DATE TIME`.
  - [EVIDENCE] src/io/iaga2002.py:L10-L24
  - [EVIDENCE] src/io/iaga2002.py:L28-L33
- Time: `DATE` + `TIME` are parsed to UTC and converted to `ts_ms`.
  - [EVIDENCE] src/io/iaga2002.py:L72-L76
- Missing values: sentinel values `>= 88888` are treated as missing with flags.
  - [EVIDENCE] src/io/iaga2002.py:L35-L39
  - [EVIDENCE] src/io/iaga2002.py:L88-L99

### AEF (IAGA2002 minute data)
- Files: `*.min` under AEF root in config.
  - [EVIDENCE] README.md:L20-L21
  - [EVIDENCE] configs/default.yaml:L12-L16
- Parsing is the same IAGA2002 path as geomag (shared reader).
  - [EVIDENCE] src/pipeline/ingest.py:L77-L86
  - [EVIDENCE] src/io/iaga2002.py:L64-L105

### Seismic (MiniSEED + StationXML)
- Files: MiniSEED (`*.seed`/`*.mseed`) + optional StationXML.
  - [EVIDENCE] README.md:L21-L22
  - [EVIDENCE] configs/default.yaml:L18-L24
- Trace metadata extraction uses ObsPy and yields `station_id = NET.STA.LOC.CHAN` plus start/end times.
  - [EVIDENCE] src/io/seismic.py:L30-L49
- StationXML (if provided) is used to enrich lat/lon/elev and compute match stats.
  - [EVIDENCE] src/io/seismic.py:L19-L27
  - [EVIDENCE] src/io/seismic.py:L107-L157

### VLF (CDF spectrogram product)
- Files: CDF `*.cdf` under VLF root.
  - [EVIDENCE] README.md:L22-L22
  - [EVIDENCE] configs/default.yaml:L25-L28
- Required variables: `epoch_vlf`, `freq_vlf`, `ch1`, `ch2`.
  - [EVIDENCE] src/io/vlf.py:L19-L25
- Converted outputs: `epoch_ns` (int64), `freq_hz`, `ch1`, `ch2` arrays; PadValue -> NaN.
  - [EVIDENCE] src/io/vlf.py:L26-L46
  - [EVIDENCE] src/io/vlf.py:L29-L37

## Output Layers
### Ingest Outputs
- Geomag/AEF: `outputs/ingest/<source>` parquet.
- Seismic: `outputs/ingest/seismic` metadata parquet; waveform cache in `outputs/ingest/seismic_files/`.
- VLF: Zarr cubes at `outputs/raw/vlf/<station>/<run>/spectrogram.zarr` plus `vlf_meta.json` and `vlf_gap_report.json`.
- [EVIDENCE] src/pipeline/ingest.py:L65-L203
- [EVIDENCE] src/store/paths.py:L6-L35

### Raw Index Outputs
- Raw index per source in `outputs/raw/index/source=<source>/...` with file paths and time bounds.
- VLF catalog at `outputs/raw/vlf_catalog.parquet`.
- [EVIDENCE] src/pipeline/raw.py:L54-L151
- [EVIDENCE] README.md:L116-L118

### Standard Outputs
- Standardized tables per source in `outputs/standard/source=<source>/...` (parquet, partitioned).
- Seismic standard rows are interval stats (`*_rms`, `*_mean_abs`).
- VLF standard rows are band-power and peak-frequency features.
- [EVIDENCE] src/pipeline/standard.py:L460-L556
- [EVIDENCE] src/pipeline/standard.py:L559-L745
- [EVIDENCE] README.md:L119-L119

### Linked Outputs
- Event-aligned long table: `outputs/linked/<event_id>/aligned.parquet`.
- `summary.json` includes event window, join coverage, source counts.
- `event.json` captures event metadata and alignment params.
- [EVIDENCE] src/pipeline/link.py:L90-L135
- [EVIDENCE] outputs/linked/eq_20200912_024411/summary.json:L1-L17
- [EVIDENCE] outputs/linked/eq_20200912_024411/event.json:L1-L17

### Features + Model Outputs
- `features.parquet` with per-group stats and derived features.
- `anomaly.parquet` for z-score anomalies; `association.json` for cross-source association summary.
- [EVIDENCE] src/pipeline/features.py:L60-L150
- [EVIDENCE] src/pipeline/model.py:L224-L293

### Plots + Reports
- Plotly HTML + JSON spec under `outputs/plots/html` and `outputs/plots/spec`.
- Data quality reports under `outputs/reports/*.json`.
- [EVIDENCE] src/pipeline/plots.py:L16-L140
- [EVIDENCE] src/dq/reporting.py:L11-L43

## Time Handling and Alignment
- `ts_ms` is always UTC milliseconds (from timestamps or sample indices).
  - [EVIDENCE] src/io/iaga2002.py:L72-L76
  - [EVIDENCE] src/io/seismic.py:L80-L88
- Event window is defined by `pre_hours`/`post_hours` around `origin_time_utc`.
  - [EVIDENCE] src/pipeline/link.py:L39-L44
- Alignment uses floor-to-interval: `ts_ms = (ts_ms // interval_ms) * interval_ms`.
  - [EVIDENCE] src/pipeline/link.py:L17-L18

## Missing Values and Quality Flags
- IAGA sentinel values (`>= 88888`) are treated as missing with `quality_flags`.
  - [EVIDENCE] src/io/iaga2002.py:L35-L39
  - [EVIDENCE] src/io/iaga2002.py:L88-L99
- VLF PadValue is converted to NaN before ingest.
  - [EVIDENCE] src/io/vlf.py:L29-L37
- Standard stage marks outliers and interpolations in `quality_flags` and sets outliers to NaN.
  - [EVIDENCE] src/pipeline/standard.py:L278-L309
- Quality flag fields are standardized in `src/constants.py`.
  - [EVIDENCE] src/constants.py:L18-L31

## Units and Coordinates
- Coordinates in canonical tables are WGS84 latitude/longitude (degrees) per data dictionary.
  - [EVIDENCE] docs/data_dictionary.md:L11-L11
- VLF spectrogram units are `V^2/Hz` (stored in `vlf_meta.json`).
  - [EVIDENCE] src/pipeline/ingest.py:L153-L163

## Data Quality Report Schema
`basic_stats()` defines the standard DQ fields used in ingest/standard reports.
- [EVIDENCE] src/dq/reporting.py:L11-L37

Example DQ report fields (from outputs):
- [EVIDENCE] outputs/reports/dq_ingest_iaga.json:L1-L19
- [EVIDENCE] outputs/reports/dq_standard.json:L1-L37
