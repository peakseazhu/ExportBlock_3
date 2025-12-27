# Module Deep Dive: scripts.finalize_event_package + make_event_bundle

Purpose / Reader / Takeaways:
- Purpose: document event packaging and bundling scripts.
- Reader: engineers preparing deliverables or debugging missing event artifacts.
- Takeaways: required artifacts and strict-mode behavior.

## Responsibilities
- Assemble event outputs into `outputs/events/<event_id>`.
- Generate event summary and artifacts manifest.
- Create final zip bundle for distribution.
- [EVIDENCE] scripts/finalize_event_package.py:L58-L134
- [EVIDENCE] scripts/make_event_bundle.py:L12-L27

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `--event_id` | Event to package/bundle. | - [EVIDENCE] scripts/finalize_event_package.py:L58-L66<br>- [EVIDENCE] scripts/make_event_bundle.py:L12-L19 |
| `--strict` | Fail if required artifacts missing. | - [EVIDENCE] scripts/finalize_event_package.py:L61-L127 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| `outputs/events/<event_id>/reports/artifacts_manifest.json` | Required/optional file checklist. | - [EVIDENCE] scripts/finalize_event_package.py:L95-L114 |
| `outputs/events/<event_id>/reports/event_summary.md` | Rendered event summary. | - [EVIDENCE] scripts/finalize_event_package.py:L92-L111 |
| `outputs/events/<event_id>/DONE` or `FAIL` | Completion markers. | - [EVIDENCE] scripts/finalize_event_package.py:L116-L134 |
| `outputs/events/<event_id>/event_bundle.zip` | Zip bundle of event directory. | - [EVIDENCE] scripts/make_event_bundle.py:L23-L27 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `_build_manifest` | Builds required/optional file checklist. | - [EVIDENCE] scripts/finalize_event_package.py:L31-L55 |
| `render_event_summary` | Produces event summary report. | - [EVIDENCE] scripts/finalize_event_package.py:L92-L94 |

## Error Handling / Edge Cases
- Strict mode: missing required files -> FAIL, exit code 1.
  - [EVIDENCE] scripts/finalize_event_package.py:L116-L127
- If event directory missing, `make_event_bundle.py` raises FileNotFoundError.
  - [EVIDENCE] scripts/make_event_bundle.py:L17-L20

## Verification
- Artifacts manifest includes completeness ratio and per-file stats.
  - [EVIDENCE] outputs/events/eq_20200912_024411/reports/artifacts_manifest.json:L1-L103
