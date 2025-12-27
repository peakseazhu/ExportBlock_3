# 00 Quickstart

Purpose / Reader / Takeaways:
- Purpose: show the minimal, reproducible steps to run the pipeline and verify outputs.
- Reader: new user who needs a working run and concrete acceptance checks.
- Takeaways: required data layout, commands, and expected artifacts.

## 0) Preconditions (data layout)
The pipeline expects data folders at the repo root with these names and formats.
- [EVIDENCE] README.md:L7-L22

Required roots (names must match config defaults):
- `地磁/` for IAGA2002 geomagnetic files (`*.sec`, optionally `*.min`).
- `地震波/` for MiniSEED/SAC + StationXML.
- `大气电磁信号/大气电场/` for AEF IAGA2002 minute files.
- `大气电磁信号/电磁波动vlf/` for VLF CDF files.
- [EVIDENCE] README.md:L11-L22
- [EVIDENCE] configs/default.yaml:L4-L28

## 1) Environment setup
Option A (conda):
```bash
conda env create -f environment.yml
conda activate exportblock-3
```
- [EVIDENCE] README.md:L24-L31
- [EVIDENCE] environment.yml:L1-L9

Option B (pip):
```bash
pip install -r requirements.txt
```
- [EVIDENCE] README.md:L33-L37
- [EVIDENCE] requirements.txt:L1-L20

## 2) Run the pipeline (minimal demo)
Stage order is strict and enforced by the runner.
- [EVIDENCE] README.md:L54-L71
- [EVIDENCE] src/pipeline/runner.py:L11-L43

Demo run (small limits):
```bash
python scripts/pipeline_run.py --stages manifest,ingest,raw,standard,spatial,link,features,model,plots --config configs/demo.yaml --event_id eq_20200101_000000
```
- [EVIDENCE] README.md:L73-L82
- [EVIDENCE] scripts/pipeline_run.py:L22-L83

Full run (default config):
```bash
python scripts/pipeline_run.py --stages manifest,ingest,raw,standard,spatial,link,features,model,plots --config configs/default.yaml --event_id eq_20200912_024411
```
- [EVIDENCE] README.md:L73-L82
- [EVIDENCE] configs/default.yaml:L37-L44

List valid stages (sanity check):
```bash
python scripts/pipeline_run.py --list-stages
```
- [EVIDENCE] scripts/pipeline_run.py:L22-L33
- [EVIDENCE] src/pipeline/runner.py:L11-L43

## 3) Expected outputs and acceptance checks
Pipeline writes to the configured output root (default `outputs/`).
- [EVIDENCE] configs/default.yaml:L30-L32
- [EVIDENCE] scripts/pipeline_run.py:L42-L44
- [EVIDENCE] src/store/paths.py:L6-L35

Minimum acceptance checklist:
- `outputs/reports/config_snapshot.yaml` exists and includes run_id + params_hash.
  - [EVIDENCE] scripts/pipeline_run.py:L46-L59
- `outputs/reports/runtime_report.json` exists and lists per-stage durations.
  - [EVIDENCE] scripts/pipeline_run.py:L61-L83
  - [EVIDENCE] outputs/reports/runtime_report.json:L1-L62
- DQ reports exist for ingest/raw/standard/spatial.
  - [EVIDENCE] outputs/reports/dq_ingest_iaga.json:L1-L19
  - [EVIDENCE] outputs/reports/dq_ingest_mseed.json:L1-L6
  - [EVIDENCE] outputs/reports/dq_ingest_vlf.json:L1-L12
  - [EVIDENCE] outputs/reports/dq_raw.json:L1-L27
  - [EVIDENCE] outputs/reports/dq_standard.json:L1-L37
  - [EVIDENCE] outputs/reports/dq_spatial.json:L1-L5

Event-level artifacts (after `link`/`features`/`model`/`plots`):
- `outputs/linked/<event_id>/aligned.parquet`, `summary.json`, `event.json`.
- `outputs/features/<event_id>/features.parquet`, `anomaly.parquet`, `association.json`.
- `outputs/plots/html/<event_id>/plot_*.html`.
- [EVIDENCE] README.md:L108-L128
- [EVIDENCE] outputs/linked/eq_20200912_024411/summary.json:L1-L17
- [EVIDENCE] outputs/linked/eq_20200912_024411/event.json:L1-L17
- [EVIDENCE] outputs/features/eq_20200912_024411/summary.json:L1-L10
- [EVIDENCE] outputs/features/eq_20200912_024411/association.json:L1-L13

## 4) Finalize and bundle an event
Finalize a complete event package (with required artifacts), then build a zip bundle:
```bash
python scripts/finalize_event_package.py --event_id eq_20200912_024411 --strict
python scripts/make_event_bundle.py --event_id eq_20200912_024411
```
- [EVIDENCE] README.md:L94-L103
- [EVIDENCE] scripts/finalize_event_package.py:L58-L134
- [EVIDENCE] scripts/make_event_bundle.py:L12-L27

Success criteria (event package):
- `outputs/events/<event_id>/DONE` exists.
- `outputs/events/<event_id>/reports/artifacts_manifest.json` completeness_ratio_required is 1.0.
- [EVIDENCE] scripts/finalize_event_package.py:L116-L134
- [EVIDENCE] outputs/events/eq_20200912_024411/reports/artifacts_manifest.json:L1-L103

## 5) API / UI quick check
Start API (FastAPI):
```bash
uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000
```
- [EVIDENCE] README.md:L131-L137

Example sanity checks (from docs/README):
- `GET /health`
- `GET /raw/summary?source=geomag`
- `GET /standard/summary?source=geomag`
- `GET /events`
- [EVIDENCE] README.md:L139-L157
- [EVIDENCE] docs/api.md:L3-L33

Note: API uses `OUTPUT_ROOT` env var (defaults to `outputs/`).
- [EVIDENCE] src/api/app.py:L20-L26
