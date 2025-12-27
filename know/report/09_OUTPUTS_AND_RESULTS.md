# 09 Outputs and Results

Purpose / Reader / Takeaways:
- Purpose: catalog output artifacts and provide sample outputs from this workspace.
- Reader: reviewers validating run completeness and output semantics.
- Takeaways: where outputs live and what each file contains.

## Output Directory Catalog
Canonical output layout is defined in `OutputPaths`.
- [EVIDENCE] src/store/paths.py:L6-L35

| Path | Description | Evidence |
| --- | --- | --- |
| `outputs/manifests/` | Run manifest JSON files. | - [EVIDENCE] src/pipeline/stages.py:L18-L27 |
| `outputs/ingest/` | Ingest parquet and cached files. | - [EVIDENCE] src/pipeline/ingest.py:L65-L203 |
| `outputs/raw/index/` | Raw index datasets by source. | - [EVIDENCE] src/pipeline/raw.py:L54-L123 |
| `outputs/raw/vlf_catalog.parquet` | VLF catalog index. | - [EVIDENCE] src/pipeline/ingest.py:L180-L183 |
| `outputs/raw/vlf/` | VLF Zarr spectrogram cubes. | - [EVIDENCE] src/pipeline/ingest.py:L138-L151 |
| `outputs/standard/source=<source>/` | Standardized parquet datasets. | - [EVIDENCE] src/pipeline/standard.py:L1016-L1029 |
| `outputs/linked/<event_id>/` | Event-aligned dataset + summary. | - [EVIDENCE] src/pipeline/link.py:L90-L135 |
| `outputs/features/<event_id>/` | Features + anomaly/association outputs. | - [EVIDENCE] src/pipeline/features.py:L135-L150<br>- [EVIDENCE] src/pipeline/model.py:L224-L293 |
| `outputs/models/` | Rulebook YAML with anomaly thresholds. | - [EVIDENCE] src/pipeline/model.py:L287-L290 |
| `outputs/plots/html/` + `outputs/plots/spec/` | Plotly HTML + JSON specs. | - [EVIDENCE] src/pipeline/plots.py:L16-L21 |
| `outputs/reports/` | DQ + runtime reports. | - [EVIDENCE] src/dq/reporting.py:L40-L43
| `outputs/events/<event_id>/` | Final event package + bundle. | - [EVIDENCE] scripts/finalize_event_package.py:L58-L134 |

## Sample Output Snapshots (from this workspace)
### Runtime Report
- `outputs/reports/runtime_report.json` includes total duration + per-stage timing.
- [EVIDENCE] outputs/reports/runtime_report.json:L1-L62

### Ingest DQ
- Geomag and AEF DQ with rows, time ranges, missing rates.
- [EVIDENCE] outputs/reports/dq_ingest_iaga.json:L1-L19

### Raw Index DQ
- Counts of files/traces/stations per source.
- [EVIDENCE] outputs/reports/dq_raw.json:L1-L27

### Standard DQ
- Missing/outlier rates and time ranges per source.
- [EVIDENCE] outputs/reports/dq_standard.json:L1-L37

### Spatial DQ
- Station count and index type.
- [EVIDENCE] outputs/reports/dq_spatial.json:L1-L5

### Linked Summary (event example)
- `outputs/linked/eq_20200912_024411/summary.json` shows event window coverage.
- [EVIDENCE] outputs/linked/eq_20200912_024411/summary.json:L1-L17

### Features Summary (event example)
- `outputs/features/eq_20200912_024411/summary.json` lists feature rows and sources.
- [EVIDENCE] outputs/features/eq_20200912_024411/summary.json:L1-L10

### Association Summary (event example)
- `outputs/features/eq_20200912_024411/association.json` includes association flags.
- [EVIDENCE] outputs/features/eq_20200912_024411/association.json:L1-L13

### Event Package Manifest
- `outputs/events/eq_20200912_024411/reports/artifacts_manifest.json` lists required and optional artifacts.
- [EVIDENCE] outputs/events/eq_20200912_024411/reports/artifacts_manifest.json:L1-L103

## Output Field Notes
- Standard long-table outputs include base columns defined in `src/constants.py`.
  - [EVIDENCE] src/constants.py:L3-L16
- `quality_flags` is a JSON-encoded dict in parquet storage.
  - [EVIDENCE] src/store/parquet.py:L18-L24

## Visualization Outputs
Plotly specs and HTML are written for aligned timeseries, station map, filter effect, and VLF spectrogram.
- [EVIDENCE] src/pipeline/plots.py:L43-L137
- [EVIDENCE] outputs/reports/dq_plots.json:L1-L6
