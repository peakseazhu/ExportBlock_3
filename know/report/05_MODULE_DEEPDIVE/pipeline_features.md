# Module Deep Dive: pipeline.features

Purpose / Reader / Takeaways:
- Purpose: document feature extraction from linked event datasets.
- Reader: developers validating feature values or extending features.
- Takeaways: feature schema and event-specific outputs.

## Responsibilities
- Compute summary stats (mean/std/variance/min/max/rms/count) per source/station/channel.
- Add geomag gradient features and seismic arrival offset proxies.
- Write `features.parquet` plus summary/DQ JSON.
- [EVIDENCE] src/pipeline/features.py:L38-L150

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `outputs/linked/<event_id>/aligned.parquet` | Event-aligned long table. | - [EVIDENCE] src/pipeline/features.py:L51-L56 |
| `config.events` | Event metadata for origin time. | - [EVIDENCE] src/pipeline/features.py:L49-L51 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| `outputs/features/<event_id>/features.parquet` | Feature rows. | - [EVIDENCE] src/pipeline/features.py:L135-L143 |
| `outputs/features/<event_id>/summary.json` | Feature count and sources. | - [EVIDENCE] src/pipeline/features.py:L144-L149 |
| `outputs/features/<event_id>/dq_features.json` | Same payload as summary. | - [EVIDENCE] src/pipeline/features.py:L149-L150 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `_gradient_stats` | Computes mean/max absolute gradients (geomag). | - [EVIDENCE] src/pipeline/features.py:L14-L26 |
| `_arrival_offset_s` | Peak-based arrival offset from origin time. | - [EVIDENCE] src/pipeline/features.py:L29-L35 |
| `run_features` | Main feature extraction pipeline. | - [EVIDENCE] src/pipeline/features.py:L38-L150 |

## Error Handling / Edge Cases
- Missing aligned parquet raises `FileNotFoundError`.
  - [EVIDENCE] src/pipeline/features.py:L51-L55
- Empty aligned dataset yields empty features parquet with schema only.
  - [EVIDENCE] src/pipeline/features.py:L56-L143

## Performance Notes
- Feature extraction groups by `source, station_id, channel` and processes each group.
  - [EVIDENCE] src/pipeline/features.py:L62-L87

## Verification
- Summary file records feature rows and per-source counts.
  - [EVIDENCE] src/pipeline/features.py:L144-L149
  - [EVIDENCE] outputs/features/eq_20200912_024411/summary.json:L1-L10
