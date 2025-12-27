# Module Deep Dive: pipeline.manifest

Purpose / Reader / Takeaways:
- Purpose: document file scanning and manifest generation.
- Reader: developers validating data provenance or troubleshooting missing files.
- Takeaways: manifest JSON schema and how files are discovered.

## Responsibilities
- Scan configured roots and glob patterns for each data source.
- Compute file size, mtime, and SHA256 for reproducibility.
- Write `outputs/manifests/run_<run_id>.json`.
- [EVIDENCE] src/pipeline/manifest.py:L23-L69

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `config.paths.*` | Roots/patterns per source, with IAGA pattern handling. | - [EVIDENCE] src/pipeline/manifest.py:L30-L45 |
| `limits.max_files_per_source` | Optional cap on scanned files. | - [EVIDENCE] src/pipeline/manifest.py:L31-L32 |
| `base_dir`, `run_id`, `params_hash` | Added to manifest metadata. | - [EVIDENCE] src/pipeline/manifest.py:L24-L29 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| `outputs/manifests/run_<run_id>.json` | Manifest payload with file list and totals. | - [EVIDENCE] src/pipeline/stages.py:L18-L27<br>- [EVIDENCE] src/pipeline/manifest.py:L60-L68 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `build_manifest` | Main entry: builds file list and summary. | - [EVIDENCE] src/pipeline/manifest.py:L23-L69 |
| `_collect_files` | Applies glob patterns and file cap. | - [EVIDENCE] src/pipeline/manifest.py:L12-L20 |

## Error Handling / Edge Cases
- Uses `resolve_iaga_patterns` to avoid incorrect patterns when `read_mode` is set.
  - [EVIDENCE] src/pipeline/manifest.py:L34-L40
- No explicit try/except around file hashing; errors will bubble up from filesystem operations.
  - [EVIDENCE] src/pipeline/manifest.py:L45-L57
  - [EVIDENCE] src/utils.py:L16-L21

## Performance Notes
- SHA256 hashing reads full files; large datasets may increase manifest time.
  - [EVIDENCE] src/utils.py:L16-L21

## Verification
- Manifest output includes `total_files`, `total_bytes`, and per-file `sha256`.
  - [EVIDENCE] src/pipeline/manifest.py:L60-L67
