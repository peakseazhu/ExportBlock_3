# 06 Algorithm Notes

Purpose / Reader / Takeaways:
- Purpose: capture key algorithms with steps, formulas, and complexity.
- Reader: reviewers and maintainers validating correctness.
- Takeaways: what each algorithm does and why it exists in the pipeline.

## A) IAGA2002 Parsing (Geomag/AEF)
Algorithm summary:
1) Read header lines and parse station metadata (station_id, lat, lon, elev).
2) Read data section into a dataframe.
3) Convert `DATE` + `TIME` into UTC timestamp and `ts_ms`.
4) For each value column (channel), emit one row per timestamp.
5) Treat `value >= 88888` or NaN as missing; add `quality_flags`.

Evidence:
- Header parsing + metadata extraction: [EVIDENCE] src/io/iaga2002.py:L10-L25
- Data start detection + datetime parsing: [EVIDENCE] src/io/iaga2002.py:L28-L76
- Sentinel handling + long-table record construction: [EVIDENCE] src/io/iaga2002.py:L35-L105

Complexity: O(R * C) for R rows and C value columns (one record per channel per timestamp).

## B) Minute Expansion (AEF)
Algorithm summary:
- Expand each minute record into N second records.
- Offsets are either centered or forward-aligned.
- Each expanded record sets `quality_flags.is_interpolated = True` with `interp_method = "minute_expand"`.

Evidence:
- Expansion logic and flag updates: [EVIDENCE] src/pipeline/standard.py:L92-L123
- Expansion config resolution: [EVIDENCE] src/pipeline/standard.py:L76-L88
- Integration into write loop: [EVIDENCE] src/pipeline/standard.py:L854-L877

Complexity: O(R * N) where N = expansion seconds (default 60).

## C) Outlier Detection (MAD + Hampel)
MAD (global per group):
- Compute median and MAD; z = 0.6745 * (x - median) / MAD.
- If MAD is zero, fallback to mean/std z-score.

Hampel (localized for AEF despike):
- Compute rolling median and rolling MAD within a window; flag points above threshold.

Evidence:
- MAD outlier mask: [EVIDENCE] src/pipeline/standard.py:L126-L139
- Hampel mask: [EVIDENCE] src/pipeline/standard.py:L142-L150
- Application + flagging: [EVIDENCE] src/pipeline/standard.py:L260-L288

Complexity: O(R) per group with rolling window (Hampel) and O(R) for MAD.

## D) Wavelet Denoising
Algorithm summary:
- Fill NaNs by interpolation.
- Perform wavelet decomposition (db4 by default).
- Estimate noise sigma from the last detail coefficients and apply soft threshold.
- Reconstruct and restore NaNs.

Evidence:
- Wavelet config and reconstruction: [EVIDENCE] src/pipeline/standard.py:L176-L203

Complexity: O(R) per series for wavelet transform (dependent on implementation).

## E) Seismic Preprocess + Feature Windows
Algorithm summary:
1) Detrend (demean + linear) and taper waveform.
2) Bandpass filter; cap freqmax by Nyquist ratio.
3) Optional notch filtering for powerline harmonics.
4) Compute RMS and mean_abs over fixed intervals (default 60s).

Evidence:
- Detrend/taper/bandpass/notch: [EVIDENCE] src/pipeline/standard.py:L385-L457
- RMS + mean_abs features: [EVIDENCE] src/pipeline/standard.py:L460-L526

Complexity: O(N) per trace for filtering + O(N / window) for aggregation.

## F) VLF Feature Extraction
Algorithm summary:
- Load Zarr spectrogram arrays (time x freq x channel).
- Mask line noise around base frequencies and harmonics.
- Compute band power per band (median or mean over freq bins).
- Compute peak frequency for each timestamp.
- Aggregate to target time interval and apply rolling median.
- Optional background subtraction per station/channel.

Evidence:
- Line mask and band power: [EVIDENCE] src/pipeline/standard.py:L598-L662
- Peak frequency: [EVIDENCE] src/pipeline/standard.py:L663-L681
- Time aggregation + rolling median: [EVIDENCE] src/pipeline/standard.py:L693-L708
- Background subtraction: [EVIDENCE] src/pipeline/standard.py:L710-L724

Complexity: O(T * F * B) where T = time bins, F = freq bins, B = band count.

## G) Event Linking
Algorithm summary:
- Build event window [origin - pre_hours, origin + post_hours].
- Filter standard data by time and optional distance.
- Align timestamps to `align_interval` via floor division.
- Write aligned parquet and coverage metrics.

Evidence:
- Event window + interval: [EVIDENCE] src/pipeline/link.py:L39-L48
- Spatial filter + align: [EVIDENCE] src/pipeline/link.py:L69-L78
- Coverage metrics: [EVIDENCE] src/pipeline/link.py:L104-L116

Complexity: O(R) for filtering + alignment where R is rows in window.

## H) Feature Aggregation
Algorithm summary:
- Group by (source, station_id, channel).
- Compute stats: mean/std/variance/min/max/peak/rms/count.
- Add geomag gradients and seismic arrival offsets.

Evidence:
- Stats computation: [EVIDENCE] src/pipeline/features.py:L62-L87
- Gradient features: [EVIDENCE] src/pipeline/features.py:L88-L105
- Arrival offsets: [EVIDENCE] src/pipeline/features.py:L106-L132

Complexity: O(R) with groupby aggregation.

## I) Anomaly Scoring + Association
Algorithm summary:
- For each (source, channel, feature), compute z-score; flag abs(z) >= threshold.
- For association: compute pre/post mean shift per series and cross-correlation across sources with lag search.

Evidence:
- Z-score scoring: [EVIDENCE] src/pipeline/model.py:L224-L235
- Change score + flag: [EVIDENCE] src/pipeline/model.py:L101-L130
- Lagged correlation: [EVIDENCE] src/pipeline/model.py:L133-L177

Complexity: O(G) for z-score groups + O(P * L) for correlation pairs (P=pair count, L=lag count).
