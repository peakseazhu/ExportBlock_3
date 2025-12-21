PIPELINE_VERSION = "0.1.0"

BASE_COLUMNS = [
    "ts_ms",
    "source",
    "station_id",
    "channel",
    "value",
    "lat",
    "lon",
    "elev",
    "quality_flags",
    "proc_stage",
    "proc_version",
    "params_hash",
]

QUALITY_FLAG_KEYS = [
    "is_missing",
    "missing_reason",
    "is_interpolated",
    "interp_method",
    "is_outlier",
    "outlier_method",
    "threshold",
    "is_filtered",
    "filter_type",
    "filter_params",
    "station_match",
    "note",
]
