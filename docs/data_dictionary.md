# 数据字典

## 统一长表字段（Raw/Standard/Linked/Features）
- `ts_ms`：UTC 毫秒时间戳
- `source`：`geomag | seismic | aef | vlf`
- `station_id`：
  - 地磁/AEF：IAGA CODE（如 `KAK`）
  - 地震：`NET.STA.LOC.CHAN`
- `channel`：如 `X/Y/Z/F` 或 `BHZ_rms` 等
- `value`：主数值
- `lat/lon/elev`：WGS84 坐标（允许 NaN）
- `quality_flags`：质量标记（JSON）
- `proc_stage`：`ingest|raw|standard|linked|features|model|plots`
- `proc_version`：流水线版本
- `params_hash`：参数快照哈希

## VLF Raw（频谱矩阵）
- `epoch_ns`：TT2000 转换后的纳秒时间轴
- `freq_hz`：频率轴
- `ch1/ch2`：频谱功率（`V^2/Hz`）

## quality_flags 说明
- `is_missing` / `missing_reason`
- `is_interpolated` / `interp_method`
- `is_outlier` / `outlier_method` / `threshold`
- `is_filtered` / `filter_type` / `filter_params`
- `station_match`
- `note`
