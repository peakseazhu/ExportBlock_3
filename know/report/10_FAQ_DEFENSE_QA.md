# 10 FAQ / Defense Q&A

Purpose / Reader / Takeaways:
- Purpose: provide defensible answers to common and deep-dive questions.
- Reader: presenters and reviewers in a defense or audit.
- Takeaways: concise answers backed by concrete evidence.

| # | Question | Answer | Evidence |
| --- | --- | --- | --- |
| 1 | Why must stages run in a strict order? | The runner enforces a fixed stage order and rejects out-of-order lists to maintain data dependencies. | - [EVIDENCE] src/pipeline/runner.py:L11-L44 |
| 2 | What is the purpose of the manifest stage? | It scans input files and records size, mtime, and SHA256 for reproducibility. | - [EVIDENCE] src/pipeline/manifest.py:L23-L57 |
| 3 | Why is there a raw index stage? | Raw index builds queryable metadata so `/raw/query` can read original files efficiently. | - [EVIDENCE] src/pipeline/raw.py:L40-L151<br>- [EVIDENCE] src/api/app.py:L492-L597 |
| 4 | How are geomag/AEF timestamps represented? | `DATE` + `TIME` are parsed as UTC and converted to `ts_ms` (epoch ms). | - [EVIDENCE] src/io/iaga2002.py:L72-L76 |
| 5 | How are missing values detected in IAGA files? | Values `>= 88888` (or NaN) are treated as missing and flagged. | - [EVIDENCE] src/io/iaga2002.py:L35-L39<br>- [EVIDENCE] src/io/iaga2002.py:L88-L99 |
| 6 | Where do seismic station coordinates come from? | StationXML is loaded and joined to trace metadata using network/station/location/channel keys. | - [EVIDENCE] src/io/seismic.py:L19-L27<br>- [EVIDENCE] src/io/seismic.py:L107-L157 |
| 7 | How is VLF raw data stored? | VLF CDF is converted to Zarr `spectrogram.zarr` with `epoch_ns`, `freq_hz`, `ch1`, `ch2`. | - [EVIDENCE] src/pipeline/ingest.py:L138-L151 |
| 8 | Why does VLF raw query return catalog rows instead of long-table samples? | API explicitly returns VLF catalog rows for `/raw/query` and uses `/raw/vlf/slice` for spectrogram slices. | - [EVIDENCE] src/api/app.py:L510-L523<br>- [EVIDENCE] docs/api.md:L14-L16 |
| 9 | How is the event time window computed? | `origin_time_utc` is expanded by `pre_hours` and `post_hours` to define the window. | - [EVIDENCE] src/pipeline/link.py:L39-L44 |
| 10 | How are timestamps aligned for linking? | Alignment is floor-to-interval: `ts_ms = (ts_ms // interval_ms) * interval_ms`. | - [EVIDENCE] src/pipeline/link.py:L17-L18 |
| 11 | What spatial filtering is applied in linking? | Stations are filtered by haversine distance within `link.spatial_km`. | - [EVIDENCE] src/pipeline/link.py:L69-L70<br>- [EVIDENCE] src/pipeline/spatial.py:L14-L22 |
| 12 | How are geomag/AEF outliers detected? | MAD-based z-scores are computed; points above threshold are flagged and set to NaN. | - [EVIDENCE] src/pipeline/standard.py:L126-L139<br>- [EVIDENCE] src/pipeline/standard.py:L278-L288 |
| 13 | How are AEF spikes removed? | Hampel filtering is applied with window + threshold before interpolation. | - [EVIDENCE] src/pipeline/standard.py:L260-L276 |
| 14 | How are missing values filled in standardization? | Values are interpolated up to `max_gap_points` and flagged in `quality_flags`. | - [EVIDENCE] src/pipeline/standard.py:L290-L309 |
| 15 | Why are geomag/AEF wavelets used? | Wavelet denoising is applied when configured to suppress noise. | - [EVIDENCE] src/pipeline/standard.py:L176-L203 |
| 16 | How are seismic features computed? | For each trace, RMS and mean_abs are computed over fixed windows. | - [EVIDENCE] src/pipeline/standard.py:L460-L526 |
| 17 | How are VLF features computed? | Band power per frequency band + peak frequency per time bin are computed and aggregated. | - [EVIDENCE] src/pipeline/standard.py:L613-L681<br>- [EVIDENCE] src/pipeline/standard.py:L693-L700 |
| 18 | How are event-level features computed? | Per-group stats (mean/std/min/max/rms/count) plus geomag gradients and seismic arrival offsets. | - [EVIDENCE] src/pipeline/features.py:L62-L132 |
| 19 | How are anomalies scored? | Z-score is computed per `(source, channel, feature)` and thresholded. | - [EVIDENCE] src/pipeline/model.py:L224-L235 |
| 20 | How is cross-source association decided? | Uses pre/post mean change and lagged correlations with configurable thresholds. | - [EVIDENCE] src/pipeline/model.py:L101-L199 |
| 21 | Where is the pipeline version recorded? | Stored in event metadata (`event.json`) and `proc_version` fields. | - [EVIDENCE] src/pipeline/link.py:L129-L130<br>- [EVIDENCE] outputs/linked/eq_20200912_024411/event.json:L1-L12 |
| 22 | What is `params_hash` and why is it used? | Hash of config JSON for reproducibility; stored in outputs and rulebook. | - [EVIDENCE] src/config.py:L24-L26<br>- [EVIDENCE] src/pipeline/model.py:L287-L290 |
| 23 | How do we verify end-to-end runtime? | `runtime_report.json` contains per-stage timing and total duration. | - [EVIDENCE] scripts/pipeline_run.py:L61-L83<br>- [EVIDENCE] outputs/reports/runtime_report.json:L1-L62 |
| 24 | What if a required event artifact is missing? | `finalize_event_package.py --strict` marks FAIL and exits non-zero. | - [EVIDENCE] scripts/finalize_event_package.py:L116-L127 |
| 25 | How are outputs partitioned for query efficiency? | Parquet datasets are written with hive partitioning (e.g., `station_id`, `date`). | - [EVIDENCE] src/store/parquet.py:L58-L63<br>- [EVIDENCE] configs/default.yaml:L154-L155 |
| 26 | How does the API choose the output root? | It uses `OUTPUT_ROOT` env var and defaults to `outputs/`. | - [EVIDENCE] src/api/app.py:L20-L21 |
| 27 | What plots are generated? | Aligned timeseries, station map, filter effect, optional VLF spectrogram. | - [EVIDENCE] src/pipeline/plots.py:L43-L137 |
| 28 | How does the API parse time inputs? | Supports ISO/date/epoch (10 or 13 digits) and converts to ms. | - [EVIDENCE] src/api/app.py:L29-L40 |
| 29 | Are there automated tests for the API? | Smoke test validates `/health`, `/raw/query`, `/standard/query`. | - [EVIDENCE] tests/test_api_smoke.py:L11-L81 |
| 30 | How is data quality reported? | `basic_stats` computes rows/time/missing/outlier rates and adds `generated_at_utc`. | - [EVIDENCE] src/dq/reporting.py:L11-L43 |
