# Module Deep Dive: core config/constants/utils/dq

Purpose / Reader / Takeaways:
- Purpose: describe shared utilities and constants used across the pipeline.
- Reader: developers changing configuration or data quality reporting.
- Takeaways: config loading, params hashing, and DQ schema.

## Responsibilities
- Load YAML config and compute deterministic params hash.
- Resolve events by `event_id` with error checks.
- Define base column and quality flag keys.
- Provide utility helpers (ensure_dir, write_json).
- Generate DQ payloads with standard fields.
- [EVIDENCE] src/config.py:L9-L38
- [EVIDENCE] src/constants.py:L3-L31
- [EVIDENCE] src/utils.py:L8-L27
- [EVIDENCE] src/dq/reporting.py:L11-L43

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `load_config` | YAML config loader. | - [EVIDENCE] src/config.py:L9-L12 |
| `compute_params_hash` | Deterministic hash of config payload. | - [EVIDENCE] src/config.py:L24-L26 |
| `get_event` | Select event by id (or default). | - [EVIDENCE] src/config.py:L29-L38 |
| `write_json` | JSON write helper with UTF-8 and indentation. | - [EVIDENCE] src/utils.py:L24-L27 |
| `basic_stats` | Standard DQ statistics schema. | - [EVIDENCE] src/dq/reporting.py:L11-L37 |

## Error Handling / Edge Cases
- Missing events list or unknown `event_id` raises `ValueError`.
  - [EVIDENCE] src/config.py:L31-L38
- `basic_stats` returns null stats for empty DataFrame.
  - [EVIDENCE] src/dq/reporting.py:L11-L20

## Verification
- DQ reports include `generated_at_utc` timestamp.
  - [EVIDENCE] src/dq/reporting.py:L40-L43
  - [EVIDENCE] outputs/reports/dq_raw.json:L1-L3
