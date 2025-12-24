# 配置参考（configs/default.yaml / configs/demo.yaml）

## 配置文件说明
`configs/default.yaml` 作为完整运行的基准配置，`configs/demo.yaml` 用于快速演示与小样本验证。当前运行入口在 `scripts/pipeline_run.py`，通过 `--config` 指定配置文件路径。

示例：
```bash
python scripts/pipeline_run.py --config configs/demo.yaml --stages manifest,ingest,raw,standard,link,features,model,plots
```

## 字段说明
### pipeline
#### pipeline.version
- 类型/必填/默认/范围：string，必填；默认 `"0.1.0"`；建议语义化版本号。
- 作用与影响/读取位置：写入 `proc_version` 与事件元数据；`src/pipeline/ingest.py::run_ingest`、`src/pipeline/raw.py::run_raw`、`src/pipeline/standard.py::run_standard`、`src/pipeline/link.py::run_link`。
- 典型场景与示例：发布新版本或结果对比时改为 `"0.2.0"`。
- 注意事项：只影响元数据记录，不改变算法流程。

### paths
#### paths.geomag.root
- 类型/必填/默认/范围：string，必填；默认 `"地磁"`；相对或绝对路径均可。
- 作用与影响/读取位置：定位 IAGA2002 地磁数据目录；`src/pipeline/manifest.py::build_manifest`、`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：数据目录移动到 `data/geomag` 时设为 `"data/geomag"`。
- 注意事项：路径不存在会导致无数据进入后续阶段。

#### paths.geomag.sec_patterns
- 类型/必填/默认/范围：string[]，可选；默认 `["*.sec"]`；glob 模式。
- 作用与影响/读取位置：秒级地磁文件扫描范围；`src/pipeline/manifest.py::build_manifest`、`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：只读取秒级时保持默认；如文件后缀不同可改为 `["*.SEC"]`。
- 注意事项：与 `read_mode` 联动，未启用时不会被读取。
#### paths.geomag.min_patterns
- 类型/必填/默认/范围：string[]，可选；默认 `["*.min"]`；glob 模式。
- 作用与影响/读取位置：分钟级地磁文件扫描范围；`src/pipeline/manifest.py::build_manifest`、`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：需要分钟数据时设为 `["*.min"]` 并将 `read_mode` 设为 `min` 或 `both`。
- 注意事项：分钟与秒级混读会造成时间粒度混杂，建议分开处理。
#### paths.geomag.read_mode
- 类型/必填/默认/范围：string，可选；默认 `"sec"`；取值 `sec|min|both`。
- 作用与影响/读取位置：决定 ingest 读取哪种粒度的地磁数据；`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：秒级分析设为 `"sec"`；仅分钟数据时设为 `"min"`。
- 注意事项：`both` 会合并输出为同一 source，需自行评估是否接受混合粒度。

#### paths.aef.root
- 类型/必填/默认/范围：string，必填；默认 `"大气电磁信号/大气电场/kak202001-202010daef.min"`。
- 作用与影响/读取位置：定位 AEF 数据文件目录；`src/pipeline/manifest.py::build_manifest`、`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：更换 AEF 数据批次时更新为对应目录。
- 注意事项：AEF 目录通常包含单批次文件，指向上层目录会导致多批次混合。

#### paths.aef.min_patterns
- 类型/必填/默认/范围：string[]，可选；默认 `["*.min"]`。
- 作用与影响/读取位置：AEF 文件扫描；`src/pipeline/manifest.py::build_manifest`、`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：AEF 仅分钟级时保持默认。
- 注意事项：若有秒级 AEF，需要显式扩展并调整 `read_mode`。
#### paths.aef.read_mode
- 类型/必填/默认/范围：string，可选；默认 `"min"`；取值 `min|sec|both`。
- 作用与影响/读取位置：决定 ingest 读取哪种粒度的 AEF 数据；`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：分钟数据展开为秒级常量段时保持 `"min"`。
- 注意事项：`sec`/`both` 仅在存在秒级 AEF 文件时使用。

#### paths.seismic.root
- 类型/必填/默认/范围：string，必填；默认 `"地震波"`。
- 作用与影响/读取位置：地震波形与台站元数据目录；`src/pipeline/manifest.py::build_manifest`、`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：数据集中在 `data/seismic` 时设为 `"data/seismic"`。
- 注意事项：若目录下无波形文件，后续地震特征将为空。

#### paths.seismic.mseed_patterns
- 类型/必填/默认/范围：string[]，必填；默认 `["*.seed"]`。
- 作用与影响/读取位置：MiniSEED 文件扫描；`src/pipeline/manifest.py::build_manifest`、`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：若数据为 `.mseed`，需改为 `["*.mseed"]` 或追加 `["*.seed","*.mseed"]`。
- 注意事项：只读取秒级波形数据，避免混入分钟级文件。

#### paths.seismic.sac_patterns
- 类型/必填/默认/范围：string[]，必填；默认 `["*.sac"]`。
- 作用与影响/读取位置：SAC 文件仅用于原始保留与后续可选使用；`src/pipeline/manifest.py::build_manifest`、`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：若无 SAC 文件，可设为 `[]`。
- 注意事项：SAC 目前不会参与特征提取，仅保存在 ingest 缓存。

#### paths.seismic.stationxml
- 类型/必填/默认/范围：string，可选；默认 `"地震波/stations_inventory.xml"`。
- 作用与影响/读取位置：用于补充台站经纬度与高程；`src/pipeline/manifest.py::build_manifest`、`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：自定义台站文件时设为 `"metadata/stations.xml"`。
- 注意事项：缺失或无法解析将导致 `lat/lon` 为空，影响空间过滤与站点地图。

#### paths.vlf.root
- 类型/必填/默认/范围：string，必填；默认 `"大气电磁信号/电磁波动vlf/vlf"`。
- 作用与影响/读取位置：VLF CDF 文件目录；`src/pipeline/manifest.py::build_manifest`、`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：更换 VLF 数据库路径时更新该字段。
- 注意事项：目录为空将导致 VLF 特征缺失。

#### paths.vlf.patterns
- 类型/必填/默认/范围：string[]，必填；默认 `["*.cdf"]`。
- 作用与影响/读取位置：VLF 文件扫描；`src/pipeline/manifest.py::build_manifest`、`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：若命名后缀不同，调整为对应扩展名。
- 注意事项：模式不匹配会导致 VLF 完全不参与流程。

### outputs
#### outputs.root
- 类型/必填/默认/范围：string，必填；默认 `"outputs"`。
- 作用与影响/读取位置：输出目录根路径；`scripts/pipeline_run.py::main`、`src/store/paths.py::OutputPaths`。
- 典型场景与示例：多项目并行时设为 `"outputs_demo"`。
- 注意事项：FastAPI 读取的是 `OUTPUT_ROOT` 环境变量，不会自动跟随此配置。

### limits
#### limits.max_files_per_source
- 类型/必填/默认/范围：int|null，可选；默认 `null`（demo 为 `1`）；正整数或 `null`。
- 作用与影响/读取位置：限制每个数据源扫描文件数量；`src/pipeline/manifest.py::build_manifest`、`src/pipeline/ingest.py::run_ingest`。
- 典型场景与示例：快速验证时设为 `1`。
- 注意事项：值为 `0` 等同于无限制（因代码按 truthy 判断）。

#### limits.max_rows_per_source
- 类型/必填/默认/范围：int|null，可选；默认 `null`（demo 为 `5000`）。
- 作用与影响/读取位置：限制 ingest 与 standard 阶段生成的记录数；`src/pipeline/ingest.py::run_ingest`、`src/pipeline/standard.py::run_standard`。
- 典型场景与示例：低资源调试时设为 `2000`。
- 注意事项：值为 `0` 不会生效；建议使用正整数。

### events
#### events
- 类型/必填/默认/范围：list，必填；默认包含 1 条事件；每条需包含 `event_id`、`origin_time_utc`、`lat`、`lon`。
- 作用与影响/读取位置：驱动 link/features/model/plots 的事件上下文；`src/config.py::get_event`、`src/pipeline/link.py::run_link` 等。
- 典型场景与示例：批量事件可配置多条，使用 `--event_id` 选择。
- 注意事项：列表为空且未指定 `--event_id` 会抛异常。

#### events[].event_id
- 类型/必填/默认/范围：string，必填；示例 `"eq_20200912_024411"`。
- 作用与影响/读取位置：作为输出目录名与事件索引键；`src/config.py::get_event`、`src/pipeline/link.py::run_link`。
- 典型场景与示例：按日期与时间命名便于检索。
- 注意事项：必须唯一；重复会导致选择错误。

#### events[].name
- 类型/必填/默认/范围：string，可选；示例 `"2020-09-12 Japan"`。
- 作用与影响/读取位置：写入事件元数据；`src/pipeline/link.py::run_link`。
- 典型场景与示例：面向展示或报表时填写可读名称。
- 注意事项：缺失不影响流程，仅影响可读性。

#### events[].origin_time_utc
- 类型/必填/默认/范围：string，必填；ISO8601 UTC（如 `"2020-09-12T02:44:11Z"`）。
- 作用与影响/读取位置：计算事件时间窗与对齐区间；`src/pipeline/link.py::run_link`。
- 典型场景与示例：替换为实际地震起始时间。
- 注意事项：格式无效会在 `pd.Timestamp` 处报错。

#### events[].lat
- 类型/必填/默认/范围：float，必填；范围 `[-90, 90]`。
- 作用与影响/读取位置：空间过滤、站点距离计算；`src/pipeline/link.py::run_link`。
- 典型场景与示例：填入震中纬度。
- 注意事项：超出范围会导致距离计算异常或无意义。

#### events[].lon
- 类型/必填/默认/范围：float，必填；范围 `[-180, 180]`。
- 作用与影响/读取位置：空间过滤、站点距离计算；`src/pipeline/link.py::run_link`。
- 典型场景与示例：填入震中经度。
- 注意事项：经度方向错误会影响筛选结果。

#### events[].depth_km
- 类型/必填/默认/范围：float，可选；示例 `10.0`。
- 作用与影响/读取位置：写入事件元数据；`src/pipeline/link.py::run_link`。
- 典型场景与示例：用于报告展示或后续模型扩展。
- 注意事项：当前不参与计算逻辑。

#### events[].magnitude
- 类型/必填/默认/范围：float，可选；示例 `5.0`。
- 作用与影响/读取位置：写入事件元数据；`src/pipeline/link.py::run_link`。
- 典型场景与示例：用于报表或过滤。
- 注意事项：当前不参与计算逻辑。

### time
#### time.timezone
- 类型/必填/默认/范围：string，可选；默认 `"UTC"`。
- 作用与影响/读取位置：当前未使用（保留字段）。
- 典型场景与示例：若未来支持本地时区处理，可设为 `"Asia/Shanghai"`。
- 注意事项：当前设置不会改变任何行为。

#### time.align_interval
- 类型/必填/默认/范围：string，必填；默认 `"1min"`；需为 pandas 可解析的时间间隔（如 `"30s"`、`"5min"`）。
- 作用与影响/读取位置：对齐时间轴，影响 join 覆盖率；`src/pipeline/link.py::run_link`。
- 典型场景与示例：高频数据可改为 `"30s"`。
- 注意事项：无效字符串会抛异常。

#### time.event_window.pre_hours
- 类型/必填/默认/范围：number，必填；默认 `72`（demo 为 `24`）；非负。
- 作用与影响/读取位置：事件前窗口时长；`src/pipeline/link.py::run_link`。
- 典型场景与示例：仅关注近场时设为 `6`。
- 注意事项：过长会拉大输出体量。

#### time.event_window.post_hours
- 类型/必填/默认/范围：number，必填；默认 `24`（demo 为 `12`）；非负。
- 作用与影响/读取位置：事件后窗口时长；`src/pipeline/link.py::run_link`。
- 典型场景与示例：关注余震期可扩大至 `48`。
- 注意事项：与 `pre_hours` 一起决定总窗口大小。

#### time.align_strategy.geomag_sec
- 类型/必填/默认/范围：string，可选；默认 `"aggregate"`（仅 default.yaml）；预留字段。
- 作用与影响/读取位置：当前未使用。
- 典型场景与示例：未来区分秒级/分钟级对齐策略。
- 注意事项：现阶段修改不会改变输出。

#### time.align_strategy.geomag_min
- 类型/必填/默认/范围：string，可选；默认 `"no_interpolate"`。
- 作用与影响/读取位置：当前未使用。
- 典型场景与示例：预留多策略对齐时使用。
- 注意事项：现阶段修改不会改变输出。

#### time.align_strategy.aef_min
- 类型/必填/默认/范围：string，可选；默认 `"no_interpolate"`。
- 作用与影响/读取位置：当前未使用。
- 典型场景与示例：预留多策略对齐时使用。
- 注意事项：现阶段修改不会改变输出。

#### time.align_strategy.seismic_waveform
- 类型/必填/默认/范围：string，可选；默认 `"feature_then_align"`。
- 作用与影响/读取位置：当前未使用。
- 典型场景与示例：预留波形特征化策略切换。
- 注意事项：现阶段修改不会改变输出。

### seismic
#### seismic.feature_interval_sec
- 类型/必填/默认/范围：int，可选；默认 `60`；正整数秒。
- 作用与影响/读取位置：standard 阶段地震波形特征窗口大小；`src/pipeline/standard.py::_seismic_features`。
- 典型场景与示例：需要更高时间分辨率可设为 `30`。
- 注意事项：窗口过小会增加计算量。

### preprocess
#### preprocess.outlier.method
- 类型/必填/默认/范围：string，可选；默认 `"zscore"`。
- 作用与影响/读取位置：当前仅写入质量标记；`src/pipeline/standard.py::_clean_timeseries_group`。
- 典型场景与示例：暂不支持其他方法，仅保留 `"zscore"`。
- 注意事项：修改为其他值不会改变清洗逻辑。

#### preprocess.outlier.threshold
- 类型/必填/默认/范围：float，必填；默认 `4.0`。
- 作用与影响/读取位置：z-score 异常阈值；`src/pipeline/standard.py::_clean_timeseries_group`。
- 典型场景与示例：更严格可设为 `3.0`。
- 注意事项：过小会导致过度插值。

#### preprocess.interpolate.max_gap_minutes
- 类型/必填/默认/范围：int，必填；默认 `10`（demo 为 `5`）。
- 作用与影响/读取位置：插值允许的连续缺失点数；`src/pipeline/standard.py::_clean_timeseries_group`。
- 典型场景与示例：缺失较多时提高至 `20`。
- 注意事项：这是点数上限，并非严格时间分钟。

#### preprocess.interpolate.method
- 类型/必填/默认/范围：string，可选；默认 `"linear"`。
- 作用与影响/读取位置：当前仅写入质量标记；`src/pipeline/standard.py::_clean_timeseries_group`。
- 典型场景与示例：未来扩展其他插值方法时使用。
- 注意事项：目前仍使用 pandas 默认线性插值。

#### preprocess.filter.enabled
- 类型/必填/默认/范围：bool，必填；默认 `true`。
- 作用与影响/读取位置：是否进行滚动均值滤波；`src/pipeline/standard.py::_clean_timeseries_group`。
- 典型场景与示例：调试原始噪声时设为 `false`。
- 注意事项：关闭后 `filter_effect.json` 中的 after_std 可能为空。

#### preprocess.filter.method
- 类型/必填/默认/范围：string，可选；默认 `"rolling_mean"`。
- 作用与影响/读取位置：当前仅写入质量标记；`src/pipeline/standard.py::_clean_timeseries_group`。
- 典型场景与示例：预留其他滤波方式。
- 注意事项：修改不会改变实际滤波算法。

#### preprocess.filter.window
- 类型/必填/默认/范围：int，必填；默认 `5`（demo 为 `3`）；正整数。
- 作用与影响/读取位置：滚动均值窗口大小；`src/pipeline/standard.py::_clean_timeseries_group`。
- 典型场景与示例：平滑强度不足时增大窗口。
- 注意事项：窗口过大可能掩盖异常信号。

#### preprocess.batch_rows
- 类型/必填/默认/范围：int，可选；默认 `50000`（demo 为 `20000`）；正整数。
- 作用与影响/读取位置：控制 standard 阶段按批清洗 geomag/aef；`src/pipeline/standard.py::_process_standard_source`。
- 典型场景与示例：内存紧张时可降到 `20000` 或更低。
- 注意事项：值过小会降低吞吐；过大可能触发 MemoryError。

#### preprocess.expand_minute_to_seconds
- 类型/必填/默认/范围：object，可选；默认空；按数据源配置分钟级展开规则。
- 作用与影响/读取位置：将分钟级数据在 standard 阶段展开为秒级常量段；`src/pipeline/standard.py::_process_standard_source`。
- 典型场景与示例：AEF 分钟均值需要还原为秒级常量段。
- 注意事项：会放大数据量，建议配合 `chunk_rows` 控制内存峰值。
#### preprocess.expand_minute_to_seconds.aef.enabled
- 类型/必填/默认/范围：bool，可选；默认 `false`。
- 作用与影响/读取位置：是否启用 AEF 分钟展开；`src/pipeline/standard.py::_process_standard_source`。
#### preprocess.expand_minute_to_seconds.aef.seconds
- 类型/必填/默认/范围：int，可选；默认 `60`。
- 作用与影响/读取位置：每条分钟记录展开的秒数；`src/pipeline/standard.py::_process_standard_source`。
#### preprocess.expand_minute_to_seconds.aef.mode
- 类型/必填/默认/范围：string，可选；默认 `"centered"`；取值 `centered|left`。
- 作用与影响/读取位置：时间戳扩展方式；`centered` 表示以分钟时间为中心扩展。
#### preprocess.expand_minute_to_seconds.aef.chunk_rows
- 类型/必填/默认/范围：int，可选；默认 `2000`。
- 作用与影响/读取位置：分钟展开的分块行数，降低内存峰值；`src/pipeline/standard.py::_process_standard_source`。

### link
#### link.spatial_km
- 类型/必填/默认/范围：float，必填；默认 `1000`；非负。
- 作用与影响/读取位置：按震中距离过滤站点；`src/pipeline/link.py::run_link`。
- 典型场景与示例：近场研究可设为 `50`。
- 注意事项：过小会导致无站点匹配。

#### link.require_station_location
- 类型/必填/默认/范围：bool，可选；默认 `false`。
- 作用与影响/读取位置：要求 `lat/lon` 存在才进入链接；`src/pipeline/link.py::run_link`。
- 典型场景与示例：空间分析严格时设为 `true`。
- 注意事项：缺少 StationXML 时启用会导致地震数据被全部剔除。

### features
#### features.rolling_window_minutes
- 类型/必填/默认/范围：int，可选；默认 `30`；预留字段。
- 作用与影响/读取位置：当前未使用。
- 典型场景与示例：未来用于滑窗特征聚合。
- 注意事项：修改不影响当前输出。

#### features.topn_anomalies
- 类型/必填/默认/范围：int，必填；默认 `50`（demo 为 `20`）；正整数。
- 作用与影响/读取位置：异常结果 TopN 截断；`src/pipeline/model.py::run_model`。
- 典型场景与示例：只保留前 10 个异常，设为 `10`。
- 注意事项：过小可能遗漏重要异常。

#### features.anomaly_threshold
- 类型/必填/默认/范围：float，可选；默认 `3.0`（代码内默认值，YAML 未显式提供）。
- 作用与影响/读取位置：异常 z-score 阈值；`src/pipeline/model.py::run_model`。
- 典型场景与示例：更敏感检测可设为 `2.5` 并在 YAML 中新增该字段。
- 注意事项：当前配置文件未包含，需要手动添加才会覆盖默认值。

### vlf
#### vlf.band_edges_hz
- 类型/必填/默认/范围：number[]，必填；默认 `[10, 1000, 3000, 10000]`；递增数组且长度 ≥ 2。
- 作用与影响/读取位置：划分频带并计算带功率；`src/pipeline/standard.py::_vlf_features`。
- 典型场景与示例：高频关注可扩展为 `[10, 1000, 3000, 10000, 20000]`。
- 注意事项：非递增会导致频带选择异常。

#### vlf.preview.max_time_bins
- 类型/必填/默认/范围：int，可选；默认 `200`（demo 为 `120`）；正整数。
- 作用与影响/读取位置：预览图时间维度裁剪；`src/pipeline/ingest.py::_write_preview_png`。
- 典型场景与示例：减小预览耗时可降为 `80`。
- 注意事项：过小会使预览失真，但不影响特征计算。

#### vlf.preview.max_freq_bins
- 类型/必填/默认/范围：int，可选；默认 `200`（demo 为 `120`）；正整数。
- 作用与影响/读取位置：预览图频率维度裁剪；`src/pipeline/ingest.py::_write_preview_png`。
- 典型场景与示例：快速查看时设为 `64`。
- 注意事项：只影响预览 PNG，不影响特征。

### storage
#### storage.parquet.compression
- 类型/必填/默认/范围：string，可选；默认 `"zstd"`。
- 作用与影响/读取位置：控制 Parquet 压缩算法；`src/store/parquet.py::write_parquet_configured`、`src/store/parquet.py::write_parquet_partitioned`。
- 典型场景与示例：需要更快写入可设为 `"snappy"`，压缩率优先可保持 `"zstd"`。
- 注意事项：不同压缩策略不会影响读取，但会影响磁盘占用与写入耗时。

#### storage.parquet.partition_cols
- 类型/必填/默认/范围：string[]，可选；默认 `["station_id","date"]`。
- 作用与影响/读取位置：控制 Standard 长表分区；`src/store/parquet.py::write_parquet_partitioned`、`src/pipeline/standard.py::_process_standard_source`。
- 典型场景与示例：默认输出 `outputs/standard/source=<source>/station_id=<id>/date=YYYY-MM-DD/part-*.parquet`。
- 注意事项：`date` 由 `ts_ms` 派生；修改分区需同步调整读取路径。

#### storage.parquet.batch_rows
- 类型/必填/默认/范围：int，可选；默认 `30000`（demo 为 `20000`）；正整数。
- 作用与影响/读取位置：控制 Parquet 写入分批行数/单文件行数；`src/store/parquet.py::write_parquet_configured`、`src/store/parquet.py::write_parquet_partitioned`。
- 典型场景与示例：内存紧张时可降到 `20000` 或 `10000`。
- 注意事项：值过小会降低写入吞吐，过大可能触发 ArrowMemoryError。

#### storage.zarr.compressor
- 类型/必填/默认/范围：string，可选；默认 `"zstd"`。
- 作用与影响/读取位置：当前未使用；VLF 写入采用 zarr 默认压缩。
- 典型场景与示例：未来控制 zarr 压缩策略。
- 注意事项：当前修改无效，需代码层支持。

### api
#### api.host
- 类型/必填/默认/范围：string，可选；默认 `"0.0.0.0"`。
- 作用与影响/读取位置：当前未在代码中读取；API 使用 `OUTPUT_ROOT` 环境变量。
- 典型场景与示例：启动 FastAPI 时使用 `uvicorn src.api.app:app --host 0.0.0.0`。
- 注意事项：在 YAML 中修改不会改变 API 绑定地址。

#### api.port
- 类型/必填/默认/范围：int，可选；默认 `8000`。
- 作用与影响/读取位置：当前未在代码中读取；需由启动命令指定端口。
- 典型场景与示例：`uvicorn src.api.app:app --port 8000`。
- 注意事项：YAML 修改不会改变监听端口。

## 常见错误与排查提示
- YAML 缩进错误会导致加载失败；优先检查是否混用 Tab。
- `origin_time_utc` 或 `align_interval` 格式不合法会触发解析异常。
- 未提供 `stationxml` 时，`require_station_location: true` 会导致 link 阶段无数据。
- `max_files_per_source`、`max_rows_per_source` 设置为 `0` 不生效；请使用 `null` 或正整数。
- `storage.zarr` 与 `api` 相关字段仍为预留/未接入配置的部分。
