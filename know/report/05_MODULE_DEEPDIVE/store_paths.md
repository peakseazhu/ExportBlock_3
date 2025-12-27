# Module Deep Dive: store.paths

Purpose / Reader / Takeaways:
- Purpose: define the output directory contract used across the pipeline.
- Reader: developers adding new outputs or relocating output roots.
- Takeaways: canonical paths and their meaning.

## Responsibilities
- Define output subdirectories (manifests, ingest, raw, standard, linked, features, models, plots, reports, events).
- Provide `ensure()` to create directories.
- [EVIDENCE] src/store/paths.py:L6-L36

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `root` | Output root path configured by CLI. | - [EVIDENCE] scripts/pipeline_run.py:L42-L44 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| `OutputPaths` object | Holds path properties for all subdirectories. | - [EVIDENCE] src/store/paths.py:L6-L19 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `OutputPaths.__init__` | Defines all output directory paths. | - [EVIDENCE] src/store/paths.py:L6-L19 |
| `OutputPaths.ensure` | Creates directories. | - [EVIDENCE] src/store/paths.py:L21-L36 |

## Error Handling / Edge Cases
- Uses `ensure_dir` which creates parents and does not error if exists.
  - [EVIDENCE] src/store/paths.py:L3-L36
  - [EVIDENCE] src/utils.py:L12-L13

## Verification
- A pipeline run creates all output subdirectories under configured root.
  - [EVIDENCE] scripts/pipeline_run.py:L42-L45
