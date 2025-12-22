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

## Features 输出（示例）
- 统计类：`mean`, `std`, `variance`, `min`, `max`, `peak`, `rms`, `count`
- 地磁梯度：`gradient_abs_mean`, `gradient_abs_max`
- 地震到时（近似）：`p_arrival_offset_s`, `s_arrival_offset_s`

说明：
- `p_arrival_offset_s` / `s_arrival_offset_s` 为简化估计值（相对震源时刻的秒偏移）。
- VLF 峰值频率来自 standard 阶段的 `ch1_peak_freq` / `ch2_peak_freq`，在 features 中以统计特征体现。

## quality_flags 说明
- `is_missing` / `missing_reason`
- `is_interpolated` / `interp_method`
- `is_outlier` / `outlier_method` / `threshold`
- `is_filtered` / `filter_type` / `filter_params`
- `station_match`
- `note`
