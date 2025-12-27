# Module Deep Dive: pipeline runner + stages

Purpose / Reader / Takeaways:
- Purpose: explain how stages are ordered and dispatched.
- Reader: developers adding/removing stages or debugging orchestration.
- Takeaways: stage order enforcement and timing output.

## Responsibilities
- Enforce strict stage order and dispatch stage functions.
- Collect per-stage timing records for runtime reports.
- [EVIDENCE] src/pipeline/runner.py:L11-L82

## Inputs
| Input | Source | Notes | Evidence |
| --- | --- | --- | --- |
| `stages` | CLI (`scripts/pipeline_run.py`) | Comma-separated stage list. | - [EVIDENCE] scripts/pipeline_run.py:L22-L73 |
| `base_dir`, `config`, `output_paths`, `run_id`, `params_hash`, `strict`, `event_id` | CLI runner | Passed through to each stage function. | - [EVIDENCE] src/pipeline/runner.py:L47-L71 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| Timing list | Each stage has `stage`, `start_utc`, `end_utc`, `duration_s`. | - [EVIDENCE] src/pipeline/runner.py:L58-L81 |
| Stage dispatch | `STAGE_FUNCS` maps stage name to callable. | - [EVIDENCE] src/pipeline/runner.py:L23-L33 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `_validate_stage_order` | Ensures list follows `STAGE_ORDER`. | - [EVIDENCE] src/pipeline/runner.py:L36-L44 |
| `run_stages` | Dispatch loop with timing. | - [EVIDENCE] src/pipeline/runner.py:L47-L82 |
| `run_manifest` | Adapter that calls manifest builder. | - [EVIDENCE] src/pipeline/stages.py:L18-L27 |

## Error Handling / Edge Cases
- Unknown stage or out-of-order stage raises `ValueError`.
  - [EVIDENCE] src/pipeline/runner.py:L36-L44

## Performance Notes
- Stage timing uses `time.perf_counter()` and records elapsed duration.
  - [EVIDENCE] src/pipeline/runner.py:L61-L80

## Verification
- End-to-end run writes `outputs/reports/runtime_report.json` with stage timing list.
  - [EVIDENCE] scripts/pipeline_run.py:L61-L83
  - [EVIDENCE] outputs/reports/runtime_report.json:L1-L62
