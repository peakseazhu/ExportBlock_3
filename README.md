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
- Geomag: IAGA2002 `*.sec` (minute files can be enabled via `paths.geomag.read_mode`)
- AEF: IAGA2002 `*.min` (minute values can be expanded to seconds in standard stage)
- Seismic: MiniSEED `*.seed` + StationXML (optional `.mseed` via config), SAC optional
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
- `preprocess`: per-source cleaning params (geomag/aef wavelet+detrend, seismic bandpass, VLF preprocess)
- `link`: spatial radius
- `features`: anomaly thresholds + association params

## Pipeline Stages

The pipeline must follow the strict order:

```
manifest -> ingest -> raw -> standard -> spatial -> link -> features -> model -> plots
```

Stage meanings (short):
- manifest: scan files and record manifest metadata.
- ingest: parse raw files into structured tables (no event filtering).
- raw: build raw index for original files to support `/raw/query`.
- standard: per-source cleaning + standardized series (geomag/aef cleaned series, seismic rms/mean_abs, VLF band power/peak).
- spatial: build station index and spatial DQ.
- link: event window + spatial join into linked dataset.
- features: extract stats + signal features (including geomag gradients, VLF peaks, seismic arrival proxies).
- model: score anomalies with z-score thresholds.
- plots: generate Plotly figures for UI.

Run all stages (demo):

```bash

python scripts/pipeline_run.py --stages manifest,ingest,raw,standard,spatial,link,features,model,plots --config configs/default.yaml --event_id eq_20200912_024411

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
Full cleaning parameters live under `preprocess.<source>` / `preprocess.seismic_bandpass` / `preprocess.vlf_preprocess`.
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
outputs/ingest/seismic_files/                  # seismic waveform cache (not for API query)
outputs/raw/index/source=<source>/station_id=<id>/part-*.parquet # raw index for original files
outputs/raw/vlf_catalog.parquet
outputs/raw/vlf/                               # VLF Zarr cubes (raw spectrogram)
outputs/standard/source=<source>/station_id=<id>/date=YYYY-MM-DD/part-*.parquet
outputs/linked/<event_id>/aligned.parquet
outputs/features/<event_id>/features.parquet
outputs/features/<event_id>/association_changes.parquet
outputs/features/<event_id>/association_similarity.parquet
outputs/features/<event_id>/association.json
outputs/features/<event_id>/anomaly.parquet
outputs/plots/html/<event_id>/plot_*.html
outputs/events/<event_id>/reports/event_summary.md
outputs/events/<event_id>/event_bundle.zip
```

## API & UI

Run API:

```bash
uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000
```

  Example queries:
  ```
  GET /raw/summary?source=geomag
  GET /raw/query?source=geomag&start=2020-01-31&end=2020-02-01
  GET /raw/query?source=aef&start=2020-09-10&end=2020-09-12
  GET /raw/query?source=seismic&start=2020-09-10&end=2020-09-12&station_id=NET.STA..BHZ
  GET /raw/query?source=vlf&start=2020-09-10T00:00:00Z&end=2020-09-11T00:00:00Z
  GET /raw/vlf/slice?station_id=KAK&start=2020-09-10T00:00:00Z&end=2020-09-10T01:00:00Z&max_time=200&max_freq=128
  GET /standard/query?source=geomag&lat_min=30&lat_max=40&lon_min=130&lon_max=150
  GET /events
  GET /events/<event_id>/linked
  GET /events/<event_id>/features
  GET /events/<event_id>/anomaly
  GET /events/<event_id>/association
  GET /events/<event_id>/plots?kind=aligned_timeseries
  GET /events/<event_id>/export?format=csv&include_raw=true
  GET /events/<event_id>/seismic/export?format=csv
  GET /events/<event_id>/vlf/export?station_id=KAK&format=json
  ```

  Time parameters (`start`/`end`) accept ISO8601, date-only (`YYYY-MM-DD`), or Unix epoch seconds/milliseconds.
  `source=vlf` returns catalog rows (`ts_start_ns`/`ts_end_ns`) rather than long-table samples.
  `/raw/vlf/slice` returns downsampled spectrogram slices for small windows.
  Raw queries read original files by index; large windows should pass `limit` or narrower time ranges.

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
```自测示例
RAW:
//KAK、KNY、MMB
http://127.0.0.1:8000/raw/query?source=geomag&start=2020-09-11&end=2020-09-12&station_id=KAK&limit=5000

http://127.0.0.1:8000/raw/query?source=aef&start=2020-09-11&end=2020-09-12&station_id=KAK&limit=100

//II.ERM.00.BHZ、JP.JKA..BHZ、JP.JMM..BHZ、JP.JSD..BHZ、JP.JTM..BHZ JP.JYT..BHZ
http://127.0.0.1:8000/raw/query?source=seismic&start=2020-09-11&end=2020-09-12&station_id=II.ERM.00.BHZ&limit=100

http://127.0.0.1:8000/raw/query?source=vlf&start=2020-09-11&end=2020-09-12&station_id=MOS&limit=100

2020-09-10T00:00:00Z
http://127.0.0.1:8000/raw/vlf/slice?station_id=MOS&start=2020-09-10T00%3A00%3A00Z&end=2020-09-10T01%3A00%3A00Z&max_time=200&max_freq=128&max_files=1

STANDARD:
//KAK、KNY、MMB
http://127.0.0.1:8000/standard/query?source=geomag&start=2020-09-11&end=2020-09-12&limit=5000

http://127.0.0.1:8000/standard/query?source=aef&start=2020-09-11&end=2020-09-12&station_id=KAK&limit=5000

//II.ERM.00.BHZ、JP.JKA..BHZ、JP.JMM..BHZ、JP.JSD..BHZ、JP.JTM..BHZ JP.JYT..BHZ
http://127.0.0.1:8000/standard/query?source=seismic&start=2020-09-11&end=2020-09-12&station_id=II.ERM.00.BHZ&limit=1000

http://127.0.0.1:8000/standard/query?source=vlf&start=2020-09-11&end=2020-09-12&station_id=MOS&limit=1000

RAW_SUMMARY:
http://127.0.0.1:8000/raw/summary?source=geomag
http://127.0.0.1:8000/raw/summary?source=aef
http://127.0.0.1:8000/raw/summary?source=seismic
http://127.0.0.1:8000/raw/summary?source=vlf
STANDARD_SUMMARY:
http://127.0.0.1:8000/standard/summary?source=geomag
http://127.0.0.1:8000/standard/summary?source=aef
http://127.0.0.1:8000/standard/summary?source=seismic
http://127.0.0.1:8000/standard/summary?source=vlf

LINKED:
http://127.0.0.1:8000/events/eq_20200912_024411/linked?limit=5000

FEATURES:
http://127.0.0.1:8000/events/eq_20200912_024411/features

ANOMALY:返回未空即[]，不知道为什么
http://127.0.0.1:8000/events/eq_20200912_024411/anomaly

ASSOCIATION:
http://127.0.0.1:8000/events/eq_20200912_024411/association?limit=200

EXPORT_EVENT_SEISMIC:  csv hdf5 json   2020-09-12T00:00:00ZS
http://127.0.0.1:8000/events/eq_20200912_024411/seismic/export?format=csv&start=2020-09-12T01%3A00%3A00Z&end=2020-09-12T02%3A00%3A00Z&limit=20000

EXPORT_EVENT_VLF:  csv hdf5 json   2020-09-12T01:00:00Z

EXPORT_EVENT:  2020-09-12T01:00:00Z  csv json
http://127.0.0.1:8000/events/eq_20200912_024411/export?format=csv&start=2020-09-12T01%3A00%3A00Z&end=2020-09-12T02%3A00%3A00Z&include_raw=false&raw_limit=20000&raw_seismic_format=csv&raw_vlf_format=json&raw_vlf_station_id=MOS&raw_vlf_max_time=200&raw_vlf_max_freq=128&raw_vlf_max_files=1

UI
http://127.0.0.1:8000/ui

```

```
RAW:
curl -X 'GET' \
  'http://127.0.0.1:8000/raw/query?source=geomag&start=2020-09-11&end=2020-09-12&station_id=KAK&limit=5000' \
  -H 'accept: application/json'

curl -X 'GET' \
  'http://127.0.0.1:8000/raw/query?source=aef&start=2020-09-11&end=2020-09-12&station_id=KAK&limit=100' \
  -H 'accept: application/json'

curl -X 'GET' \
  'http://127.0.0.1:8000/raw/query?source=seismic&start=2020-09-11&end=2020-09-12&station_id=II.ERM.00.BHZ&limit=100' \
  -H 'accept: application/json'

curl -X 'GET' \
  'http://127.0.0.1:8000/raw/query?source=vlf&start=2020-09-11&end=2020-09-12&station_id=MOS&limit=100' \
  -H 'accept: application/json'

curl -X 'GET' \
  'http://127.0.0.1:8000/raw/vlf/slice?station_id=MOS&start=2020-09-10T00%3A00%3A00Z&end=2020-09-10T01%3A00%3A00Z&max_time=200&max_freq=128&max_files=1' \
  -H 'accept: application/json'


STANDARD:
curl -X 'GET' \
  'http://127.0.0.1:8000/standard/query?source=geomag&start=2020-09-11&end=2020-09-12&limit=5000' \
  -H 'accept: application/json'

curl -X 'GET' \
  'http://127.0.0.1:8000/standard/query?source=aef&start=2020-09-11&end=2020-09-12&station_id=KAK&limit=5000' \
  -H 'accept: application/json'

curl -X 'GET' \
  'http://127.0.0.1:8000/standard/query?source=seismic&start=2020-09-11&end=2020-09-12&station_id=II.ERM.00.BHZ&limit=1000' \
  -H 'accept: application/json'
curl -X 'GET' \
  'http://127.0.0.1:8000/standard/query?source=vlf&start=2020-09-11&end=2020-09-12&station_id=MOS&limit=1000' \
  -H 'accept: application/json'
```
