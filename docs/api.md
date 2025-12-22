# API 说明（FastAPI）

## 基础
- `GET /health`：健康检查
- 提示：`0.0.0.0` 仅是服务绑定地址，浏览器访问建议使用 `http://127.0.0.1:8000/docs`

## Raw/Standard 查询
- `GET /raw/query?source=geomag|aef|seismic|vlf&start=<ISO>&end=<ISO>&station_id=<id>&lat_min=&lat_max=&lon_min=&lon_max=&limit=5000`
- `GET /standard/query?source=geomag|aef|seismic|vlf&start=<ISO>&end=<ISO>&station_id=<id>&lat_min=&lat_max=&lon_min=&lon_max=&limit=5000`
- `GET /raw/summary?source=geomag|aef|seismic|vlf`：返回行数与时间范围（用于确认可查询时间窗）
- `GET /standard/summary?source=geomag|aef|seismic|vlf`：返回行数与时间范围（用于确认可查询时间窗）

时间参数说明：
- 支持 ISO8601（如 `2020-01-31T22:40:00Z`）
- 支持日期简写（如 `2020-01-31`）
- 支持 Unix 时间戳（秒/毫秒，长度为 10 或 13）

查询返回头（raw/standard）：
- `X-Result-Count`：过滤后行数
- `X-Source-Rows`：原始数据行数
- `X-Source-Time-Range`：数据覆盖范围（UTC）

## 事件级
- `GET /events`：事件列表（默认仅 READY）
- `GET /events/{event_id}/linked`
- `GET /events/{event_id}/features`
- `GET /events/{event_id}/anomaly`
- `GET /events/{event_id}/plots?kind=aligned_timeseries|station_map|filter_effect|vlf_spectrogram`
- `GET /events/{event_id}/export?format=csv|hdf5&start=<ISO>&end=<ISO>`

## UI
- `GET /ui`：事件列表
- `GET /ui/events/{event_id}`：事件详情
