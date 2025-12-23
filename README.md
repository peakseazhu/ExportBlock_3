# ExportBlock-3: Multi-Source Earthquake Data Pipeline

This project implements the full pipeline defined in `plan_final_revised_v9.md`, covering
ingest, raw/standard storage, event linking, feature extraction, anomaly scoring, plots,
finalization, and a FastAPI/HTML UI for querying and visualization.

## Data Layout (Required)

Place data in the repository root using the existing directory names:

```
地磁/                      # IAGA2002 (geomag, sec/min)
地震波/                    # MiniSEED/SAC + stations_inventory.xml
大气电磁信号/大气电场/      # AEF (IAGA2002)
大气电磁信号/电磁波动vlf/   # VLF CDF
```

Supported formats:
- Geomag/AEF: IAGA2002 `*.min` / `*.sec`
- Seismic: MiniSEED + StationXML, SAC optional
- VLF: CDF frequency product (see `plan_final_revised_v9.md` for variable names)

## Installation

Using conda:

```bash
conda env create -f environment.yml
conda activate exportblock-3
```

Or in the current environment:

```bash
pip install -r requirements.txt
```

## Configuration

Main configs:
- `configs/default.yaml`: full run
- `configs/demo.yaml`: lightweight demo run
- `configs/local.yaml`: optional overrides (ignored by git)

Key sections:
- `paths`: data locations and file patterns
- `events`: event list with `event_id`, `origin_time_utc`, `lat`, `lon`
- `time`: alignment window and interval
- `preprocess`: outlier, interpolation, filter
- `link`: spatial radius
- `features`: anomaly thresholds

## Pipeline Stages

The pipeline must follow the strict order:

```
manifest -> ingest -> raw -> standard -> spatial -> link -> features -> model -> plots
```

Stage meanings (short):
- manifest: scan files and record manifest metadata.
- ingest: parse raw files into structured tables (no event filtering).
- raw: persist structured raw data for `/raw/query`.
- standard: denoise/interpolate/filter and persist cleaned data.
- spatial: build station index and spatial DQ.
- link: event window + spatial join into linked dataset.
- features: extract stats + signal features (including geomag gradients, VLF peaks, seismic arrival proxies).
- model: score anomalies with z-score thresholds.
- plots: generate Plotly figures for UI.

Run all stages (demo):

```bash
python scripts/pipeline_run.py \
  --stages manifest,ingest,raw,standard,spatial,link,features,model,plots \
  --config configs/demo.yaml \
  --event_id eq_20200101_000000
```
设定批大小
推荐在配置文件中设置（写入与清洗可分别控制）：
```yaml
preprocess:
  batch_rows: 50000
storage:
  parquet:
    batch_rows: 30000
```
如需临时覆盖，可使用环境变量（可选）：
PowerShell 
```bash
$env:PARQUET_BATCH_ROWS = "80000"
python scripts/pipeline_run.py --stages manifest,ingest,raw,standard,spatial,link,features,model,plots --config configs/default.yaml --event_id eq_20200912_024411
```
cmd 用法（可选）：
```bash
set PARQUET_BATCH_ROWS=80000
python scripts/pipeline_run.py --stages manifest,ingest,raw,standard,spatial,link,features,model,plots --config configs/default.yaml --event_id eq_20200912_024411
```
Finalize and bundle:

```bash
python scripts/finalize_event_package.py --event_id  eq_20200912_024411 --strict
python scripts/make_event_bundle.py --event_id eq_20200912_024411
```

```bash
python scripts/finalize_event_package.py --event_id eq_20200101_000000 --strict
python scripts/make_event_bundle.py --event_id eq_20200101_000000
```

Full run uses `configs/default.yaml` and the event id in that config.

## Outputs

Key outputs:

```
outputs/manifests/                             # manifest json
outputs/ingest/                                # ingest parquet
outputs/raw/                                   # raw parquet + vlf catalog
outputs/standard/                              # cleaned parquet
outputs/linked/<event_id>/aligned.parquet
outputs/features/<event_id>/features.parquet
outputs/features/<event_id>/anomaly.parquet
outputs/plots/html/<event_id>/plot_*.html
outputs/events/<event_id>/reports/event_summary.md
outputs/events/<event_id>/event_bundle.zip
```

## API & UI

Run API:

```bash
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

Example queries:

```
GET /raw/summary?source=geomag
GET /raw/query?source=geomag&start=2020-01-31&end=2020-02-01
GET /standard/query?source=geomag&lat_min=30&lat_max=40&lon_min=130&lon_max=150
GET /events
GET /events/<event_id>/linked
GET /events/<event_id>/features
GET /events/<event_id>/anomaly
GET /events/<event_id>/plots?kind=aligned_timeseries
GET /events/<event_id>/export?format=csv&start=...&end=...
```

Time parameters (`start`/`end`) accept ISO8601, date-only (`YYYY-MM-DD`), or Unix epoch seconds/milliseconds.

UI:
- `GET /ui`
- `GET /ui/events/<event_id>`

## Tests

```bash
pytest
```

## Notes

- VLF Raw data is stored as Zarr; compression is disabled for compatibility with Zarr v3.
- `outputs/` is generated at runtime and should not be committed.
