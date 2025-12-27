# Module Deep Dive: pipeline.standard

Purpose / Reader / Takeaways:
- Purpose: detail the standardization and cleaning logic for all sources.
- Reader: developers tuning preprocessing or validating standard outputs.
- Takeaways: preprocessing steps, feature generation, and DQ reporting.

## Responsibilities
- Clean geomag/AEF long-table series (detrend, highpass, wavelet, outliers, interpolate, lowpass).
- Generate seismic features (RMS and mean_abs) from waveform windows.
- Generate VLF band-power and peak-frequency features from Zarr spectrograms.
- Write standardized parquet outputs and DQ/filter reports.
- [EVIDENCE] src/pipeline/standard.py:L206-L745
- [EVIDENCE] src/pipeline/standard.py:L982-L1032

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| `outputs/ingest/geomag` | Geomag ingest parquet. | - [EVIDENCE] src/pipeline/standard.py:L997-L1004 |
| `outputs/ingest/aef` | AEF ingest parquet. | - [EVIDENCE] src/pipeline/standard.py:L1006-L1013 |
| `outputs/ingest/seismic_files` | Seismic MiniSEED cache. | - [EVIDENCE] src/pipeline/standard.py:L474-L486 |
| `outputs/raw/vlf/*/spectrogram.zarr` | VLF raw spectrograms. | - [EVIDENCE] src/pipeline/standard.py:L587-L596 |
| `config.preprocess` | Cleaning parameters and expansion rules. | - [EVIDENCE] src/pipeline/standard.py:L37-L88 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| `outputs/standard/source=<source>` | Standardized parquet outputs. | - [EVIDENCE] src/pipeline/standard.py:L776-L879<br>- [EVIDENCE] src/pipeline/standard.py:L1016-L1029 |
| `outputs/reports/dq_standard.json` | DQ stats per source. | - [EVIDENCE] src/pipeline/standard.py:L1031-L1031 |
| `outputs/reports/filter_effect.json` | Before/after std for geomag/AEF. | - [EVIDENCE] src/pipeline/standard.py:L978-L1032 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `_iter_expand_minute_to_seconds` | Expand minute data to 1-second rows with interpolation flags. | - [EVIDENCE] src/pipeline/standard.py:L92-L123 |
| `_mad_outlier_mask` | Median absolute deviation outlier detection. | - [EVIDENCE] src/pipeline/standard.py:L126-L139 |
| `_hampel_mask` | Hampel filter for spike removal. | - [EVIDENCE] src/pipeline/standard.py:L142-L150 |
| `_wavelet_denoise` | Wavelet denoising with thresholding. | - [EVIDENCE] src/pipeline/standard.py:L176-L203 |
| `_apply_geomag_aef_preprocess` | Detrend/highpass/wavelet preprocessing. | - [EVIDENCE] src/pipeline/standard.py:L206-L237 |
| `_clean_timeseries_group` | Outlier flagging, interpolation, lowpass. | - [EVIDENCE] src/pipeline/standard.py:L240-L328 |
| `_apply_seismic_preprocess` | Detrend, taper, bandpass, notch for seismic. | - [EVIDENCE] src/pipeline/standard.py:L385-L457 |
| `_seismic_features` | RMS/mean_abs aggregation by interval. | - [EVIDENCE] src/pipeline/standard.py:L460-L556 |
| `_vlf_features` | Band power/peak frequency + aggregation. | - [EVIDENCE] src/pipeline/standard.py:L559-L745 |
| `run_standard` | Main entry and report writes. | - [EVIDENCE] src/pipeline/standard.py:L982-L1032 |

## Error Handling / Edge Cases
- Seismic preprocessing catches errors during detrend/taper/filter and annotates metadata.
  - [EVIDENCE] src/pipeline/standard.py:L389-L427
- Wavelet denoise returns input if too few points (<8).
  - [EVIDENCE] src/pipeline/standard.py:L176-L179
- Missing/outlier values are set to NaN and flagged in `quality_flags`.
  - [EVIDENCE] src/pipeline/standard.py:L278-L309

## Performance Notes
- Standard stage scans parquet in batches and uses overlap windows to avoid edge artifacts.
  - [EVIDENCE] src/pipeline/standard.py:L756-L845
- Outputs are overwritten (`shutil.rmtree`) to prevent stale partitions.
  - [EVIDENCE] src/pipeline/standard.py:L776-L779
- VLF feature generation loops over time/frequency and can be CPU-heavy for large Zarr arrays.
  - [EVIDENCE] src/pipeline/standard.py:L587-L689

## Verification
- DQ report `outputs/reports/dq_standard.json` and filter effect report exist after run.
  - [EVIDENCE] src/pipeline/standard.py:L1031-L1032
  - [EVIDENCE] outputs/reports/dq_standard.json:L1-L37
  - [EVIDENCE] outputs/reports/filter_effect.json:L1-L10
