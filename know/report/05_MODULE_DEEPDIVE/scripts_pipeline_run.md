# Module Deep Dive: scripts.pipeline_run

Purpose / Reader / Takeaways:
- Purpose: document the CLI runner entry point.
- Reader: developers running the pipeline or integrating batch runs.
- Takeaways: CLI arguments, output artifacts, and timing report.

## Responsibilities
- Parse CLI args (`--config`, `--stages`, `--event_id`, `--strict`).
- Load config and compute params hash.
- Create output directories, write config snapshot, run stages, and record timing.
- [EVIDENCE] scripts/pipeline_run.py:L22-L83

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `--config` | Path to YAML config. | - [EVIDENCE] scripts/pipeline_run.py:L23-L27 |
| `--stages` | Comma-separated stage list. | - [EVIDENCE] scripts/pipeline_run.py:L25-L26 |
| `--event_id` | Event selector for link/features/model/plots. | - [EVIDENCE] scripts/pipeline_run.py:L26-L27 |
| `--strict` | Passed through to stages (not used by all). | - [EVIDENCE] scripts/pipeline_run.py:L27-L72 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| `outputs/reports/config_snapshot.yaml` | Run metadata + full config snapshot. | - [EVIDENCE] scripts/pipeline_run.py:L46-L59 |
| `outputs/reports/runtime_report.json` | Stage timing + total duration. | - [EVIDENCE] scripts/pipeline_run.py:L61-L83 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `_utc_run_id` | Generates run_id timestamp. | - [EVIDENCE] scripts/pipeline_run.py:L18-L19 |
| `main` | CLI flow and stage invocation. | - [EVIDENCE] scripts/pipeline_run.py:L22-L83 |

## Error Handling / Edge Cases
- `--list-stages` prints allowed stages and exits. | - [EVIDENCE] scripts/pipeline_run.py:L31-L33

## Verification
- After execution, `runtime_report.json` should list each stage duration.
  - [EVIDENCE] scripts/pipeline_run.py:L61-L83
  - [EVIDENCE] outputs/reports/runtime_report.json:L1-L62
