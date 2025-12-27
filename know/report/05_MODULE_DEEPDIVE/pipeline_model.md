# Module Deep Dive: pipeline.model

Purpose / Reader / Takeaways:
- Purpose: document anomaly scoring and association logic.
- Reader: developers tuning thresholds or investigating anomaly outputs.
- Takeaways: z-score anomaly process and cross-source association results.

## Responsibilities
- Compute z-score anomalies on features and store top-N.
- Compute association signals (pre/post mean shift + cross-correlation with lag).
- Write anomaly/association parquet + rulebook YAML.
- [EVIDENCE] src/pipeline/model.py:L204-L293

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `outputs/features/<event_id>/features.parquet` | Feature rows for scoring. | - [EVIDENCE] src/pipeline/model.py:L215-L221 |
| `config.features.*` | Thresholds and association config. | - [EVIDENCE] src/pipeline/model.py:L16-L27<br>- [EVIDENCE] src/pipeline/model.py:L221-L223 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| `outputs/features/<event_id>/anomaly.parquet` | Ranked anomalies by z-score. | - [EVIDENCE] src/pipeline/model.py:L224-L245 |
| `outputs/features/<event_id>/association.json` | Association summary. | - [EVIDENCE] src/pipeline/model.py:L247-L286 |
| `outputs/features/<event_id>/association_changes.parquet` | Pre/post change metrics. | - [EVIDENCE] src/pipeline/model.py:L249-L267 |
| `outputs/features/<event_id>/association_similarity.parquet` | Cross-correlation results. | - [EVIDENCE] src/pipeline/model.py:L268-L284 |
| `outputs/models/rulebook.yaml` | Thresholds + params hash. | - [EVIDENCE] src/pipeline/model.py:L287-L290 |
| `outputs/features/<event_id>/dq_anomaly.json` | Anomaly count + threshold. | - [EVIDENCE] src/pipeline/model.py:L292-L293 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `_association_config` | Normalizes association parameters. | - [EVIDENCE] src/pipeline/model.py:L16-L27 |
| `_series_map` | Builds per-source/channel series for correlation. | - [EVIDENCE] src/pipeline/model.py:L30-L48 |
| `_compute_association` | Pre/post mean change + lagged correlation. | - [EVIDENCE] src/pipeline/model.py:L79-L201 |
| `run_model` | Main anomaly scoring + association outputs. | - [EVIDENCE] src/pipeline/model.py:L204-L293 |

## Error Handling / Edge Cases
- Missing `features.parquet` raises `FileNotFoundError`.
  - [EVIDENCE] src/pipeline/model.py:L215-L218
- If not enough points, z-score/correlation functions return `None` and skip.
  - [EVIDENCE] src/pipeline/model.py:L51-L59
  - [EVIDENCE] src/pipeline/model.py:L71-L76

## Performance Notes
- Anomaly scoring uses groupby over `(source, channel, feature)`.
  - [EVIDENCE] src/pipeline/model.py:L224-L235
- Association uses nested loops over series pairs and lag steps; can be O(N^2 * L).
  - [EVIDENCE] src/pipeline/model.py:L133-L177

## Verification
- `dq_anomaly.json` indicates anomaly count and threshold.
  - [EVIDENCE] src/pipeline/model.py:L292-L293
  - [EVIDENCE] outputs/features/eq_20200912_024411/dq_anomaly.json:L1-L5
- Association summary exists when linked data is present.
  - [EVIDENCE] outputs/features/eq_20200912_024411/association.json:L1-L13
