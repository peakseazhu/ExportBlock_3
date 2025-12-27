# Module Deep Dive: pipeline.plots

Purpose / Reader / Takeaways:
- Purpose: document Plotly plot generation for UI and reports.
- Reader: developers adjusting visualization outputs.
- Takeaways: plot types, inputs, and DQ outputs.

## Responsibilities
- Generate aligned timeseries, station map, filter effect, and VLF spectrogram plots.
- Write Plotly JSON specs and HTML files.
- Emit `dq_plots.json` status report.
- [EVIDENCE] src/pipeline/plots.py:L24-L140

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `outputs/linked/<event_id>/aligned.parquet` | Aligned long table for plots. | - [EVIDENCE] src/pipeline/plots.py:L35-L37 |
| `outputs/reports/filter_effect.json` | Standard filter effect stats. | - [EVIDENCE] src/pipeline/plots.py:L87-L97 |
| `outputs/raw/vlf/*/spectrogram.zarr` | VLF spectrogram data (optional). | - [EVIDENCE] src/pipeline/plots.py:L103-L118 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| `outputs/plots/spec/<event_id>/plot_*.json` | Plotly figure specs. | - [EVIDENCE] src/pipeline/plots.py:L16-L21
| `outputs/plots/html/<event_id>/plot_*.html` | Rendered HTML plots. | - [EVIDENCE] src/pipeline/plots.py:L16-L21 |
| `outputs/reports/dq_plots.json` | Plot availability status. | - [EVIDENCE] src/pipeline/plots.py:L139-L140 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `_write_plot` | Writes spec + HTML for a figure. | - [EVIDENCE] src/pipeline/plots.py:L16-L21 |
| `run_plots` | Creates all plots and DQ status. | - [EVIDENCE] src/pipeline/plots.py:L24-L140 |

## Error Handling / Edge Cases
- If aligned data is missing, plot status is set to `missing` and plot is skipped.
  - [EVIDENCE] src/pipeline/plots.py:L43-L64
- If station coordinates are missing, station map is marked missing.
  - [EVIDENCE] src/pipeline/plots.py:L65-L85
- VLF plot is only written if a spectrogram exists.
  - [EVIDENCE] src/pipeline/plots.py:L102-L137

## Performance Notes
- Plot building uses full aligned dataset; large data can increase runtime.
  - [EVIDENCE] src/pipeline/plots.py:L43-L59

## Verification
- `outputs/reports/dq_plots.json` reports `ok` or `missing` for each plot.
  - [EVIDENCE] src/pipeline/plots.py:L139-L140
  - [EVIDENCE] outputs/reports/dq_plots.json:L1-L6
