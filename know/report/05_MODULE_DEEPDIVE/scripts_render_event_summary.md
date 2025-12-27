# Module Deep Dive: scripts.render_event_summary

Purpose / Reader / Takeaways:
- Purpose: document how event summary reports are generated from outputs.
- Reader: developers modifying report template or adding new fields.
- Takeaways: inputs, template rendering, and output paths.

## Responsibilities
- Collect event metadata, DQ reports, and plots.
- Render Markdown summary using Jinja2 template.
- Optionally generate HTML version of the summary.
- [EVIDENCE] scripts/render_event_summary.py:L45-L125

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `outputs/events/<event_id>/event.json` | Event metadata. | - [EVIDENCE] scripts/render_event_summary.py:L54-L55 |
| `outputs/events/<event_id>/linked/summary.json` | Linked summary. | - [EVIDENCE] scripts/render_event_summary.py:L55-L56 |
| DQ + filter reports | `dq_event_link`, `dq_event_features`, `dq_plots`, `filter_effect`. | - [EVIDENCE] scripts/render_event_summary.py:L57-L68 |
| Plot HTML files | Used for report references. | - [EVIDENCE] scripts/render_event_summary.py:L73-L101 |
| Template | `templates/event_summary_template_v3.md`. | - [EVIDENCE] scripts/render_event_summary.py:L115-L117 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| `reports/event_summary.md` | Rendered Markdown summary. | - [EVIDENCE] scripts/render_event_summary.py:L119-L120 |
| `reports/event_summary.html` | HTML wrapper (optional). | - [EVIDENCE] scripts/render_event_summary.py:L122-L124 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `render_event_summary` | Main rendering entry. | - [EVIDENCE] scripts/render_event_summary.py:L45-L125 |
| `_format_top_anomalies` | Renders anomaly table. | - [EVIDENCE] scripts/render_event_summary.py:L25-L34 |

## Error Handling / Edge Cases
- If anomaly file is missing or empty, the report explicitly states it.
  - [EVIDENCE] scripts/render_event_summary.py:L25-L34
- Missing files fall back to empty/default JSON payloads.
  - [EVIDENCE] scripts/render_event_summary.py:L13-L16
  - [EVIDENCE] scripts/render_event_summary.py:L57-L68

## Verification
- Integration test validates that report content includes key sections.
  - [EVIDENCE] tests/test_event_summary.py:L10-L38
