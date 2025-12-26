
# ExportBlock-3: 多源地震数据管道

本项目实现了在 `plan_final_revised_v9.md` 中定义的完整管道，涵盖了数据摄取、原始/标准存储、事件链接、特征提取、异常评分、绘图、最终处理和用于查询和可视化的 FastAPI/HTML UI。

## 数据布局（必需）

将数据放置在仓库根目录，使用现有的目录名称：

```
地磁/                      # IAGA2002 (geomag, sec/min)
地震波/                    # MiniSEED/SAC + stations_inventory.xml
大气电磁信号/大气电场/      # AEF (IAGA2002)
大气电磁信号/电磁波动vlf/   # VLF CDF
```

支持的格式：
- 地磁：IAGA2002 `*.sec`（分钟级可通过 `paths.geomag.read_mode` 启用）
- AEF：IAGA2002 `*.min`（可在 standard 阶段展开为秒级常量段）
- 地震波：MiniSEED `*.seed` + StationXML（如为 `.mseed` 需配置），SAC 可选
- VLF：CDF 频率产品（请参见 `plan_final_revised_v9.md` 了解变量名称）

## 安装

使用 conda：

```bash
conda env create -f environment.yml
conda activate exportblock-3
```

或在当前环境中：

```bash
pip install -r requirements.txt
```

## 配置

主要配置：
- `configs/default.yaml`：完整运行
- `configs/demo.yaml`：轻量级演示运行
- `configs/local.yaml`：可选覆盖（git 忽略）

关键部分：
- `paths`：数据位置和文件模式
- `events`：包含 `event_id`、`origin_time_utc`、`lat`、`lon` 的事件列表
- `time`：对齐窗口和间隔
- `preprocess`：按数据源清洗参数（geomag/aef 小波+去趋势，seismic 带通，VLF 频谱预处理）
- `link`：空间半径
- `features`：异常阈值

## 管道阶段

管道必须按照严格的顺序执行：

```
manifest -> ingest -> raw -> standard -> spatial -> link -> features -> model -> plots
```

运行所有阶段（演示）：

```bash
python scripts/pipeline_run.py --stages manifest,ingest,raw,standard,spatial,link,features,model,plots --config configs/default.yaml --event_id eq_20200912_024411

python scripts/pipeline_run.py   --stages manifest,ingest,raw,standard,spatial,link,features,model,plots   --config configs/demo.yaml   --event_id eq_20200101_000000
```
manifest：扫描数据文件并生成清单（审计/可追溯），写入 outputs/manifests。
ingest：解析原始数据为结构化表；IAGA/AEF/地震索引写入 outputs/ingest，地震波形缓存到 outputs/ingest/seismic_files，VLF 频谱写入 outputs/raw/vlf。
raw：生成原始文件索引，写入 outputs/raw/index/source=<source>/station_id=<id>/part-*.parquet，用于 raw 查询。
standard：按数据源清洗后生成标准化序列（geomag/aef 清洗序列、seismic RMS/mean_abs、VLF 频带功率/峰值），写入 outputs/standard/source=<source>/station_id=<id>/date=YYYY-MM-DD/part-*.parquet。
spatial：生成站点空间索引与报告，写入 outputs/reports/spatial_index。
link：按事件窗口与空间半径对齐/筛选，写入 outputs/linked/<event_id>。
features：统计特征（mean/std/min/max/rms 等），写入 outputs/features/<event_id>。
model??????????????????????????????????????? anomaly.parquet + association_*.parquet/association.json ??? outputs/models???
plots：生成图表 JSON/HTML，写入 outputs/plots/spec|html/<event_id>。

事件关联数据集：link 阶段写入 aligned.parquet（API：/events/{id}/linked）。
特征值：features 阶段写入 features.parquet（API：/events/{id}/features）。
??????/?????????????????????model ???????????? anomaly.parquet + association_*.parquet???API???events/{id}/anomaly, /events/{id}/association??????
finalize_event_package 会把上述内容（link、features、model）汇总到 outputs/events/<event_id>/。
参考：features.py (line 70) link.py (line 29)
make_event_bundle.py在 finalize 后打包事件为 zip 用于归档/交付。
完成并打包：

```bash
python scripts/finalize_event_package.py --event_id eq_20200101_000000 --strict
python scripts/make_event_bundle.py --event_id eq_20200101_000000
```

完整运行使用 `configs/default.yaml` 和该配置中的事件 ID。

## 输出

主要输出：

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
outputs/features/<event_id>/anomaly.parquet
outputs/features/<event_id>/association_changes.parquet
outputs/features/<event_id>/association_similarity.parquet
outputs/features/<event_id>/association.json
outputs/plots/html/<event_id>/plot_*.html
outputs/events/<event_id>/reports/event_summary.md
outputs/events/<event_id>/event_bundle.zip
```

## API 和 UI

运行 API：

```bash
uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

示例查询：

```
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

时间参数说明：支持 ISO8601、日期简写（YYYY-MM-DD）或 Unix 时间戳（秒/毫秒）。
`source=vlf` 的 raw 查询返回 catalog 行（`ts_start_ns/ts_end_ns`），不返回长表样本。
raw 查询会按索引读取原始文件，窗口过大时建议配合 `limit` 或收窄时间范围。

UI：
- `GET /ui`
- `GET /ui/events/<event_id>`

## 测试

```bash
pytest
```

## 注意事项

- VLF 原始数据存储为 Zarr；为了与 Zarr v3 兼容，压缩功能已禁用。
- `outputs/` 在运行时生成，不应提交。
