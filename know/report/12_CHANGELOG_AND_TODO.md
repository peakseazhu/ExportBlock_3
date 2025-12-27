# 12 Changelog and TODO

Purpose / Reader / Takeaways:
- Purpose: list observed risks, technical debt, and improvement ideas with evidence.
- Reader: maintainers planning next iterations.
- Takeaways: actionable items grounded in repository evidence.

| Item | Risk / Issue | Evidence | Suggested Action |
| --- | --- | --- | --- |
| Output overwrite behavior | Standard and raw stages delete existing output directories, which can remove previous results if reused output root. | - [EVIDENCE] src/pipeline/standard.py:L776-L779<br>- [EVIDENCE] src/pipeline/raw.py:L33-L37 | Add run-scoped output roots or archive previous outputs before overwrite. |
| API output root mismatch | Pipeline writes to `outputs.root`, but API uses `OUTPUT_ROOT` env var and does not read config, which can lead to mismatched data roots. | - [EVIDENCE] scripts/pipeline_run.py:L42-L44<br>- [EVIDENCE] src/api/app.py:L20-L21 | Align API startup with config snapshot or export `OUTPUT_ROOT` from run metadata. |
| Implicit anomaly threshold | `features.anomaly_threshold` is not in default config and falls back to `3.0` in code. | - [EVIDENCE] configs/default.yaml:L133-L145<br>- [EVIDENCE] src/pipeline/model.py:L221-L235 | Add `features.anomaly_threshold` to config for explicit control. |
| Unused config keys (align_strategy) | `time.align_strategy.*` is defined but not used in code. | - [EVIDENCE] configs/default.yaml:L52-L56<br>- [EVIDENCE] docs/config_reference.md:L189-L210 | Either remove unused keys or implement their behavior in `link`/`standard`. |
| Unused config key (`features.rolling_window_minutes`) | Key exists in config; usage not found in pipeline code during review. | - [EVIDENCE] configs/default.yaml:L133-L135 | [UNKNOWN] Confirm with code search; implement rolling-window features if required. |
| Zarr compression config not wired | `storage.zarr.compressor` is defined, but ingest writes Zarr without using it. | - [EVIDENCE] configs/default.yaml:L157-L158<br>- [EVIDENCE] src/pipeline/ingest.py:L138-L151<br>- [EVIDENCE] src/store/zarr_utils.py:L1-L5 | Wire compressor selection into VLF Zarr writes. |
| Limited E2E test coverage | Tests focus on unit/integration; no full pipeline run test observed. | - [EVIDENCE] tests/test_api_smoke.py:L11-L81<br>- [EVIDENCE] tests/test_anomaly_model.py:L9-L31 | Add a small end-to-end test using demo config and fixtures. |
| VLF/Seismic DQ in filter_effect | Filter-effect report only covers geomag/AEF sources. | - [EVIDENCE] src/pipeline/standard.py:L997-L1032<br>- [EVIDENCE] outputs/reports/filter_effect.json:L1-L10 | Consider extending filter-effect reporting to seismic/VLF or clarify scope. |
