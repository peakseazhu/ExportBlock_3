# 08 Verification and Tests

Purpose / Reader / Takeaways:
- Purpose: provide a verification checklist and current test coverage.
- Reader: engineers validating pipeline correctness and outputs.
- Takeaways: what is tested and how to run/accept results.

## Test Inventory (Pytest)
Markers are defined in `pytest.ini`.
- [EVIDENCE] pytest.ini:L1-L5

| Test | Scope | What it covers | Evidence |
| --- | --- | --- | --- |
| `tests/test_iaga_parser.py` | unit | IAGA parsing + sentinel missing flags. | - [EVIDENCE] tests/test_iaga_parser.py:L9-L21 |
| `tests/test_vlf_reader.py` | unit | VLF CDF reading + pad value handling. | - [EVIDENCE] tests/test_vlf_reader.py:L11-L43 |
| `tests/test_seismic_stationxml.py` | unit | StationXML join and coordinates. | - [EVIDENCE] tests/test_seismic_stationxml.py:L11-L52 |
| `tests/test_spatial_index.py` | unit | Spatial radius query logic. | - [EVIDENCE] tests/test_spatial_index.py:L7-L18 |
| `tests/test_parquet_batch.py` | unit | Parquet batch write/read + partitioning. | - [EVIDENCE] tests/test_parquet_batch.py:L8-L20 |
| `tests/test_event_summary.py` | integ | Event summary rendering and template content. | - [EVIDENCE] tests/test_event_summary.py:L10-L38 |
| `tests/test_anomaly_model.py` | integ | Anomaly scoring output creation. | - [EVIDENCE] tests/test_anomaly_model.py:L9-L31 |
| `tests/test_api_smoke.py` | smoke | FastAPI endpoints `/health`, `/raw/query`, `/standard/query`. | - [EVIDENCE] tests/test_api_smoke.py:L11-L81 |

## How to Run Tests
```bash
pytest
```
- [EVIDENCE] README.md:L168-L171

Run subsets:
```bash
pytest -m unit
pytest -m integ
pytest -m smoke
```
- [EVIDENCE] pytest.ini:L1-L5

## End-to-End Verification Checklist
Minimal pipeline verification (demo config):
```bash
python scripts/pipeline_run.py --stages manifest,ingest,raw,standard,spatial,link,features,model,plots --config configs/demo.yaml --event_id eq_20200101_000000
```
- [EVIDENCE] README.md:L73-L82

Acceptance checks:
- `outputs/reports/runtime_report.json` exists and lists all stages.
  - [EVIDENCE] scripts/pipeline_run.py:L61-L83
  - [EVIDENCE] outputs/reports/runtime_report.json:L1-L62
- DQ reports exist: `dq_ingest_*`, `dq_raw.json`, `dq_standard.json`, `dq_spatial.json`.
  - [EVIDENCE] outputs/reports/dq_ingest_iaga.json:L1-L19
  - [EVIDENCE] outputs/reports/dq_raw.json:L1-L27
  - [EVIDENCE] outputs/reports/dq_standard.json:L1-L37
  - [EVIDENCE] outputs/reports/dq_spatial.json:L1-L5
- Linked + features summaries exist for event id.
  - [EVIDENCE] outputs/linked/eq_20200912_024411/summary.json:L1-L17
  - [EVIDENCE] outputs/features/eq_20200912_024411/summary.json:L1-L10

## API Verification
Start API:
```bash
uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000
```
- [EVIDENCE] README.md:L133-L137

Verify:
- `GET /health` returns status 200.
- `GET /raw/summary?source=geomag` returns a time range.
- `GET /standard/summary?source=geomag` returns a time range.
- [EVIDENCE] docs/api.md:L3-L12

## Performance Verification
- Runtime report includes per-stage durations and total time.
  - [EVIDENCE] scripts/pipeline_run.py:L61-L83
  - [EVIDENCE] outputs/reports/runtime_report.json:L1-L62
- Use `outputs/reports/runtime_report.json` to track regressions across runs.
  - [EVIDENCE] outputs/reports/runtime_report.json:L1-L62
