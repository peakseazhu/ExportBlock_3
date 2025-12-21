# API 说明（FastAPI）

## 基础
- `GET /health`：健康检查

## Raw/Standard 查询
- `GET /raw/query?source=geomag|aef|seismic|vlf&start=<ISO>&end=<ISO>&station_id=<id>&lat_min=&lat_max=&lon_min=&lon_max=&limit=5000`
- `GET /standard/query?source=geomag|aef|seismic|vlf&start=<ISO>&end=<ISO>&station_id=<id>&lat_min=&lat_max=&lon_min=&lon_max=&limit=5000`

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
