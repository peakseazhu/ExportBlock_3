# 07 Error Handling and Edge Cases

Purpose / Reader / Takeaways:
- Purpose: enumerate explicit error handling and edge-case behaviors.
- Reader: engineers diagnosing failures or building robust validations.
- Takeaways: where errors are raised vs. silently handled.

## File Parsing and Missing Data
- IAGA2002 parser raises `ValueError` if header is missing.
  - [EVIDENCE] src/io/iaga2002.py:L28-L33
  - [EVIDENCE] src/io/iaga2002.py:L130-L133
- IAGA sentinel values (`>= 88888`) are marked missing and set to `None`.
  - [EVIDENCE] src/io/iaga2002.py:L35-L39
  - [EVIDENCE] src/io/iaga2002.py:L88-L99
- VLF PadValue is converted to NaN in `ch1`/`ch2` arrays.
  - [EVIDENCE] src/io/vlf.py:L29-L37
- Seismic window reads skip empty traces.
  - [EVIDENCE] src/io/seismic.py:L74-L75

## Pipeline Stage Guards
- Feature stage raises if `aligned.parquet` is missing.
  - [EVIDENCE] src/pipeline/features.py:L51-L55
- Model stage raises if `features.parquet` is missing.
  - [EVIDENCE] src/pipeline/model.py:L215-L218
- Link stage writes an empty aligned parquet when no rows remain.
  - [EVIDENCE] src/pipeline/link.py:L94-L99

## Preprocessing Edge Handling
- Wavelet denoise returns original series if too few points.
  - [EVIDENCE] src/pipeline/standard.py:L176-L179
- Seismic preprocessing catches exceptions for detrend/taper/bandpass and records errors.
  - [EVIDENCE] src/pipeline/standard.py:L389-L427
- Interpolation and outlier flags update `quality_flags` with `missing_reason`, `is_outlier`, `is_interpolated`.
  - [EVIDENCE] src/pipeline/standard.py:L278-L309

## API Error Responses
- Missing standard source returns HTTP 404.
  - [EVIDENCE] src/api/app.py:L645-L646
- Missing event outputs return HTTP 404 (`aligned.parquet`, `features.parquet`, `anomaly.parquet`).
  - [EVIDENCE] src/api/app.py:L721-L742
- VLF slice/export returns 404 if no data is found.
  - [EVIDENCE] src/api/app.py:L626-L628
  - [EVIDENCE] src/api/app.py:L831-L833

## Packaging and Export Edge Cases
- Finalize script in strict mode writes FAIL markers and exits with code 1 if required files missing.
  - [EVIDENCE] scripts/finalize_event_package.py:L116-L127
- Event bundle creation raises `FileNotFoundError` when the event directory does not exist.
  - [EVIDENCE] scripts/make_event_bundle.py:L17-L20

## Data Quality Reporting
- `basic_stats` returns null metrics for empty datasets (rows=0, ts_min/max=None).
  - [EVIDENCE] src/dq/reporting.py:L11-L20

## Unknown / Needs Confirmation
- `[UNKNOWN]` Behavior for `time.align_strategy.*` and `features.rolling_window_minutes` is not implemented in code; confirm with `rg -n "align_strategy|rolling_window_minutes" src` and verify if new logic is added.
  - [EVIDENCE] configs/default.yaml:L52-L56
  - [EVIDENCE] configs/default.yaml:L133-L135
