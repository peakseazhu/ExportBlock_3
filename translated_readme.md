
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
- 地磁/AEF：IAGA2002 `*.min` / `*.sec`
- 地震波：MiniSEED + StationXML，SAC 可选
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
- `preprocess`：异常值、插值、滤波
- `link`：空间半径
- `features`：异常阈值

## 管道阶段

管道必须按照严格的顺序执行：

```
manifest -> ingest -> raw -> standard -> spatial -> link -> features -> model -> plots
```

运行所有阶段（演示）：

```bash
python scripts/pipeline_run.py   --stages manifest,ingest,raw,standard,spatial,link,features,model,plots   --config configs/demo.yaml   --event_id eq_20200101_000000
```
manifest：扫描数据文件并生成清单（审计/可追溯），写入 outputs/manifests。
ingest：解析原始数据为结构化表；IAGA/AEF/地震索引写入 outputs/ingest，VLF 频谱写入 outputs/raw/vlf。
raw：把 ingest 数据标记为 raw 并写入 outputs/raw，同时复制波形文件。
standard：清洗/插值/滤波并生成标准化表，写入 outputs/standard。
spatial：生成站点空间索引与报告，写入 outputs/reports/spatial_index。
link：按事件窗口与空间半径对齐/筛选，写入 outputs/linked/<event_id>。
features：统计特征（mean/std/min/max/rms 等），写入 outputs/features/<event_id>。
model：异常检测与规则输出，写入 anomaly.parquet 和 outputs/models。
plots：生成图表 JSON/HTML，写入 outputs/plots/spec|html/<event_id>。

事件关联数据集：link 阶段写入 aligned.parquet（API：/events/{id}/linked）。
特征值：features 阶段写入 features.parquet（API：/events/{id}/features）。
异常/关联模型输出：model 阶段写入 anomaly.parquet（API：/events/{id}/anomaly）。
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
outputs/raw/                                   # raw parquet + vlf catalog
outputs/standard/                              # cleaned parquet
outputs/linked/<event_id>/aligned.parquet
outputs/features/<event_id>/features.parquet
outputs/features/<event_id>/anomaly.parquet
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
GET /raw/query?source=geomag&start=2020-01-01T00:00:00Z&end=2020-01-02T00:00:00Z
GET /standard/query?source=geomag&lat_min=30&lat_max=40&lon_min=130&lon_max=150
GET /events
GET /events/<event_id>/linked
GET /events/<event_id>/features
GET /events/<event_id>/anomaly
GET /events/<event_id>/plots?kind=aligned_timeseries
GET /events/<event_id>/export?format=csv&start=...&end=...
```

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
