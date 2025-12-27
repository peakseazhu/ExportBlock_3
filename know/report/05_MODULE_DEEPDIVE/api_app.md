# Module Deep Dive: api.app

Purpose / Reader / Takeaways:
- Purpose: document the FastAPI surface and how it serves data from `outputs/`.
- Reader: developers integrating external tools or boosting API coverage.
- Takeaways: endpoints, query parameters, and output formats.

## Responsibilities
- Serve raw/standard data queries, event artifacts, export bundles, and UI pages.
- Mount `outputs/` as static files for plot HTML.
- [EVIDENCE] src/api/app.py:L20-L26
- [EVIDENCE] src/api/app.py:L487-L1034

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `OUTPUT_ROOT` env var | Output root for API data. | - [EVIDENCE] src/api/app.py:L20-L21 |
| Raw index + standard parquet | Data sources for `/raw/query` and `/standard/query`. | - [EVIDENCE] src/api/app.py:L492-L667 |
| Linked/features outputs | Data sources for event endpoints. | - [EVIDENCE] src/api/app.py:L718-L765 |

## Outputs
| Endpoint | Description | Evidence |
| --- | --- | --- |
| `GET /health` | Health check. | - [EVIDENCE] src/api/app.py:L487-L489 |
| `GET /raw/query` | Raw data query by source/time/station/bounds. | - [EVIDENCE] src/api/app.py:L492-L597 |
| `GET /raw/vlf/slice` | Downsampled VLF spectrogram slice. | - [EVIDENCE] src/api/app.py:L599-L628 |
| `GET /standard/query` | Standardized data query. | - [EVIDENCE] src/api/app.py:L631-L667 |
| `GET /raw/summary` | Raw index summary. | - [EVIDENCE] src/api/app.py:L670-L684 |
| `GET /standard/summary` | Standard summary. | - [EVIDENCE] src/api/app.py:L687-L698 |
| `GET /events` | List event bundles (DONE/FAIL). | - [EVIDENCE] src/api/app.py:L701-L715 |
| `GET /events/{id}/linked` | Linked data for event. | - [EVIDENCE] src/api/app.py:L718-L724 |
| `GET /events/{id}/features` | Features data for event. | - [EVIDENCE] src/api/app.py:L727-L733 |
| `GET /events/{id}/anomaly` | Anomaly data for event. | - [EVIDENCE] src/api/app.py:L736-L742 |
| `GET /events/{id}/association` | Association summary + rows. | - [EVIDENCE] src/api/app.py:L745-L765 |
| `GET /events/{id}/plots` | Plotly spec for event plot. | - [EVIDENCE] src/api/app.py:L768-L773 |
| `GET /events/{id}/export` | Export aligned data (CSV/HDF5) + optional raw bundle. | - [EVIDENCE] src/api/app.py:L853-L977 |
| `GET /events/{id}/seismic/export` | Export seismic raw window. | - [EVIDENCE] src/api/app.py:L776-L800 |
| `GET /events/{id}/vlf/export` | Export VLF raw slice (json/npz). | - [EVIDENCE] src/api/app.py:L803-L850 |
| `GET /ui` and `/ui/events/{id}` | HTML UI pages. | - [EVIDENCE] src/api/app.py:L980-L1034 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `_parse_time` | Parse ISO/date/epoch time inputs. | - [EVIDENCE] src/api/app.py:L29-L40 |
| `_filter_df` | Apply time/station/geo filters + limit. | - [EVIDENCE] src/api/app.py:L43-L82 |
| `_summarize_df` | Build summary with time ranges. | - [EVIDENCE] src/api/app.py:L110-L120 |

## Error Handling / Edge Cases
- Missing outputs return HTTP 404 errors for most endpoints.
  - [EVIDENCE] src/api/app.py:L645-L646
  - [EVIDENCE] src/api/app.py:L721-L742
- VLF slice/export returns 404 when no data matches.
  - [EVIDENCE] src/api/app.py:L626-L628
  - [EVIDENCE] src/api/app.py:L831-L833

## Performance Notes
- Raw queries can read original files; large windows should use `limit` or narrower ranges.
  - [EVIDENCE] docs/api.md:L14-L16
  - [EVIDENCE] src/api/app.py:L533-L582

## Verification
- Smoke test covers `/health`, `/raw/query`, and `/standard/query` endpoints.
  - [EVIDENCE] tests/test_api_smoke.py:L11-L81
