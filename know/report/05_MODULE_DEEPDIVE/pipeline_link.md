# Module Deep Dive: pipeline.link

Purpose / Reader / Takeaways:
- Purpose: explain event-window alignment and spatial linking into event datasets.
- Reader: developers validating linked outputs or tuning event windows.
- Takeaways: alignment rules, spatial filtering, and output artifacts.

## Responsibilities
- Compute event time window and align timestamps to interval.
- Filter by spatial radius (optional) and combine sources into one aligned table.
- Write linked outputs: `aligned.parquet`, `summary.json`, `event.json`, `stations.json`.
- [EVIDENCE] src/pipeline/link.py:L30-L135

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `config.events` | Event metadata, incl. origin time and location. | - [EVIDENCE] src/pipeline/link.py:L39-L44 |
| `config.time.align_interval` | Alignment interval (e.g., 1min). | - [EVIDENCE] src/pipeline/link.py:L46-L48 |
| `config.time.event_window` | Pre/post hours around event. | - [EVIDENCE] src/pipeline/link.py:L41-L44 |
| `config.link.spatial_km` | Spatial radius for station filtering. | - [EVIDENCE] src/pipeline/link.py:L48-L49 |
| `outputs/standard/source=<source>` | Standardized per-source parquet. | - [EVIDENCE] src/pipeline/link.py:L57-L63 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| `outputs/linked/<event_id>/aligned.parquet` | Event-aligned long table. | - [EVIDENCE] src/pipeline/link.py:L90-L100 |
| `outputs/linked/<event_id>/stations.json` | Station summaries (rows, distance). | - [EVIDENCE] src/pipeline/link.py:L81-L103 |
| `outputs/linked/<event_id>/summary.json` | Coverage summary and source counts. | - [EVIDENCE] src/pipeline/link.py:L104-L118 |
| `outputs/linked/<event_id>/event.json` | Event metadata + config context. | - [EVIDENCE] src/pipeline/link.py:L120-L135 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `_align_ts` | Floor-align timestamps to interval. | - [EVIDENCE] src/pipeline/link.py:L17-L18 |
| `_filter_by_distance` | Haversine filter by radius. | - [EVIDENCE] src/pipeline/link.py:L21-L27 |
| `run_link` | Main link pipeline. | - [EVIDENCE] src/pipeline/link.py:L30-L135 |

## Error Handling / Edge Cases
- If a source directory does not exist, it is skipped.
  - [EVIDENCE] src/pipeline/link.py:L58-L61
- If no data after filtering, an empty aligned parquet is still written.
  - [EVIDENCE] src/pipeline/link.py:L94-L99
- `require_station_location` drops rows without coordinates when enabled.
  - [EVIDENCE] src/pipeline/link.py:L50-L67

## Performance Notes
- Uses parquet predicate pushdown via `read_parquet_filtered` with time filters.
  - [EVIDENCE] src/pipeline/link.py:L61-L63
  - [EVIDENCE] src/store/parquet.py:L284-L314

## Verification
- `summary.json` and `event.json` should exist under `outputs/linked/<event_id>/`.
  - [EVIDENCE] src/pipeline/link.py:L104-L135
  - [EVIDENCE] outputs/linked/eq_20200912_024411/summary.json:L1-L17
  - [EVIDENCE] outputs/linked/eq_20200912_024411/event.json:L1-L17
