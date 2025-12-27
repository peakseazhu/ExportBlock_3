# 04 Config Spec

Purpose / Reader / Takeaways:
- Purpose: define every configuration key, default value, scope, and its impact on code paths.
- Reader: engineers modifying configs or validating reproducibility.
- Takeaways: what each config controls and where it is used.

## Config Files and Loading
Primary configs live under `configs/` and are loaded via `load_config`.
- [EVIDENCE] README.md:L41-L44
- [EVIDENCE] src/config.py:L9-L12

Defaults referenced below are from `configs/default.yaml` unless noted.
- [EVIDENCE] configs/default.yaml:L1-L162

## pipeline
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `pipeline.version` | `"0.1.0"` | ingest/raw/standard/link/model | Written to `proc_version` fields and event metadata. | - [EVIDENCE] configs/default.yaml:L1-L2<br>- [EVIDENCE] src/pipeline/ingest.py:L54-L70<br>- [EVIDENCE] src/pipeline/raw.py:L49-L70<br>- [EVIDENCE] src/pipeline/link.py:L129-L130 |

## paths
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `paths.geomag.root` | `"地磁"` | manifest/ingest/raw | Root for IAGA2002 geomag files. | - [EVIDENCE] configs/default.yaml:L4-L6<br>- [EVIDENCE] src/pipeline/manifest.py:L34-L40<br>- [EVIDENCE] src/pipeline/ingest.py:L65-L70 |
| `paths.geomag.sec_patterns` | `["*.sec"]` | manifest/ingest/raw | Glob patterns for geomag sec files. | - [EVIDENCE] configs/default.yaml:L7-L8<br>- [EVIDENCE] src/io/iaga2002.py:L108-L119 |
| `paths.geomag.min_patterns` | `["*.min"]` | manifest/ingest/raw | Glob patterns for geomag minute files (if enabled). | - [EVIDENCE] configs/default.yaml:L9-L10<br>- [EVIDENCE] src/io/iaga2002.py:L108-L119 |
| `paths.geomag.read_mode` | `"sec"` | ingest/raw/manifest | Controls sec/min/both selection in IAGA pattern resolution. | - [EVIDENCE] configs/default.yaml:L11-L11<br>- [EVIDENCE] src/io/iaga2002.py:L108-L119 |
| `paths.aef.root` | `"大气电磁信号/大气电场/kak202001-202010daef.min"` | manifest/ingest/raw | Root for AEF IAGA2002 files. | - [EVIDENCE] configs/default.yaml:L12-L13<br>- [EVIDENCE] src/pipeline/ingest.py:L77-L80 |
| `paths.aef.min_patterns` | `["*.min"]` | manifest/ingest/raw | Glob patterns for AEF files. | - [EVIDENCE] configs/default.yaml:L14-L15<br>- [EVIDENCE] src/io/iaga2002.py:L108-L119 |
| `paths.aef.read_mode` | `"min"` | ingest/raw/manifest | Controls sec/min/both selection in IAGA pattern resolution. | - [EVIDENCE] configs/default.yaml:L16-L16<br>- [EVIDENCE] src/io/iaga2002.py:L108-L119 |
| `paths.seismic.root` | `"地震波"` | manifest/ingest | Root for MiniSEED/SAC + StationXML. | - [EVIDENCE] configs/default.yaml:L17-L18<br>- [EVIDENCE] src/pipeline/ingest.py:L88-L100 |
| `paths.seismic.mseed_patterns` | `["*.seed","*.mseed"]` | manifest/ingest | Glob patterns for MiniSEED files. | - [EVIDENCE] configs/default.yaml:L19-L21<br>- [EVIDENCE] src/pipeline/ingest.py:L89-L91 |
| `paths.seismic.sac_patterns` | `["*.sac"]` | manifest/ingest | Optional SAC copy to ingest cache. | - [EVIDENCE] configs/default.yaml:L22-L23<br>- [EVIDENCE] src/pipeline/ingest.py:L196-L203 |
| `paths.seismic.stationxml` | `"地震波stations_inventory.xml"` | manifest/ingest | StationXML used for lat/lon/elev enrichment. | - [EVIDENCE] configs/default.yaml:L24-L24<br>- [EVIDENCE] src/pipeline/ingest.py:L102-L107 |
| `paths.vlf.root` | `"大气电磁信号/电磁波动vlf/vlf"` | manifest/ingest | Root for VLF CDF files. | - [EVIDENCE] configs/default.yaml:L25-L26<br>- [EVIDENCE] src/pipeline/ingest.py:L122-L124 |
| `paths.vlf.patterns` | `["*.cdf"]` | manifest/ingest | Glob patterns for VLF files. | - [EVIDENCE] configs/default.yaml:L27-L28<br>- [EVIDENCE] src/pipeline/ingest.py:L123-L125 |

## outputs
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `outputs.root` | `"outputs"` | CLI runner | Root output directory. | - [EVIDENCE] configs/default.yaml:L30-L31<br>- [EVIDENCE] scripts/pipeline_run.py:L42-L44 |

## limits
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `limits.max_files_per_source` | `null` | manifest/ingest/raw | Caps files per source scan. | - [EVIDENCE] configs/default.yaml:L33-L35<br>- [EVIDENCE] src/pipeline/manifest.py:L31-L45<br>- [EVIDENCE] src/pipeline/ingest.py:L55-L58 |
| `limits.max_rows_per_source` | `null` | ingest/standard | Caps rows per source after ingest or during standardization. | - [EVIDENCE] configs/default.yaml:L34-L35<br>- [EVIDENCE] src/pipeline/ingest.py:L57-L84<br>- [EVIDENCE] src/pipeline/standard.py:L354-L369 |

## events
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `events[]` | list w/ one event | link/features/model | Event context for linking and feature/model stages. | - [EVIDENCE] configs/default.yaml:L37-L44<br>- [EVIDENCE] src/config.py:L29-L38<br>- [EVIDENCE] src/pipeline/link.py:L39-L44 |
| `events[].event_id` | `"eq_20200912_024411"` | link/features/model | Output directory name and event selector. | - [EVIDENCE] configs/default.yaml:L37-L38<br>- [EVIDENCE] src/pipeline/link.py:L108-L133 |
| `events[].name` | `"2020-09-12 Japan"` | link | Stored in event metadata. | - [EVIDENCE] configs/default.yaml:L39-L39<br>- [EVIDENCE] src/pipeline/link.py:L123-L127 |
| `events[].origin_time_utc` | `"2020-09-12T02:44:11Z"` | link/features/model | Defines event window and arrival offsets. | - [EVIDENCE] configs/default.yaml:L40-L40<br>- [EVIDENCE] src/pipeline/link.py:L39-L44<br>- [EVIDENCE] src/pipeline/features.py:L49-L51 |
| `events[].lat` | `38.748` | link | Used for spatial filtering. | - [EVIDENCE] configs/default.yaml:L41-L41<br>- [EVIDENCE] src/pipeline/link.py:L69-L70 |
| `events[].lon` | `142.245` | link | Used for spatial filtering. | - [EVIDENCE] configs/default.yaml:L42-L42<br>- [EVIDENCE] src/pipeline/link.py:L69-L70 |
| `events[].depth_km` | `34.0` | link | Stored in event metadata. | - [EVIDENCE] configs/default.yaml:L43-L43<br>- [EVIDENCE] src/pipeline/link.py:L125-L127 |
| `events[].magnitude` | `6.1` | link | Stored in event metadata. | - [EVIDENCE] configs/default.yaml:L44-L44<br>- [EVIDENCE] src/pipeline/link.py:L127-L129 |

## time
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `time.timezone` | `"UTC"` | (not referenced) | Reserved; not used in code paths. | - [EVIDENCE] configs/default.yaml:L46-L48<br>- [EVIDENCE] docs/config_reference.md:L165-L169 |
| `time.align_interval` | `"1min"` | link | Alignment bucket size. | - [EVIDENCE] configs/default.yaml:L48-L48<br>- [EVIDENCE] src/pipeline/link.py:L46-L48 |
| `time.event_window.pre_hours` | `72` | link | Pre-event window hours. | - [EVIDENCE] configs/default.yaml:L49-L51<br>- [EVIDENCE] src/pipeline/link.py:L41-L44 |
| `time.event_window.post_hours` | `24` | link | Post-event window hours. | - [EVIDENCE] configs/default.yaml:L50-L51<br>- [EVIDENCE] src/pipeline/link.py:L41-L44 |
| `time.align_strategy.geomag_sec` | `"aggregate"` | (not referenced) | Reserved strategy; not currently used. | - [EVIDENCE] configs/default.yaml:L52-L53<br>- [EVIDENCE] docs/config_reference.md:L189-L193 |
| `time.align_strategy.geomag_min` | `"no_interpolate"` | (not referenced) | Reserved strategy; not currently used. | - [EVIDENCE] configs/default.yaml:L54-L54<br>- [EVIDENCE] docs/config_reference.md:L195-L199 |
| `time.align_strategy.aef_min` | `"no_interpolate"` | (not referenced) | Reserved strategy; not currently used. | - [EVIDENCE] configs/default.yaml:L55-L55<br>- [EVIDENCE] docs/config_reference.md:L201-L205 |
| `time.align_strategy.seismic_waveform` | `"feature_then_align"` | (not referenced) | Reserved strategy; not currently used. | - [EVIDENCE] configs/default.yaml:L56-L56<br>- [EVIDENCE] docs/config_reference.md:L207-L210 |

## seismic
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `seismic.feature_interval_sec` | `60` | standard | Window size for seismic feature aggregation. | - [EVIDENCE] configs/default.yaml:L58-L59<br>- [EVIDENCE] src/pipeline/standard.py:L460-L491 |

## preprocess (general)
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `preprocess.batch_rows` | `30000` | standard | Batch size for parquet scanning and cleaning. | - [EVIDENCE] configs/default.yaml:L61-L62<br>- [EVIDENCE] src/pipeline/standard.py:L37-L42 |

### preprocess.geomag
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `preprocess.geomag.detrend.method` | `"linear"` | standard | Detrend method for geomag. | - [EVIDENCE] configs/default.yaml:L63-L66<br>- [EVIDENCE] src/pipeline/standard.py:L210-L217 |
| `preprocess.geomag.highpass.window_points` | `600` | standard | Rolling window size for highpass. | - [EVIDENCE] configs/default.yaml:L66-L68<br>- [EVIDENCE] src/pipeline/standard.py:L218-L225 |
| `preprocess.geomag.highpass.method` | `"rolling_median"` | standard | Highpass baseline method. | - [EVIDENCE] configs/default.yaml:L66-L68<br>- [EVIDENCE] src/pipeline/standard.py:L221-L227 |
| `preprocess.geomag.wavelet.name` | `"db4"` | standard | Wavelet name for denoise. | - [EVIDENCE] configs/default.yaml:L69-L70<br>- [EVIDENCE] src/pipeline/standard.py:L228-L236 |
| `preprocess.geomag.wavelet.mode` | `"soft"` | standard | Wavelet threshold mode. | - [EVIDENCE] configs/default.yaml:L71-L71<br>- [EVIDENCE] src/pipeline/standard.py:L228-L236 |
| `preprocess.geomag.wavelet.threshold_scale` | `1.0` | standard | Threshold scaling factor. | - [EVIDENCE] configs/default.yaml:L72-L72<br>- [EVIDENCE] src/pipeline/standard.py:L228-L236 |
| `preprocess.geomag.outlier.threshold` | `6.0` | standard | MAD outlier threshold. | - [EVIDENCE] configs/default.yaml:L73-L74<br>- [EVIDENCE] src/pipeline/standard.py:L278-L288 |
| `preprocess.geomag.interpolate.max_gap_points` | `10` | standard | Max gap for interpolation. | - [EVIDENCE] configs/default.yaml:L75-L76<br>- [EVIDENCE] src/pipeline/standard.py:L290-L298 |
| `preprocess.geomag.interpolate.method` | `"linear"` | standard | Interpolation method label. | - [EVIDENCE] configs/default.yaml:L76-L77<br>- [EVIDENCE] src/pipeline/standard.py:L296-L309 |
| `preprocess.geomag.lowpass.window_points` | `5` | standard | Lowpass rolling mean window. | - [EVIDENCE] configs/default.yaml:L78-L79<br>- [EVIDENCE] src/pipeline/standard.py:L313-L325 |

### preprocess.aef
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `preprocess.aef.detrend.method` | `"linear"` | standard | Detrend method for AEF. | - [EVIDENCE] configs/default.yaml:L80-L83<br>- [EVIDENCE] src/pipeline/standard.py:L210-L217 |
| `preprocess.aef.highpass.window_points` | `300` | standard | Highpass window for AEF. | - [EVIDENCE] configs/default.yaml:L83-L85<br>- [EVIDENCE] src/pipeline/standard.py:L218-L225 |
| `preprocess.aef.highpass.method` | `"rolling_median"` | standard | Highpass baseline method. | - [EVIDENCE] configs/default.yaml:L84-L86<br>- [EVIDENCE] src/pipeline/standard.py:L221-L227 |
| `preprocess.aef.wavelet.name` | `"db4"` | standard | Wavelet name for denoise. | - [EVIDENCE] configs/default.yaml:L86-L87<br>- [EVIDENCE] src/pipeline/standard.py:L228-L236 |
| `preprocess.aef.wavelet.mode` | `"soft"` | standard | Wavelet threshold mode. | - [EVIDENCE] configs/default.yaml:L88-L88<br>- [EVIDENCE] src/pipeline/standard.py:L228-L236 |
| `preprocess.aef.wavelet.threshold_scale` | `1.0` | standard | Threshold scaling factor. | - [EVIDENCE] configs/default.yaml:L89-L89<br>- [EVIDENCE] src/pipeline/standard.py:L228-L236 |
| `preprocess.aef.despike.window_points` | `5` | standard | Hampel window for despiking. | - [EVIDENCE] configs/default.yaml:L90-L91<br>- [EVIDENCE] src/pipeline/standard.py:L260-L276 |
| `preprocess.aef.despike.zscore_mad_threshold` | `6.0` | standard | Hampel threshold. | - [EVIDENCE] configs/default.yaml:L91-L92<br>- [EVIDENCE] src/pipeline/standard.py:L263-L271 |
| `preprocess.aef.outlier.threshold` | `6.0` | standard | MAD outlier threshold (AEF). | - [EVIDENCE] configs/default.yaml:L93-L94<br>- [EVIDENCE] src/pipeline/standard.py:L278-L288 |
| `preprocess.aef.interpolate.max_gap_points` | `5` | standard | Max gap for interpolation. | - [EVIDENCE] configs/default.yaml:L95-L96<br>- [EVIDENCE] src/pipeline/standard.py:L290-L298 |
| `preprocess.aef.interpolate.method` | `"linear"` | standard | Interpolation method label. | - [EVIDENCE] configs/default.yaml:L96-L97<br>- [EVIDENCE] src/pipeline/standard.py:L296-L309 |
| `preprocess.aef.lowpass.window_points` | `5` | standard | Lowpass rolling mean window. | - [EVIDENCE] configs/default.yaml:L98-L99<br>- [EVIDENCE] src/pipeline/standard.py:L313-L325 |
| `preprocess.aef.expand_minute_to_seconds.seconds` | `60` | standard | Number of seconds to expand per minute. | - [EVIDENCE] configs/default.yaml:L100-L102<br>- [EVIDENCE] src/pipeline/standard.py:L76-L88 |
| `preprocess.aef.expand_minute_to_seconds.mode` | `"centered"` | standard | Expansion mode (centered/forward). | - [EVIDENCE] configs/default.yaml:L101-L103<br>- [EVIDENCE] src/pipeline/standard.py:L98-L103 |
| `preprocess.aef.expand_minute_to_seconds.chunk_rows` | `2000` | standard | Expansion batch size. | - [EVIDENCE] configs/default.yaml:L102-L103<br>- [EVIDENCE] src/pipeline/standard.py:L105-L123 |

### preprocess.seismic_bandpass
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `preprocess.seismic_bandpass.freqmin_hz` | `0.5` | standard | Bandpass low cutoff. | - [EVIDENCE] configs/default.yaml:L104-L106<br>- [EVIDENCE] src/pipeline/standard.py:L402-L409 |
| `preprocess.seismic_bandpass.freqmax_user_hz` | `20.0` | standard | User max cutoff; capped by Nyquist ratio. | - [EVIDENCE] configs/default.yaml:L105-L107<br>- [EVIDENCE] src/pipeline/standard.py:L403-L410 |
| `preprocess.seismic_bandpass.freqmax_nyquist_ratio` | `0.45` | standard | Nyquist fraction cap for `freqmax`. | - [EVIDENCE] configs/default.yaml:L106-L107<br>- [EVIDENCE] src/pipeline/standard.py:L405-L411 |
| `preprocess.seismic_bandpass.taper_max_percentage` | `0.05` | standard | Taper percentage. | - [EVIDENCE] configs/default.yaml:L108-L109<br>- [EVIDENCE] src/pipeline/standard.py:L395-L400 |
| `preprocess.seismic_bandpass.corners` | `4` | standard | Bandpass filter order. | - [EVIDENCE] configs/default.yaml:L109-L110<br>- [EVIDENCE] src/pipeline/standard.py:L412-L422 |
| `preprocess.seismic_bandpass.zerophase` | `true` | standard | Zero-phase filtering flag. | - [EVIDENCE] configs/default.yaml:L110-L110<br>- [EVIDENCE] src/pipeline/standard.py:L412-L423 |
| `preprocess.seismic_bandpass.notch.base_hz` | `[50, 60]` | standard | Notch base frequencies. | - [EVIDENCE] configs/default.yaml:L111-L113<br>- [EVIDENCE] src/pipeline/standard.py:L430-L438 |
| `preprocess.seismic_bandpass.notch.half_width_hz` | `0.5` | standard | Notch half-width. | - [EVIDENCE] configs/default.yaml:L112-L113<br>- [EVIDENCE] src/pipeline/standard.py:L432-L438 |
| `preprocess.seismic_bandpass.notch.harmonics` | `0` | standard | Number of harmonics to notch. | - [EVIDENCE] configs/default.yaml:L113-L114<br>- [EVIDENCE] src/pipeline/standard.py:L433-L438 |

### preprocess.vlf_preprocess
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `preprocess.vlf_preprocess.freq_line_mask.base_hz` | `[50, 60]` | standard | Line noise base frequencies. | - [EVIDENCE] configs/default.yaml:L116-L117<br>- [EVIDENCE] src/pipeline/standard.py:L598-L607 |
| `preprocess.vlf_preprocess.freq_line_mask.harmonics` | `5` | standard | Number of harmonics for line mask. | - [EVIDENCE] configs/default.yaml:L117-L118<br>- [EVIDENCE] src/pipeline/standard.py:L599-L606 |
| `preprocess.vlf_preprocess.freq_line_mask.half_width_hz` | `0.5` | standard | Half-width for line mask. | - [EVIDENCE] configs/default.yaml:L118-L119<br>- [EVIDENCE] src/pipeline/standard.py:L600-L607 |
| `preprocess.vlf_preprocess.time_median_window` | `3` | standard | Rolling median window after aggregation. | - [EVIDENCE] configs/default.yaml:L120-L120<br>- [EVIDENCE] src/pipeline/standard.py:L581-L708 |
| `preprocess.vlf_preprocess.standardize.bands_hz` | `[10, 1000, 3000, 10000]` | standard | Band edges for band power. | - [EVIDENCE] configs/default.yaml:L121-L122<br>- [EVIDENCE] src/pipeline/standard.py:L559-L577 |
| `preprocess.vlf_preprocess.standardize.freq_agg` | `"median"` | standard | Aggregation across frequency. | - [EVIDENCE] configs/default.yaml:L123-L123<br>- [EVIDENCE] src/pipeline/standard.py:L576-L578 |
| `preprocess.vlf_preprocess.standardize.time_agg` | `"median"` | standard | Aggregation across time bins. | - [EVIDENCE] configs/default.yaml:L124-L124<br>- [EVIDENCE] src/pipeline/standard.py:L576-L700 |
| `preprocess.vlf_preprocess.standardize.target_interval` | `"1min"` | standard | Target time interval for aggregation. | - [EVIDENCE] configs/default.yaml:L125-L125<br>- [EVIDENCE] src/pipeline/standard.py:L579-L700 |
| `preprocess.vlf_preprocess.background_subtract.method` | `"median"` | standard | Background subtraction method. | - [EVIDENCE] configs/default.yaml:L126-L127<br>- [EVIDENCE] src/pipeline/standard.py:L710-L724 |

## link
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `link.spatial_km` | `1000` | link | Spatial radius (km) for station filtering. | - [EVIDENCE] configs/default.yaml:L129-L130<br>- [EVIDENCE] src/pipeline/link.py:L48-L49 |
| `link.require_station_location` | `false` | link | Drop rows without lat/lon if true. | - [EVIDENCE] configs/default.yaml:L130-L131<br>- [EVIDENCE] src/pipeline/link.py:L50-L67 |

## features
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `features.rolling_window_minutes` | `30` | [UNKNOWN] | Not referenced in code paths found in this review; confirm with `rg -n "rolling_window_minutes" src`. | - [EVIDENCE] configs/default.yaml:L133-L135 |
| `features.topn_anomalies` | `50` | model | Limits anomaly list size. | - [EVIDENCE] configs/default.yaml:L134-L135<br>- [EVIDENCE] src/pipeline/model.py:L221-L236 |
| `features.anomaly_threshold` | (implicit `3.0`) | model | Z-score threshold if key missing in YAML. | - [EVIDENCE] src/pipeline/model.py:L221-L235 |
| `features.association.change_threshold` | `3.0` | model | Pre/post mean change threshold. | - [EVIDENCE] configs/default.yaml:L136-L138<br>- [EVIDENCE] src/pipeline/model.py:L16-L25 |
| `features.association.min_sources` | `2` | model | Minimum sources for co-occurrence. | - [EVIDENCE] configs/default.yaml:L137-L139<br>- [EVIDENCE] src/pipeline/model.py:L16-L25 |
| `features.association.corr_threshold` | `0.6` | model | Correlation threshold for similarity. | - [EVIDENCE] configs/default.yaml:L138-L140<br>- [EVIDENCE] src/pipeline/model.py:L16-L25 |
| `features.association.max_lag_minutes` | `30` | model | Max lag when computing cross-correlation. | - [EVIDENCE] configs/default.yaml:L139-L140<br>- [EVIDENCE] src/pipeline/model.py:L16-L25 |
| `features.association.lag_step_minutes` | `1` | model | Lag step for correlation scan. | - [EVIDENCE] configs/default.yaml:L140-L141<br>- [EVIDENCE] src/pipeline/model.py:L16-L25 |
| `features.association.min_overlap` | `30` | model | Minimum overlap points for correlation. | - [EVIDENCE] configs/default.yaml:L141-L142<br>- [EVIDENCE] src/pipeline/model.py:L16-L25 |
| `features.association.min_points` | `20` | model | Minimum points for z-score. | - [EVIDENCE] configs/default.yaml:L142-L143<br>- [EVIDENCE] src/pipeline/model.py:L16-L25 |
| `features.association.topn_pairs` | `50` | model | Top-N correlated pairs stored. | - [EVIDENCE] configs/default.yaml:L143-L144<br>- [EVIDENCE] src/pipeline/model.py:L16-L27 |

## vlf
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `vlf.band_edges_hz` | `[10, 1000, 3000, 10000]` | standard | Fallback band edges if preprocess standardize not set. | - [EVIDENCE] configs/default.yaml:L146-L147<br>- [EVIDENCE] src/pipeline/standard.py:L559-L564 |
| `vlf.preview.max_time_bins` | `200` | ingest | Preview image time cap. | - [EVIDENCE] configs/default.yaml:L148-L149<br>- [EVIDENCE] src/pipeline/ingest.py:L127-L129 |
| `vlf.preview.max_freq_bins` | `200` | ingest | Preview image frequency cap. | - [EVIDENCE] configs/default.yaml:L149-L150<br>- [EVIDENCE] src/pipeline/ingest.py:L128-L129 |

## storage
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `storage.parquet.compression` | `"zstd"` | store/parquet | Parquet compression codec. | - [EVIDENCE] configs/default.yaml:L152-L155<br>- [EVIDENCE] src/store/parquet.py:L53-L56 |
| `storage.parquet.partition_cols` | `["station_id", "date"]` | store/parquet | Partition columns for parquet datasets. | - [EVIDENCE] configs/default.yaml:L154-L155<br>- [EVIDENCE] src/store/parquet.py:L58-L63 |
| `storage.parquet.batch_rows` | `30000` | store/parquet | Batch size for parquet writes. | - [EVIDENCE] configs/default.yaml:L155-L156<br>- [EVIDENCE] src/store/parquet.py:L41-L50 |
| `storage.zarr.compressor` | `"zstd"` | [UNKNOWN] | No usage located in pipeline code; confirm by searching for `build_compressor` usage. | - [EVIDENCE] configs/default.yaml:L157-L158<br>- [EVIDENCE] src/store/zarr_utils.py:L1-L5 |

## api
| Key | Default | Used By | Behavior / Notes | Evidence |
| --- | --- | --- | --- | --- |
| `api.host` | `"0.0.0.0"` | (operator) | Used when starting `uvicorn`; not read by app code. | - [EVIDENCE] configs/default.yaml:L160-L162<br>- [EVIDENCE] README.md:L133-L137 |
| `api.port` | `8000` | (operator) | Used when starting `uvicorn`; not read by app code. | - [EVIDENCE] configs/default.yaml:L160-L162<br>- [EVIDENCE] README.md:L133-L137 |
