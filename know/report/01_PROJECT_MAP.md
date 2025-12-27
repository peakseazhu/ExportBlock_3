# 01 Project Map

Purpose / Reader / Takeaways:
- Purpose: map the repository structure, entry points, and key artifacts so a new reader can navigate the project.
- Reader: engineers or reviewers who need to locate code, configs, data, and outputs quickly.
- Takeaways: where the pipeline lives, how to run it, and what artifacts are produced.

## Repo Tree (depth 3)
Tree snapshot (depth=3) is stored at `know/report/dir_tree_depth3.txt` and embedded below.
- [EVIDENCE] know/report/dir_tree_depth3.txt:L1-L153

```text
D:\ExportBlock-3
|-- configs
|   |-- default.yaml
|   `-- demo.yaml
|-- docs
|   |-- api.md
|   |-- config_reference.md
|   |-- data_dictionary.md
|   `-- task_map.md
|-- fixtures
|   `-- iaga_sample.min
|-- know
|   `-- report
|       |-- 01_PROJECT_MAP.md
|       |-- dir_tree_depth3.txt
|       `-- INDEX.md
|-- outputs
|   |-- events
|   |   `-- eq_20200912_024411
|   |-- features
|   |   `-- eq_20200912_024411
|   |-- ingest
|   |   |-- aef
|   |   |-- geomag
|   |   |-- seismic
|   |   |-- seismic_files
|   |   `-- seismic_sac
|   |-- linked
|   |   `-- eq_20200912_024411
|   |-- manifests
|   |   `-- run_20251226_064619.json
|   |-- models
|   |   `-- rulebook.yaml
|   |-- plots
|   |   |-- html
|   |   `-- spec
|   |-- raw
|   |   |-- index
|   |   |-- vlf
|   |   `-- vlf_catalog.parquet
|   |-- reports
|   |   |-- spatial_index
|   |   |-- compression.json
|   |   |-- compression_stats.json
|   |   |-- config_snapshot.yaml
|   |   |-- dq_ingest_iaga.json
|   |   |-- dq_ingest_mseed.json
|   |   |-- dq_ingest_vlf.json
|   |   |-- dq_plots.json
|   |   |-- dq_raw.json
|   |   |-- dq_spatial.json
|   |   |-- dq_standard.json
|   |   |-- filter_effect.json
|   |   |-- runtime_report.json
|   |   `-- station_match.json
|   `-- standard
|       |-- source=aef
|       |-- source=geomag
|       |-- source=seismic
|       `-- source=vlf
|-- scripts
|   |-- __init__.py
|   |-- finalize_event_package.py
|   |-- make_event_bundle.py
|   |-- pipeline_run.py
|   `-- render_event_summary.py
|-- src
|   |-- api
|   |   |-- __init__.py
|   |   `-- app.py
|   |-- dq
|   |   |-- __init__.py
|   |   `-- reporting.py
|   |-- io
|   |   |-- __init__.py
|   |   |-- iaga2002.py
|   |   |-- seismic.py
|   |   `-- vlf.py
|   |-- pipeline
|   |   |-- __init__.py
|   |   |-- features.py
|   |   |-- ingest.py
|   |   |-- link.py
|   |   |-- manifest.py
|   |   |-- model.py
|   |   |-- plots.py
|   |   |-- raw.py
|   |   |-- runner.py
|   |   |-- spatial.py
|   |   |-- stages.py
|   |   `-- standard.py
|   |-- plots
|   |   `-- __init__.py
|   |-- store
|   |   |-- __init__.py
|   |   |-- parquet.py
|   |   |-- paths.py
|   |   `-- zarr_utils.py
|   |-- __init__.py
|   |-- config.py
|   |-- constants.py
|   `-- utils.py
|-- templates
|   |-- event_summary_template_v3.md
|   |-- ui_event.html
|   `-- ui_index.html
|-- tests
|   |-- conftest.py
|   |-- test_anomaly_model.py
|   |-- test_api_smoke.py
|   |-- test_event_summary.py
|   |-- test_iaga_parser.py
|   |-- test_parquet_batch.py
|   |-- test_seismic_stationxml.py
|   |-- test_spatial_index.py
|   `-- test_vlf_reader.py
|-- 地磁
|   |-- kak20200901psec.sec
|   |-- kny20200901psec.sec
|   `-- mmb20200901psec.sec
|-- 地震波
|   |-- ERM.mseed
|   |-- ERM.sac
|   |-- get_data.py
|   |-- JKA.mseed
|   |-- JKA.sac
|   |-- JMM.mseed
|   |-- JMM.sac
|   |-- JSD.mseed
|   |-- JSD.sac
|   |-- JTM.mseed
|   |-- JTM.sac
|   |-- JYT.mseed
|   |-- JYT.sac
|   `-- stations_inventory.xml
|-- 大气电磁信号
|   |-- 大气电场
|   |   `-- kak202001-202010daef.min
|   `-- 电磁波动vlf
|       `-- vlf
|-- .gitignore
|-- .pre-commit-config.yaml
|-- environment.yml
|-- plan_final_revised_v9.md
|-- project_task_list.csv
|-- pytest.ini
|-- README.md
|-- requirements.txt
|-- translated_readme.md
|-- 数据源格式.md
|-- 方祎昌综合课程设计报告.docx
|-- 综合课程设计报告模板.doc
`-- 题目内容.md
```

Raw data directories at repo root use non-ASCII names and are referenced by default configs.
- [EVIDENCE] README.md:L7-L16
- [EVIDENCE] configs/default.yaml:L4-L28

## Directory Responsibilities (Top-Level)
| Directory | Responsibility | Evidence |
| --- | --- | --- |
| `configs/` | Runtime configuration for full and demo runs. | - [EVIDENCE] configs/default.yaml:L1-L56 |
| `docs/` | Reference docs (API, config, data dictionary, task map). | - [EVIDENCE] know/report/dir_tree_depth3.txt:L5-L9 |
| `fixtures/` | Sample input fixture file(s). | - [EVIDENCE] know/report/dir_tree_depth3.txt:L10-L11 |
| `know/` | Knowledge base output for this task. | - [EVIDENCE] know/report/dir_tree_depth3.txt:L12-L16 |
| `outputs/` | Generated pipeline outputs (manifests, raw/standard/linked/features, reports, plots, events). | - [EVIDENCE] know/report/dir_tree_depth3.txt:L17-L60 |
| `scripts/` | CLI entry points to run pipeline and packaging/report scripts. | - [EVIDENCE] know/report/dir_tree_depth3.txt:L61-L66 |
| `src/` | Application code: pipeline, IO, API, storage, DQ. | - [EVIDENCE] know/report/dir_tree_depth3.txt:L67-L102 |
| `templates/` | HTML/Markdown templates for UI and event summary. | - [EVIDENCE] know/report/dir_tree_depth3.txt:L103-L106 |
| `tests/` | Pytest suites validating core features. | - [EVIDENCE] know/report/dir_tree_depth3.txt:L107-L116 |
| `地磁/`, `地震波/`, `大气电磁信号/` | Source data roots for geomag, seismic, and AEF/VLF data. | - [EVIDENCE] README.md:L7-L16 |

## Core Pipeline Stages -> Modules
Stage order is documented and enforced in code.
- [EVIDENCE] README.md:L54-L71
- [EVIDENCE] src/pipeline/runner.py:L11-L43

| Stage | Module | Role (short) | Evidence |
| --- | --- | --- | --- |
| manifest | `src/pipeline/manifest.py` | Scan files and record manifest metadata. | - [EVIDENCE] README.md:L62-L63<br>- [EVIDENCE] know/report/dir_tree_depth3.txt:L79-L91 |
| ingest | `src/pipeline/ingest.py` | Parse raw files into structured tables (no event filtering). | - [EVIDENCE] README.md:L64-L65<br>- [EVIDENCE] know/report/dir_tree_depth3.txt:L79-L91 |
| raw | `src/pipeline/raw.py` | Build raw index for original files to support `/raw/query`. | - [EVIDENCE] README.md:L65-L65<br>- [EVIDENCE] know/report/dir_tree_depth3.txt:L79-L91 |
| standard | `src/pipeline/standard.py` | Per-source cleaning + standardized series. | - [EVIDENCE] README.md:L66-L66<br>- [EVIDENCE] know/report/dir_tree_depth3.txt:L79-L91 |
| spatial | `src/pipeline/spatial.py` | Build station index and spatial DQ. | - [EVIDENCE] README.md:L67-L67<br>- [EVIDENCE] know/report/dir_tree_depth3.txt:L79-L91 |
| link | `src/pipeline/link.py` | Event window + spatial join into linked dataset. | - [EVIDENCE] README.md:L68-L68<br>- [EVIDENCE] know/report/dir_tree_depth3.txt:L79-L91 |
| features | `src/pipeline/features.py` | Extract stats + signal features. | - [EVIDENCE] README.md:L69-L69<br>- [EVIDENCE] know/report/dir_tree_depth3.txt:L79-L91 |
| model | `src/pipeline/model.py` | Score anomalies with z-score thresholds. | - [EVIDENCE] README.md:L70-L70<br>- [EVIDENCE] know/report/dir_tree_depth3.txt:L79-L91 |
| plots | `src/pipeline/plots.py` | Generate Plotly figures for UI. | - [EVIDENCE] README.md:L71-L71<br>- [EVIDENCE] know/report/dir_tree_depth3.txt:L79-L91 |

## Entry Points & Run Commands
| Entry | Purpose | Evidence |
| --- | --- | --- |
| `python scripts/pipeline_run.py --stages ... --config ... --event_id ...` | Run pipeline stages (full or demo). | - [EVIDENCE] README.md:L73-L82<br>- [EVIDENCE] scripts/pipeline_run.py:L22-L83 |
| `python scripts/pipeline_run.py --list-stages` | List valid stages (enforced order). | - [EVIDENCE] scripts/pipeline_run.py:L22-L33<br>- [EVIDENCE] src/pipeline/runner.py:L11-L43 |
| `python scripts/finalize_event_package.py --event_id <id> --strict` | Assemble event package with required artifacts. | - [EVIDENCE] README.md:L94-L103<br>- [EVIDENCE] scripts/finalize_event_package.py:L58-L114 |
| `python scripts/make_event_bundle.py --event_id <id>` | Zip finalized event bundle. | - [EVIDENCE] README.md:L94-L103<br>- [EVIDENCE] scripts/make_event_bundle.py:L12-L27 |
| `python scripts/render_event_summary.py --event_id <id> --format md|html|both` | Render event summary report. | - [EVIDENCE] scripts/render_event_summary.py:L129-L134 |
| `uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000` | Start FastAPI server + UI. | - [EVIDENCE] README.md:L131-L137<br>- [EVIDENCE] src/api/app.py:L20-L26 |
| `pytest` | Run test suite. | - [EVIDENCE] README.md:L168-L171 |

## Dependencies & Runtime Environment
- Conda environment uses Python 3.11 and installs `requirements.txt`.
  - [EVIDENCE] environment.yml:L1-L9
- Key runtime libraries include pandas, numpy, pyarrow, fastapi, uvicorn, plotly, obspy, zarr.
  - [EVIDENCE] requirements.txt:L1-L20

## Key Files (10-20)
| File | Why it matters | Evidence |
| --- | --- | --- |
| `README.md` | Primary run instructions, pipeline order, outputs, API usage. | - [EVIDENCE] README.md:L1-L137 |
| `plan_final_revised_v9.md` | Design/specification document for pipeline and deliverables. | - [EVIDENCE] plan_final_revised_v9.md:L1-L15 |
| `configs/default.yaml` | Full-run default configuration (paths, events, preprocess, outputs). | - [EVIDENCE] configs/default.yaml:L1-L56 |
| `configs/demo.yaml` | Demo configuration with reduced limits and demo event. | - [EVIDENCE] configs/demo.yaml:L1-L55 |
| `scripts/pipeline_run.py` | CLI orchestration, config snapshot, runtime report. | - [EVIDENCE] scripts/pipeline_run.py:L22-L83 |
| `src/pipeline/runner.py` | Stage order + enforcement logic. | - [EVIDENCE] src/pipeline/runner.py:L11-L43 |
| `src/pipeline/stages.py` | Stage-to-function wiring. | - [EVIDENCE] src/pipeline/stages.py:L1-L33 |
| `src/store/paths.py` | Output directory layout definition. | - [EVIDENCE] src/store/paths.py:L6-L35 |
| `src/api/app.py` | FastAPI application + OUTPUT_ROOT mount. | - [EVIDENCE] src/api/app.py:L20-L26 |
| `scripts/finalize_event_package.py` | Finalize event package + artifacts manifest. | - [EVIDENCE] scripts/finalize_event_package.py:L58-L114 |
| `scripts/make_event_bundle.py` | Bundle event outputs into zip. | - [EVIDENCE] scripts/make_event_bundle.py:L12-L27 |
| `scripts/render_event_summary.py` | Build event summary report from outputs + templates. | - [EVIDENCE] scripts/render_event_summary.py:L45-L120 |
| `docs/config_reference.md` | Configuration dictionary reference. | - [EVIDENCE] docs/config_reference.md:L1-L7 |
| `docs/data_dictionary.md` | Data schema dictionary (raw/standard/linked/features). | - [EVIDENCE] docs/data_dictionary.md:L1-L15 |
| `docs/api.md` | API endpoint reference. | - [EVIDENCE] docs/api.md:L1-L16 |
| `docs/task_map.md` | TaskID to plan section mapping for acceptance tracking. | - [EVIDENCE] docs/task_map.md:L1-L13 |

## Outputs & Artifacts (Workspace Snapshot)
- Outputs are generated under `outputs/` and should not be committed by default.
  - [EVIDENCE] README.md:L174-L177
- Output subdirectories match the code-defined layout (manifests/ingest/raw/standard/linked/features/plots/reports/events).
  - [EVIDENCE] src/store/paths.py:L6-L35
- Example run timing report exists at `outputs/reports/runtime_report.json` with per-stage timings.
  - [EVIDENCE] outputs/reports/runtime_report.json:L1-L62
  - [EVIDENCE] know/report/dir_tree_depth3.txt:L41-L55
- Data quality and processing reports (`dq_*`, `station_match.json`, `filter_effect.json`) are present under `outputs/reports/`.
  - [EVIDENCE] know/report/dir_tree_depth3.txt:L41-L55
- Event-scoped outputs exist under `outputs/events/<event_id>` and `outputs/linked/<event_id>` / `outputs/features/<event_id>`.
  - [EVIDENCE] know/report/dir_tree_depth3.txt:L17-L28
