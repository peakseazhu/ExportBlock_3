# API 说明（FastAPI）

## 基础
- `GET /health`：健康检查
- 提示：`0.0.0.0` 仅是服务绑定地址，浏览器访问建议使用 `http://127.0.0.1:8000/docs`

## Raw/Standard 查询
- `GET /raw/query?source=geomag|aef|seismic|vlf&start=<ISO>&end=<ISO>&station_id=<id>&lat_min=&lat_max=&lon_min=&lon_max=&limit=5000`
- `GET /raw/vlf/slice?station_id=<id>&start=<ISO>&end=<ISO>&freq_min=&freq_max=&max_time=400&max_freq=256&max_files=1`
- `GET /standard/query?source=geomag|aef|seismic|vlf&start=<ISO>&end=<ISO>&station_id=<id>&lat_min=&lat_max=&lon_min=&lon_max=&limit=5000`
- `GET /raw/summary?source=geomag|aef|seismic|vlf`：返回行数与时间范围（用于确认可查询时间窗）
- `GET /standard/summary?source=geomag|aef|seismic|vlf`：返回行数与时间范围（用于确认可查询时间窗）
补充说明：
- `source=vlf` 的 raw 查询返回 `vlf_catalog.parquet` 行（包含 `ts_start_ns/ts_end_ns`），不返回长表样本。
- raw 查询基于 `outputs/raw/index` 索引读取原始文件，窗口过大建议配合 `limit` 或缩小时间范围。
- `/raw/vlf/slice` 返回下采样后的频谱片段（时间×频率），用于小窗口可视化或导出。

时间参数说明：
- 支持 ISO8601（如 `2020-01-31T22:40:00Z`）
- 支持日期简写（如 `2020-01-31`）
- 支持 Unix 时间戳（秒/毫秒，长度为 10 或 13）

查询返回头（raw/standard）：
- `X-Result-Count`：过滤后行数
- `X-Source-Rows`：本次返回行数（受 limit 影响）
- `X-Source-Time-Range`：本次返回数据覆盖范围（UTC）

## 事件级
- `GET /events`：事件列表（默认仅 READY）
- `GET /events/{event_id}/linked`
- `GET /events/{event_id}/features`
- `GET /events/{event_id}/anomaly`
- `GET /events/{event_id}/plots?kind=aligned_timeseries|station_map|filter_effect|vlf_spectrogram`
- `GET /events/{event_id}/export?format=csv|hdf5&include_raw=false&start=<ISO>&end=<ISO>`
- `GET /events/{event_id}/seismic/export?format=csv|hdf5|json`
- `GET /events/{event_id}/vlf/export?format=json|npz`

## UI
- `GET /ui`：事件列表
- `GET /ui/events/{event_id}`：事件详情
