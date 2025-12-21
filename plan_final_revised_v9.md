# PLAN.md — 地震系统多源数据处理与关联建模（毕业设计，工程落地版）

> 核心目标：把“多源数据处理 + 事件关联 + 特征/异常 + API + 可视化展示”做成**可长期运行、低遗漏、可验收**的工程流水线；每一步都能用脚本/测试给出客观证据；最终按 `project_task_list.csv`（对应映射：`docs/task_map.md`）逐条闭环推进与交付。
>
> 核心要求（题目明确）：基于 Python Flask/FastAPI 开发接口，支持可视化模块查询：
>
> 1) **原始数据（按时间/空间筛选）**；2) **预处理后的标准化数据**；3) **与地震标记关联的数据集及特征值**。
>
> **本计划的关键修订（与原 plan.md 保持同一组织方式，逐段增强）**
>
> - **严禁在解析/入库阶段按地震时间窗筛选文件或裁剪数据**：时间窗 N/M 与空间窗 K 只允许在 **E.Link（时空对齐与事件关联匹配）** 阶段使用。
> - 新增并明确 **Raw/Bronze（结构化原始可查询层）**：解析到的原始数据先统一结构化 + 落库，才能支撑 `/raw/query`（时间/空间筛选）。
> - 三大步骤严格分层、分次落库：
>   - Raw（可查询原始）→ Standard（清洗后的标准化可查询）→ Linked（事件关联数据集可查询）→ Features（特征/异常分可查询）
> - **存储策略选择结论**：在“事件关联”和“特征/模型”两大步骤之间 **必须额外落库一次（Linked）**，再在特征/模型后落库 Features/Anomaly（理由见 4.E/F 与 6）。

---

## 0. 项目信息与原则

### 0.1 项目名称

- 地震系统多源数据处理与关联建模

### 0.2 数据源（必须支持）

1) **地磁：IAGA2002（sec/min）**
   - 站点：`kak/kny/mmb`，地磁数据：`sec/min`（秒级/分钟级）
   - **现状说明**：你目前已收集的地磁文件以 *分钟级 IAGA2002* 为主；本计划仍保留对 `sec/min` 的解析与统一入库（题目提到的 100Hz 属于“可能存在的高频原始采样场景”，通常不以 IAGA2002 文本直接提供）。
   - **可选扩展**：若后续拿到高频地磁原始采样（例如 100Hz 的二进制/波形文件），用 `geomag_hf` 插件按“波形/数组”路径入库（见 3.4 storage 与 A6）。
   - 对应源：`geomag`（IAGA2002 长表）/ `geomag_hf`（可选，高频数组）
2) **地震波：MiniSEED + stations_inventory.xml**
   - 必须包含波形数据，台站信息通过 `stations_inventory.xml`（FDSN StationXML）
   - 可选：SAC（如果存在，提供数据处理）
3) **大气电磁：AEF（IAGA2002 风格）**
   - **分钟级数据**：按天分文件（约 1440 行/天，允许缺失）
4) **VLF：CDF（ERG/ISEE 频谱产品）**
   - 文件格式：NASA CDF（自描述容器）
   - 真实结构（以已验证的 `isee_vlf_mos_2020090923_v01.cdf` 为准；其他文件同名变量则同结构）：
     - `epoch_vlf`：TT2000 时间轴（int64，记录数 `n_time`；该样本文件 `n_time≈8646/小时`，中位帧间隔 `≈0.4096s`）
     - `freq_vlf`：频率轴（Hz，`n_freq=1024`；该样本文件范围 `10–19989 Hz`）
     - `ch1`：**NS spectrum**，形状 `(n_time, n_freq)`，单位 `V^2/Hz`
     - `ch2`：**EW spectrum**，形状 `(n_time, n_freq)`，单位 `V^2/Hz`
   - 重要结论：这不是“每分钟一个标量值”的分钟序列，而是 **高时间分辨率的频谱帧（time × freq × channel）**。

### 0.3 工程实践原则（避免“理论正确但不可落地”）

- **解析/入库阶段禁止事件筛选（强制）**：Ingest 只负责“把所有文件读出来、解析出来、结构化落库”；任何按地震时间窗/空间窗的筛选只允许在 **E.Link** 执行。
- **不插值高频原波形到分钟/秒网格**：如地震波和秒级地磁数据，先提特征或聚合再对齐。
- **缺失/哑元（dummy/sentinel）必须显式处理**：如 AEF 的 `X/Y/F` 组件，若为 `88888.00` 或类似值，需标记为缺失，避免污染特征与相关性。
- **所有数据变换要可追溯**：每个数据处理环节都需要产生对应的 DQ（数据质量）报告，包含行数、时间范围、缺失率、异常率、join 覆盖率等。
- **两轮交付**：第一轮端到端跑通所有模块，第二轮回归测试与查漏补缺（论文答辩阶段可交付的稳定版本）。

### 0.4 执行顺序总览（必须遵守，禁止错乱）

> **Stage 0** 扫描文件清单（manifest）
> **Stage A** Ingest：读取/解析（不做事件筛选）
> **Stage A′** Raw/Bronze：统一结构化 + 落库（支撑原始数据查询）
> **Stage B** Preprocess：数据清洗（去噪/异常/缺失）→ 落库 Standard/Silver（支撑标准化数据查询）
> **Stage E** Link：按 N/M/K 做时空对齐 + 事件关联 → 落库 Linked/Gold（支撑关联数据集查询）
> **Stage F** Features/Model：在 Linked 或 Standard 基础上提特征 + 异常分 → 落库 Features/Gold（支撑特征值查询）
> **Stage G** API：对 Raw/Standard/Linked/Features 提供查询
> **Stage H/I** 可视化：Dashboard 展示与 plot 产物（可复现）

---

## 1. 目标与客观验收标准（全局）

### 1.1 目标

1) **Raw/Bronze（结构化原始可查询）**：全量读取并结构化入库，支持按时间/空间/台站/通道查询
2) **多源数据预处理（Standard/Silver）**：去噪/异常/缺失处理，格式标准化，压缩存储
3) **时空对齐（用于事件关联）**：统一到可配置时间栅格（默认 1min，可选 30s；按需在事件窗内对齐）
4) **空间匹配**：根据给定震中点和半径 K(km)，查询台站数据
5) **与地震标记关联**：通过时间窗（前 N 小时，后 M 小时）和空间窗（K km）生成事件级关联数据集（Linked）
6) **特征提取 + 简单关联模型**：输出特征值、异常分数与标记（Features/Anomaly）
7) **FastAPI**：提供 raw/standard/linked/features/plots 查询接口
8) **可视化展示**：事件详情页/地图/热力图/DQ 仪表盘，支撑答辩演示

### 1.2 全局验收口径（硬性）

- **统一 schema**：输出字段至少包含：`ts_ms, source, station_id, channel, value(s), lat, lon, elev, quality_flags`
- **时间**：统一 UTC，主字段 `ts_ms` 精确到毫秒；如原始数据具备更高精度（例如 TT2000/纳秒级），Raw 层可额外保留 `ts_ns`（不替代 `ts_ms`，用于可追溯与精密切片）
- **坐标**：WGS84（lat/lon，单位：度）
- **每阶段必须产出** `outputs/reports/*.json`，包括：
  - `rows`、`ts_min/ts_max`、`missing_rate`、`outlier_rate`、`station_count`、`join_coverage`
- **端到端 demo 一键可跑**：支持分阶段、全阶段运行，自动生成产物
- **API 冒烟测试**：使用 httpx，确保返回状态 200 且字段齐全
- **可视化可复现**：Plotly figure JSON 必须可在任意机器上 `from_json()` 还原成功

---

## 2. 统一数据规范（Raw/Standard/Linked/Features Schema 与文件产物）

### 2.1 统一记录（建议 Parquet；也可 HDF5）

**关于“结构化格式（JSON/CSV/HDF5）”的落地说明（对齐题目要求）**

- 题目举例的 JSON/CSV/HDF5 是“结构化数据形态”的典型代表。本计划采用 **统一 schema + 多格式落地** 的策略：
  1) **长期落库（canonical）**：标量/特征序列优先用 *Parquet*（列式、可分区、适合查询）；矩阵/波形类优先用 *HDF5/Zarr/MiniSEED*（便于切片读取）。
  2) **接口输出（exchange）**：FastAPI 默认返回 *JSON*（面向可视化/前端）。
  3) **离线导出（deliverable）**：提供 `export` 命令/接口，把“某个时间窗/空间窗/事件窗”的结果导出为 *CSV 或 HDF5*（用于论文/交付），避免把全量数据长期重复存三份。



**最小字段（Raw 与 Standard 共用；Linked/Features 可扩展）：**

- `ts_ms` (int64): UTC 毫秒时间戳
- `source` (str): `geomag | seismic | aef | vlf`
- `station_id` (str):
  - 地磁/AEF：IAGA CODE（如 KAK）
  - 地震：`NET.STA.LOC.CHAN`（LOC 可为空，用空串表示）
- `channel` (str): 如 `X/Y/Z/F`、或 `BHZ`、或 `VLF_xxx`
- `value` (float): 主数值（必要时扩展 `value2/value3`）
- `lat/lon/elev` (float): WGS84；缺省允许为 NaN（但地震波在 join 后应尽量非空）
- `quality_flags` (json): 见 2.3
- （建议新增，利于追溯）`proc_stage, proc_version, params_hash`


> **VLF 数据结构例外（必须写清，避免“长表强塞导致数据爆炸”）：**
>
> - 本项目的 **2.1 统一长表 schema** 主要面向「标量时间序列」：geomag/aef，以及 seismic 的窗口特征。
> - VLF 的 Raw 形态是 **频谱矩阵（time × freq × channel）**，不适合直接落成每个频点一行的长表（会膨胀到千万级行/小时）。
> - 因此约定：
>   1) **Raw/VLF**：以 `Zarr/HDF5` 等块存储保存频谱立方体 + 单独的 index/catalog（用于时间/空间/台站检索）。
>   2) **Standard/VLF**：输出“可 join 的标量特征序列”（例如 1min 频带功率、谱峰频率等），再用 2.1 长表 schema 落库供 `/standard/query` 与 E.Link/F.Features 使用。


> 约束：
>
> - **Raw/Bronze** 只允许“结构化 + 显式标记缺失/解析错误”，禁止做清洗/滤波/补缺。
> - **Standard/Silver** 才允许去噪/异常/补缺（并打标）。
> - **Linked/Gold** 才允许按地震窗 N/M/K 做筛选与对齐。
> - **Features/Gold** 存特征值与模型输出（score/flag）。

### 2.2 元数据（metadata.json）

- 原始文件清单与时间覆盖范围（manifest）
- IAGA2002 header 关键字段（Reported、Units、Resolution、Interval Type）
- MiniSEED ↔ StationXML 匹配统计（matched_ratio、downgrade_count、unmatched_keys_topN）
- 参数快照（config hash）、pipeline_version、运行环境版本（python/依赖）
- 分层落库清单：Raw/Standard/Linked/Features 的产物路径与版本

### 2.3 quality_flags 规范（必须统一）

建议字段：

- `is_missing` (bool)
- `missing_reason` (`sentinel|gap|parse_error|unknown`)
- `is_interpolated` (bool) + `interp_method`
- `is_outlier` (bool) + `outlier_method` + `threshold`
- `is_filtered` (bool) + `filter_type` + `filter_params`
- `station_match` (`exact|downgrade|unmatched`)
- `note`（可选）

### 2.4 数据分层与 API/可视化映射（强制一致）

- Raw/Bronze（结构化原始可查询）→ `GET /raw/query`（可视化“原始数据”）
- Standard/Silver（清洗标准化可查询）→ `GET /standard/query`（可视化“预处理后的标准化数据”）
- Linked/Gold（事件关联数据集）→ `GET /events/{id}/linked`（可视化“关联数据集”）
- Features/Gold（特征/异常分/模型）→ `GET /events/{id}/features` + `GET /events/{id}/anomaly`（可视化“特征值/异常”）
- Plot（可复现图产物）→ `GET /events/{id}/plots?kind=...` 与 `/ui`（可视化展示）

---

## 3. 配置参数规范（无歧义，可复现）

统一 `configs/*.yaml`，并把最终使用的 config copy 到 `outputs/reports/config_snapshot.yaml`。

### 3.1 time

- `timezone: UTC`
- `align_interval: 1min`（默认）；可选 `30s`
- **对齐策略（强制规则）**：
  - `seismic_waveform`：不直接插值原波形；先提特征，再对齐
  - `geomag_sec`：聚合到 align_interval（mean/std/min/max/ptp/梯度等）
  - `geomag_min/aef_min/aef_hor`：若 align_interval < 原间隔：
    - 默认：不数值插值（避免造假信号）
    - 可选：forward-fill（必须标记 `is_interpolated=true`，且只用于 join，不用于频谱类特征）

### 3.2 preprocess

- `geomag_detrend: kalman`（或 rolling_median；二选一，默认 kalman）

- `seismic_bandpass`（**自适应规则**，避免“默认 0.5–20Hz 一刀切”）：
  - `freqmin_hz: 0.5`（默认；若做更长周期分析可降到 `0.1`）
  - `freqmax_user_hz: 20.0`（用户上限；可配）
  - `freqmax_nyquist_ratio: 0.45`（强制留余量；`freqmax_used = min(freqmax_user_hz, freqmax_nyquist_ratio * sampling_rate)`）
  - `corners: 4`, `zerophase: true`
  - **硬约束**：若 `freqmax_used <= freqmin_hz`，则跳过滤波并在 `quality_flags.is_filtered=false` + `note=bandpass_skipped_invalid_band`

- `aef_clean`（AEF 为分钟级 Z 通道，**不做 50/60Hz notch**）：
  - `keep_channels: ["Z"]`（默认只保留 Z；X/Y/F 视为 dummy 丢弃或全标缺失）
  - `despike`：
    - `method: rolling_median`（默认；可选 wavelet）
    - `window_points: 5`（分钟级默认 5 点）
    - `zscore_mad_threshold: 6.0`
  - `outlier`：
    - `method: mad`（或 robust_z）
    - `threshold: 6.0`
  - `missing_fill`：
    - `short_gap_max_points: 5`（分钟序列默认 5 点）
    - `method: linear`（或 spline）
    - `long_gap_keep_nan: true`

- `vlf_preprocess`（CDF 频谱产品，time×freq×channel）：
  - `vars`：
    - `time_var: "epoch_vlf"`
    - `freq_var: "freq_vlf"`
    - `ch_vars: {"ch1": "NS", "ch2": "EW"}`
  - `fill_value`：
    - `use_cdf_fillval: true`（优先读变量属性 `FILLVAL`；该样本为 `-1e31`）
    - `invalid_value_policy: "nan"`（fill/非有限/负值 → NaN）
  - `standardize`（把频谱降维为“可 join 的标量特征序列”）：
    - `freq_line_mask`（可选，针对电磁工频谱线干扰：在频谱域“掩蔽”而非时域 notch）：
      - `enable: false`（默认关闭；仅在 PSD 里确实看到 50/60Hz 及谐波尖峰时开启）
      - `base_hz: [50, 60]`（区域可配；例如日本常见 50/60 并存）
      - `harmonics: 5`（掩蔽到第 N 次谐波）
      - `half_width_hz: 0.5`（每条谱线左右各掩蔽多少 Hz）

    - `target_interval: "1min"`（默认跟 align_interval）
    - `time_agg: "median"`（或 mean）
    - `bands_hz`（可配；用于 bandpower）：
      - `[10, 300]`
      - `[300, 3000]`
      - `[3000, 10000]`
      - `[10000, 20000]`
  - `downsample_for_api`（只影响 API/可视化，不影响 Raw 落库）：
    - `time_downsample_s_default: 10`
    - `freq_downsample_bins_default: 4`
    - `max_cells: 200000`（time_bins × freq_bins × channel；超限必须自动下采样并返回 downsample_info）

### 3.3 link

- `N_hours: 72`（默认，可配）
- `M_hours: 48`（默认，可配）
- `K_km: 1000`（默认，可配 50–1000）

### 3.4 storage

- `canonical_storage`（建议只存一份长期主格式，避免重复占用）：
  - 长表（分钟/秒级标量序列、窗口特征、VLF 标量特征）：Parquet 分区
  - 数组/矩阵（VLF spectrogram、可选 geomag_hf）：Zarr/HDF5
  - 波形（seismic 原始）：MiniSEED（必要时 STEIM2）
- `export_formats`（按需导出而非长期三份共存）：API 默认 JSON；离线可导出 CSV/HDF5（按查询窗/事件窗）。
- `parquet_compression`：对长表不是“必须”，但默认建议保留 `zstd`（无损、透明、几乎零复杂度）；如数据量很小也可设为 `none`。



- `format: parquet`：用于 **长表 time-series**（geomag/aef/vlf_standard_features/seismic_window_features）
- `parquet_compression: zstd`（或 snappy）：**无损列式压缩**，并在 `compression.json` 里记录压缩比
- `waveform_storage`（面向高频采集：地震波、可选高频地磁）
  - **触发条件**：`sampling_rate_hz >= 50`（按每条 Trace / 每个数组块的元信息自动检测；可在 config 覆盖）
  - **压缩目标**：严格无损（bitwise 可复现），用于长期存储与按窗切片读取
  - **算法链（题目要求可落地：Δ1 差分 + Huffman 熵编码）**
    - Step1：Δ1 整数差分（`d[0]=x[0]`, `d[i]=x[i]-x[i-1]`），并做溢出/NaN/Inf 检测（失败则降级为“原样字节流压缩”并记录原因）
    - Step2：Canonical Huffman 编码（对差分序列做 ZigZag（符号映射）→ 统计频次 → 生成 codebook → bitstream）
    - 容器：写入 `*.dhuf`（header+codebook+bitstream），header 至少包含：`dtype/endian/npts/fs_hz/channel_id, sha256_raw`
  - **seismic 原始波形（MiniSEED）**
    - 主存储：保留下载到的 *MiniSEED 原文件*（行业标准、通常已含无损编码）；若需要切片/重写 mseed，采用 `STEIM2`（差分压缩类编码）
    - 论文/答辩“差分+霍夫曼”证据：可选导出 `outputs/raw/seismic_dhuf/.../*.dhuf`（**不替代** mseed，只用于展示题目要求的压缩链路）
  - **geomag_hf（可选，高频数组）**
    - 主存储：`Zarr/HDF5` chunked 数组（便于按窗切片）
    - 压缩：对每个 chunk 生成对应 `delta1+huffman` 的 `*.dhuf`（或将 bitstream 存为 Zarr 的 bytes dataset），并把 mapping 写入 meta（避免“只有理论描述没有产物”）
  - **必须产出（工程可验收）**
    - `outputs/reports/compression_stats.json`：逐通道/文件（或 chunk）记录：`raw_bytes, compressed_bytes, compress_ratio, codec="delta1+huffman", fs_hz, dtype, sha256_raw, sha256_decoded, max_abs_err, rms_err`
    - `outputs/reports/compression.json`：全局汇总（Parquet/Zarr/MiniSEED/ΔHUF），并提供到 `compression_stats.json` 的引用
  - **验收门槛（strict）**
    - `sha256_raw == sha256_decoded`（强制）
    - `max_abs_err == 0` 且 `rms_err == 0`（若源数据为 float，按 bytewise 解码后再比较；必须为 0）
    - 压缩率不设硬门槛（小样本可能 >1），但必须记录与解释

---

## 3.5（增强）存储工程化细节（Parquet 分区与读写策略）


> 目标：既能支撑大数据量（秒级/分钟级），又能让 API/可视化做到“秒开”。

### storage（增强）

- Parquet 分区建议：
  - Raw/Standard（长表）：`source=.../station_id=.../date=YYYY-MM-DD/part-*.parquet`
  - Linked：`event_id=.../aligned.parquet`（事件窗单文件或按 station 分片）
  - Features：`event_id=.../features.parquet` + `anomaly.parquet`
- 必须落盘统计：`outputs/reports/compression.json`
  - 原始字节数 vs 存储字节数（压缩比；分 parquet / zarr / mseed）
  - codec/参数：parquet(zstd/snappy)、zarr(delta+zstd 等)、mseed(原编码或 STEIM2)
  - 若存在高频数据：报告 `fs_hz` 分布与“按 fs 分组”的压缩比
  - 分区文件数量、单文件大小分布（避免过多小文件）
- 写入约束：
  - 单个 Parquet 文件建议 64–256MB（可配）
  - 写入必须 append-safe（按分区追加），支持增量更新（尤其是 Features 重跑）

---

## 4. 模块设计、标准方案与客观验收（逐阶段闭环）

> 每个阶段必须输出对应 DQ 报告：`outputs/reports/dq_<stage>.json`
> 严格顺序：A（解析）→ A′（Raw 入库）→ B（清洗）→ E（事件关联）→ F（特征/模型）→ G（API）→ H/I（可视化）

### A. Ingest（读取/解析：只做“解析”，禁止事件筛选）

> **强制禁止（与本次修改重点相关）**
>
> - A 阶段不得使用 `earthquakes.csv` 的时间窗 N/M 或空间窗 K 来过滤要读取的文件或行。
> - A 阶段不得只读取“疑似事件窗口附近的文件”；必须以数据源目录为范围做**全量扫描与解析**。

#### A0 文件清单（manifest，强烈建议先做）

- 输出：`outputs/manifests/run_<timestamp>.json`
- 字段：`path,size,mtime,sha256,inferred_source,inferred_station,inferred_time_range(optional)`
- 验收：文件数一致、hash 可复现

#### A1 IAGA2002 解析器（地磁 + AEF 共用）

**标准方案：** 解析 header → 解析数据表 → 识别缺失 sentinel → 输出长表 records（未清洗）。

- 输入：IAGA2002 文本（sec/min/hour）
- 关键工程细节：
  - header 解析字段：IAGA CODE、lat/lon/elev、Reported、Units、Resolution、Interval Type
  - sentinel/dummy 处理：
    - 若遇到 `88888.00`/`99999.00`/`99999.90` 等（以真实数据为准，允许在 config 中扩展列表），视为缺失并打标
    - AEF 文件可能声明 “X/Y/F components are dummies”，则：
      - 默认只把 `*_Z` 作为有效通道（单位 V/m，downward+）
      - `X/Y/F` 要么丢弃，要么保留但全部标记 missing_reason=sentinel（在 metadata 中记录策略）
- 验收（客观）：
  1) 单测：fixtures 覆盖 1 个地磁 min、1 个地磁 sec、1 个 AEF min、1 个 AEF hour；解析后列/通道正确
  2) dq_ingest_iaga.json：rows>0；ts_min/max 正确；missing_rate 可用
  3) AEF：dummy_rate（X/Y/F sentinel 占比）写入报告，且 Z 通道非全缺失

#### A2 MiniSEED ingest（ObsPy 标准实现）

**标准方案：** obspy.read → Stream/Trace → 提取 stats → 保存波形摘要（不必把全波形写入长表；raw 查询通过“文件索引 + 裁剪读取”实现）。

- 输入：MiniSEED
- 产物：
  - raw 波形：保留原 mseed（或复制到 data/raw_manifest）
  - 解析摘要：trace 清单（net/sta/loc/chan/start/end/sampling_rate/npts）
- 验收：
  1) 单测：能读取到 Trace；`sampling_rate`、`npts` 与 ObsPy 打印一致
  2) dq_ingest_mseed.json：trace_count>0；每条 trace start/end 合法

#### A3 StationXML ingest + 与 MiniSEED 匹配（无歧义 join 规则）

**标准方案：** StationXML 展开到 Channel level；按 NET/STA/LOC/CHAN + 时间 epoch 精确匹配。

- Join Key：
  1) 精确匹配 `(net, sta, loc, chan)`
  2) 若 trace.loc 为空：
     - 先匹配 `locationCode=""`
     - 找不到再降级匹配 `"00"`（记录 downgrade_count）
  3) 若存在多个 epoch（startDate/endDate）：按 trace.starttime 落在 epoch 内选择
- 验收（客观）：
  - `matched_ratio = matched_traces / total_traces`
  - 默认要求 `matched_ratio >= 0.99`（若数据自身不满足，需在报告解释并调整阈值）
  - 产出 `outputs/reports/station_match.json`：
    - matched_ratio、downgrade_count、unmatched_keys_topN、epoch_conflict_count

#### A4 SAC（可选）

- 若存在：用 ObsPy 读取，提取内置 lat/lon；验证波形长度>0
- 验收：dq_ingest_sac.json 记录文件数、成功率

#### A5 VLF CDF ingest（CDF 频谱产品，按真实结构落地）

**标准方案：** 使用 `cdflib` 读取 CDF 变量与属性，输出“可查询的 Raw 频谱立方体（time×freq×channel）”及其 catalog/index。

- 输入：CDF（文件名按小时归档，例如 `isee_vlf_mos_2020090923_v01.cdf`）
- 必须识别的变量（变量名对齐）：
  - `epoch_vlf`（TT2000，int64）：时间轴（长度 `n_time`）
  - `freq_vlf`（Hz，float）：频率轴（长度 `n_freq`）
  - `ch1`（NS spectrum，`V^2/Hz`）：形状 `(n_time, n_freq)`
  - `ch2`（EW spectrum，`V^2/Hz`）：形状 `(n_time, n_freq)`
- 必须读取并写入 metadata 的属性（用于可追溯与数据校验）：
  - global：`Station_code/Station_name/Logical_file_id/Generation_date/...`
  - var：`UNITS/FILLVAL/VALIDMIN/VALIDMAX/CATDESC`

**落库（Raw/Bronze，VLF 特例存储）**

- 数据体（频谱立方体，推荐 Zarr；也可 HDF5）：
  - `outputs/raw/vlf/station_id=<Station_code>/date=YYYY-MM-DD/hour=HH/spectrogram.zarr`
    - `ts_ms`（int64，长度 n_time）
    - `freq_hz`（float32，长度 n_freq）
    - `psd_ns_v2hz`（float32，形状 n_time×n_freq，对应 CDF `ch1`）
    - `psd_ew_v2hz`（float32，形状 n_time×n_freq，对应 CDF `ch2`）
- catalog/index（轻量 Parquet，供检索与 DQ）：
  - `outputs/raw/vlf_catalog.parquet`
    - `path, station_code, station_name, ts_min, ts_max, n_time, n_freq, freq_min, freq_max`
    - `dt_median_s, dt_max_gap_s, missing_ratio (fill/NaN 占比)`

**验收（客观）**

- `dq_ingest_vlf.json`（按文件/站点聚合）至少包含：
  - `ts_min/ts_max` 覆盖该小时桶（允许末尾缺帧）
  - `n_time>0`、`n_freq>0`、`shape(ch1)=shape(ch2)=(n_time,n_freq)`
  - `dt_median_s` 接近稳定值（该样本约 `0.4096s`），`dt_max_gap_s` 报告缺帧
  - `freq_min/freq_max` 与 `freq_vlf` 一致（该样本 `10–19989 Hz`）
  - `units` 必须为 `V^2/Hz`


**验收产物（必须产出，可直接用于答辩“量化证明数据读对了”）**

- 每个小时桶（与 `spectrogram.zarr` 同目录）必须额外产出：
  - `vlf_meta.json`：`n_time/n_freq/freq_min/freq_max/dt_median_s/ts_min/ts_max/units`（以及源文件名、Station_code 等）
  - `vlf_gap_report.json`：缺帧统计（`dt_max_gap_s`、gap 秒数分布直方图、最大 gap、gap_count）
  - `vlf_preview.png`：随机截取连续 1 小时（可设 seed 以复现）的 **time×freq** 频谱热图（必要时自动下采样以控制像素/文件大小），用于快速人工 spot-check
- 同时在 `outputs/reports/` 汇总：
  - `vlf_meta.json`：合并各桶 meta（便于答辩/复核）
  - `vlf_gap_report.json`：合并 gap 统计
  - `vlf_preview_index.json`：列出所有 `vlf_preview.png` 路径与对应 `ts_range/freq_range`（便于 UI/打包引用）


#### A6 高频地磁（geomag_hf，可选扩展：100Hz 等）Ingest

> **范围说明（务实）**
>
> - 你当前收集到的地磁数据是 IAGA2002 分钟级文本（长表标量序列）。如果项目阶段不要求引入 100Hz 数据，本模块可以不做实现，只保留接口与存储规范作为“满足题目要求的扩展点”。
> - 一旦未来接入 100Hz 级磁力仪原始采样（常见为二进制/波形文件，而非 IAGA2002 文本），本模块负责把“高频数组”按无损压缩存为可切片查询的 Raw 层数据。

**输入（示例）**

- 二进制/波形格式（以实际数据为准，常见：自定义 bin、HDF5、CSV+高精度时间戳等）

**输出（Raw/Bronze）**

- `outputs/raw/geomag_hf/station_id=<...>/date=YYYY-MM-DD/timeseries.zarr`
  - `ts_ns`（int64，纳秒或微秒；保留原始高精度时间）
  - `Bx/By/Bz`（float32/float64，形状 n_time）
  - `fs_hz`（float，采样率）
  - `units`、`fillval/sentinel`、`quality_flags`
- 同时写入 catalog：`outputs/raw/geomag_hf_catalog.parquet`（path、station、ts_min/max、fs_hz、npts、missing_ratio 等）

**压缩（必须体现题目“无损压缩（差分+霍夫曼）”要求）**

- 触发条件：`fs_hz >= 50`（高频采样才启用 ΔHUF；低频长表走 Parquet zstd 即可）
- 算法链：`Δ1 整数差分 + Canonical Huffman`（见 3.4 storage / waveform_storage；实现产物为 `*.dhuf`）
- 产物：
  - `outputs/reports/compression_stats.json`：逐通道记录 raw/stored/compress_ratio + lossless 校验
  - `outputs/reports/compression.json`：全局汇总（含 ΔHUF / Parquet / Zarr / MiniSEED）
- 验收门槛（strict）：
  - 解压后 `sha256` 完全一致；`max_abs_err==0` 且 `rms_err==0`
  - 若遇到 NaN/Inf 或 dtype 不支持导致 Δ1 失败：必须自动降级（原样字节流压缩）并在 stats 里写明 `fallback_reason`

**验收（客观）**


- `dq_ingest_geomag_hf.json`：`fs_hz`、`npts`、`ts_min/max`、missing/outlier 比例
- API 能按 `start/end` 切片返回下采样序列（见 G）



---

### A′. Structurize + Raw/Bronze 入库（新增：支撑“原始数据可查询”）

> 目的：把 A 阶段解析出的“原始记录”统一为 2.1 的 schema，并**落库为可按时间/空间查询**的数据集（Raw/Bronze）。
> 这一步是题目接口“原始数据查询”的必要条件。

**允许做的事情（必须明确）**

- 时间统一（UTC → `ts_ms`）
- 字段统一：`source/station_id/channel/value/units`
- 坐标补齐：来自 header/StationXML/站点表（能补就补；不能补则留 NaN 并报告）
- 显式标记：sentinel/parse_error/gap（仅标记，不修复）
- VLF 特例：A5 已落库 `spectrogram.zarr`，A′ 只负责生成/合并 `vlf_catalog.parquet` 与统一写入 `metadata.json`（避免重复搬运大矩阵）

**禁止做的事情**

- 禁止去噪/滤波/异常剔除/缺失补全（这些在 B 阶段做）
- 禁止按地震时间窗/空间窗筛选（这些在 E 阶段做）

**存储规范（建议 Parquet；VLF 频谱 cube 例外）**

- 路径：`outputs/raw/`（Raw/Bronze）
  - VLF 频谱 cube：`outputs/raw/vlf/.../spectrogram.zarr` + `outputs/raw/vlf_catalog.parquet`
- 分区：`source=.../station_id=.../date=YYYY-MM-DD/part-*.parquet`
- 验收：
  - `outputs/reports/dq_raw.json`：rows、ts_min/max、missing_rate（按 reason）、station_count、坐标缺失率

---

### B. Preprocess（数据清洗：去噪/异常/缺失）→ Standard/Silver 入库

> 对应题目三大步骤之一：多源数据预处理。
> **输入必须来自 Raw（outputs/raw/）**，输出落库 Standard（outputs/standard/），支撑 `/standard/query`。

**标准方案（按数据源分治，避免“同一套滤波硬套所有源”）**

1) 通用（geomag / aef / vlf_standard_features）
- 缺失：sentinel → NaN；短缺口插值；长缺口保留 NaN
- 异常：MAD/鲁棒 z-score（同一 source 内统一阈值口径）
- 插值仅用于 **短缺口**，并强制 `quality_flags.is_interpolated=true`

2) 地震波（seismic_waveform）
- bandpass：**自适应规则**（每条 Trace 先读 `sampling_rate`，再决定 `freqmax_used`）
  - `freqmin = config.seismic_bandpass.freqmin_hz`
  - `freqmax_used = min(config.seismic_bandpass.freqmax_user_hz, config.seismic_bandpass.freqmax_nyquist_ratio * sampling_rate)`
  - 若 `freqmax_used <= freqmin`：跳过滤波并记录原因（避免 Nyquist 违规）
- 去基线/漂移：必要时 `demean + detrend("linear")`（与 bandpass 解耦）

3) AEF（分钟级 Z 通道；不做 50/60Hz notch）
- dummy 通道处理：默认只保留 `Z`；`X/Y/F` 丢弃或全标缺失（见 A1 解析策略）
- 去突刺（despike）：rolling median（默认）或 wavelet（可选）
- 异常值剔除：MAD/鲁棒 z-score → 置 NaN + 标记 `is_outlier=true`
- 缺失补全：短缺口线性插值；长缺口保留 NaN（避免造假平滑）

4) VLF（频谱产品：time×freq×channel）
- Raw 不做“频域滤波”，只做 **无损清洗**（fill/非有限/负值 → NaN）
- Standard 只输出“可 join 的标量特征序列”（见 3.2 `vlf_preprocess.standardize`）：
  - 以 `align_interval`（默认 1min）为窗口，对频谱帧做 `median/mean` 聚合
  - 计算并落库（每窗口、每通道）：
    - `bandpower_<f1>_<f2>_hz`（对 PSD 做频带积分/求和）
    - `peak_freq_hz`、`peak_psd_v2hz`
    - `spectral_centroid_hz`（可选）
  - 输出仍遵循 2.1 长表：把 “特征名”编码进 `channel`（例如 `NS_bandpower_3000_10000_hz`）

**验收（客观）**

1) 单测：人为构造缺失/异常 → flags 命中率=100%（对 fixture）

2) `outputs/reports/filter_effect.json`（滤波/处理必须给证据，避免“滤了但说不清”）
- seismic bandpass：
  - 报告：`(fs, freqmin, freqmax_used)` 的分布（min/median/p95）
  - PSD 证据：抽样 Trace 的 Welch PSD（before/after）或带外功率下降比例
- （可选）VLF/AEF 的 “去突刺/异常剔除”：
  - 报告：spike_count_before/after、outlier_ratio、插值比例
- 所有证据必须写入：处理参数、抽样策略、样本数量

3) `outputs/reports/dq_standard.json`：missing/outlier/interpolated 比例（按 source/station/channel 统计）

**存储**

- 路径：`outputs/standard/`（Standard/Silver）
- 分区：同 Raw（便于 predicate pushdown）
- 说明：Standard 是“预处理后的标准化数据”，必须能被可视化端按时空查询。


### C. Align（时间对齐：只作为 Link 的内部能力，默认不单独落库）

> 对应题目三大步骤之二的一部分：时间对齐。
> 说明：题目接口不要求“全局对齐后的独立数据集”，因此本计划默认把 Align 作为 **E.Link 的内部步骤**（在事件窗内对齐并落到 Linked）。若后续确实需要全局对齐查询，再扩展一个 `outputs/aligned_standard/` 层。

**标准方案：**

- 统一生成 `ts_grid`（UTC，step=align_interval）
- 各 source 对齐规则：
  - geomag_sec：按 grid 聚合（mean/std/min/max/ptp/梯度）
  - geomag_min / aef_min / aef_hor：按 grid 重索引；细粒度 grid 默认不插值
  - seismic_waveform：先做分钟/30s 窗口特征（见 F），再对齐
  - vlf：**不是分钟标量序列**。对齐时使用 Standard/VLF 的“标量特征序列”（bandpower/peak 等）按 grid 重索引；若需要画 spectrogram，则在 API 层按 time/freq 窗口切片 + 下采样后单独返回

**验收（客观）**

- `outputs/reports/dq_align.json`（对 MVP 事件窗或抽样窗口生成）：
  - grid_len、ts_min/max、join_coverage（能在同一 ts 取到 ≥2 源的比例）

---

### D. Spatial（空间索引与范围查询：供 Link 使用）

**标准方案：**

- 台站点建立 R-tree（经纬度 bounding box；工程上常用，支持动态插入与范围查询）
- 备选（贴合题目表述）：四叉树（quadtree）/Geohash 网格索引也可实现同样的“空间范围查询”；实现时要求输出与 brute-force haversine 过滤结果一致（见验收）
- 精确距离用 haversine（球面距离，单位 km）做二次过滤（工程实践常用）

**验收（客观）**

- 单测：已知点对距离误差 < 1e-3 km
- R-tree 查询结果 == brute-force haversine 过滤结果（集合一致）
- `outputs/reports/dq_spatial.json` 输出站点数、查询示例结果数

---

### E. Link（时空对齐 + 与地震事件关联匹配）→ Linked/Gold 入库（关键：此处才允许 N/M/K）

> 对应题目三大步骤之二：时空对齐与关联匹配。
> **唯一允许使用时间窗 N/M 与空间窗 K 的阶段**：从 `outputs/standard/` 读取并生成事件级关联数据集（Linked）。

**输入格式（必须定义）**

- earthquakes.csv：`id,time_utc,lat,lon,mag[,depth]`
  - time_utc：ISO8601 或毫秒时间戳（统一转换为 UTC）
  - lat/lon：度
  - mag：Mw 或等价（写入 metadata）

**关联规则（强制）**

- 时间窗：`[t0 - N_hours, t0 + M_hours]`
- 空间窗：事件点半径 `K_km`
- 事件窗内执行：
  - D.Spatial 查询台站集合
  - C.Align 对齐多源序列（遵守“不造假”的对齐规则）
- **输出（本次修订：只落 Linked，不混入 Features）**每事件一个目录 `outputs/linked/<event_id>/`：
  - `stations.json`（台站列表、距离、匹配信息）
  - `aligned.parquet`（事件窗对齐后的多源序列/或可 join 的中间表）
  - `summary.json`（行数、覆盖率、缺失率、主要参数、params_hash）

- **事件级产物聚合目录（强烈建议新增，便于答辩与复现）**：在 `outputs/events/<event_id>/` 生成“该事件的一揽子交付物”，避免散落在多个顶层目录里难以展示与归档：
  - `event.json`：事件元信息（t0/lat/lon/mag/depth）+ 关联参数（N/M/K、align_interval、params_hash）
  - `linked/`：指向或拷贝 `outputs/linked/<event_id>/`（stations/aligned/summary）
  - `features/`：指向或拷贝 `outputs/features/<event_id>/`（features/anomaly/summary）
  - `plots/`：事件级图目录（建议保持与顶层一致的子目录结构，避免 md 引用路径混乱）
    - `plots/spec/`：指向或拷贝 `outputs/plots/spec/<event_id>/`
    - `plots/html/`：指向或拷贝 `outputs/plots/html/<event_id>/`
    - `plots/png/`：指向或拷贝 `outputs/plots/png/<event_id>/`（可选）
  - `reports/`：事件级 DQ 与说明（推荐）
    - `dq_event_link.json`（本事件 join_coverage、有效台站数、缺失率、降级原因）
    - `dq_event_features.json`（本事件特征缺失率/基线样本数/异常分布）
    - `event_summary.md`（自动生成的“1 页报告”：事件信息 + 关键图 + 关键异常点 TopN + 结论摘要）
  - `exports/`：按论文/交付需要导出的 CSV/HDF5 子集（按事件窗/频带窗裁剪后的结果）
- **可选：事件包** `outputs/events/<event_id>/event_bundle.zip`（把上述目录打包，便于提交/展示/备份）
- **实现方式**：提供脚本 `scripts/make_event_bundle.py --event_id <id>`，在 E/F/H 阶段完成后运行一次即可（默认用 symlink；Windows 环境可改为 copy）；脚本内部先调用 `scripts/render_event_summary.py` 生成 `event_summary.md` 再打包，避免遗漏。


**验收（客观）**

- 生成目录与 3 个核心文件齐全
- aligned 覆盖时间窗（ts_min <= t0-N，ts_max >= t0+M）
- `outputs/reports/dq_linked.json`：按 event 统计 join_coverage、有效台站数、有效 source 数、降级原因（如坐标缺失导致站点被剔除）

> **为什么要在这里落库一次（Linked）？**
> 因为 Link 是最需要人工核查的“关键中间结果”（覆盖率/对齐/站点集合/参数），先落盘可复现、可调参、可做增量重算；且 API/可视化经常需要直接展示“关联后的对齐曲线”。

---

### F. Features + Simple Model（特征提取 + 关联模型）→ Features/Gold 入库

> 对应题目三大步骤之三：特征提取与关联模型构建。
> 输入：优先从 `outputs/linked/<event_id>/aligned.parquet`（保证使用的是事件窗关联后的数据），必要时回读 Standard。

#### F1 特征提取（最小可交付集合）

- 通用统计：mean/std/min/max/ptp、缺失率
- 地磁（geomag）：梯度变化率（diff/Δt）、突变计数（超过阈值次数）
- AEF（aef）：**Z 通道**统计（mean/std/ptp）、一阶差分（Δ/Δt）、突刺计数（despike 前后）
- VLF（vlf）：从频谱（NS/EW）提取 **频带功率（bandpower）/谱峰频率与幅值/谱质心**；事件级特征使用“事件窗 vs 基线窗”的差值或效应量
- 地震（seismic）：
  - 窗口能量（RMS/绝对值积分）
  - 频谱峰值（主频）
  - P 到时（标准可实现）：classic STA/LTA + trigger_onset
  - S 到时（毕业设计可简化）：在 P 后窗口做二次触发/能量峰（若不稳定，可只输出 P 并在报告说明限制）

> 说明：如需更“标准”，可选做 instrument response removal（StationXML 含响应），但作为毕业设计可设为可选项：若实现则输出单位（m/s），否则保持 counts 并在 metadata 标记。

**验收（客观）**

- features 表列齐全
- NaN 占比可统计且不爆炸（例如 NaN_ratio < 0.8；阈值可配，并在报告解释）
- `outputs/reports/dq_features.json`：每源特征数量、缺失比例、时间范围

#### F2 简单关联模型（可解释）

- **阈值触发（默认）**
  - 每站每特征基线：背景窗分位数阈值
  - 输出：是否异常 + 分数（z-score 或 0–1）
  - **基线窗口选择（必须可复现）**
    - 默认基线：`[t0 - (N_hours + baseline_extra_hours), t0 - baseline_gap_hours]`
      - `baseline_extra_hours: 168`（默认 7 天；可配）
      - `baseline_gap_hours: 6`（默认 6 小时；可配）
    - 若基线缺失严重（有效样本 < `baseline_min_samples`）：
      - 降级策略 1：同台站“同月同小时段”历史数据（若数据覆盖足够长）
      - 降级策略 2：同源同站全局分位数（必须在 summary 记录降级原因）
    - `baseline_min_samples`: 默认 500（按 1min 对齐约 8.3 小时数据；30s 则翻倍）
- **相似度（可选，二选一）**
  - 余弦相似度（对齐后特征向量）
  - DTW（成本高；若启用必须限制长度并启用窗口）
- **输出定义（必须落盘）**：`anomaly_score`（默认 0–1）

**存储（本次修订：与 Linked 分开，第二次落库）**

- `outputs/features/<event_id>/features.parquet`
- `outputs/events/<event_id>/features/anomaly.parquet`
- `outputs/features/<event_id>/summary.json`（特征/模型口径、降级策略、params_hash）
- `outputs/models/rulebook.yaml`（阈值/窗口/权重/降级策略，便于论文描述与复现）

**验收（客观）**

- score 范围校验（0<=score<=1 或明确 z-score）
- `outputs/reports/feature_correlation.json`：
  - 事件窗 vs 背景窗：差值、Cohen’s d、Spearman 等（口径写清）
- `outputs/reports/dq_anomaly.json`：
  - 每事件：异常点数、异常台站数、按 source 分布、基线样本数分布（min/median/p95）

---

### G. API（FastAPI，工程闭环）

> 目标：既支持程序化查询（脚本/模型），也支持可视化端渲染（ECharts/Plotly 前端）；避免把“画图逻辑”写死在前端，保证可复现与可验收。

**接口（最小集合，与数据分层一致）**

- GET `/health`
- GET `/raw/query?source&start&end&bbox|radius&station_id&channel&limit`
  - `source=vlf`：返回 spectrogram 切片（见下：freq_min/freq_max/downsample）
  - `source=geomag_hf`（若启用）：返回高频地磁下采样序列（服务端强制限点）
- GET `/waveforms/query?source=seismic&station_id&start&end&channel&decimate&max_points`：返回地震波形裁剪切片（服务端降采样/限点，避免一次拉全量 500Hz×多天）
- GET `/standard/query?source&start&end&bbox|radius&station_id&channel&limit`
- GET `/events?include_incomplete=false`（列出事件与可用产物；默认仅返回 **READY** 事件：存在 `DONE` 且 **不存在 `FAIL`**，并附带 `completeness_ratio_required` 与 `missing_required` 摘要）
  - 当 `include_incomplete=true`：返回 READY/FAIL/INCOMPLETE 全量事件，并提供 `status` 与（若 FAIL）`finalize_fail_path`
  - 返回字段建议：`event_id,time_utc,mag,lat,lon,status,completeness_ratio_required,missing_required_top3,has_vlf`（便于 UI 列表页）
- GET `/events/{id}`（事件元信息 + 参数）
- GET `/events/{id}/linked`（返回 linked summary + 分页/抽样读取 aligned）
- GET `/events/{id}/features`
- GET `/events/{id}/anomaly`
- （可视化专用）GET `/events/{id}/plots?kind=...&format=spec|echarts|plotly|html|png`  →
  - `spec/echarts/plotly`：返回 **可视化规范**（前端渲染用）
  - `html/png`：直接返回离线产物（若存在），用于“答辩双击/免跑服务”或报告引用
- （前端无关的通用数据）GET `/events/{id}/plot-data?kind=...` → 只返回 `x/y` 序列、heatmap 网格、站点列表等“纯数据”，由前端选择 ECharts/Plotly/Matplotlib 渲染

- GET `/events/{id}/reports`：返回事件级报告索引（`dq_event_*` + `event_summary.md` 路径或内容摘要）
- GET `/events/{id}/summary`：返回 `event_summary.md`（用于 UI 内嵌渲染；可选参数 `?format=raw|html`）
- GET `/events/{id}/bundle`：下载 `outputs/events/<event_id>/event_bundle.zip`（仅对 `DONE` 就绪事件开放；若不存在或未就绪则返回 404 + 提示运行 `finalize_event_package.py` / `make_event_bundle.py`）
- （静态前端）GET `/ui` → Dashboard 首页（HTML 模板或静态文件）

**工程细节**

- 查询性能：优先读取 Parquet 分区 + predicate pushdown（按 `source/station_id/date` 过滤）
  - **VLF Raw**：从 `Zarr/HDF5` 块存储按 time/freq 切片读取（不走 Parquet）
- 统一参数：
  - `start/end` 支持 ISO8601 或 `ts_ms`；内部统一为 UTC `ts_ms`
  - `limit` 默认 20000；超限必须返回分页/截断标记
  - VLF 专用（`source=vlf`）：
    - `freq_min/freq_max`（Hz，频带窗）
    - `time_downsample_s`（默认 10s；服务端可自动加大以满足 `max_cells`）
    - `freq_downsample_bins`（默认 4；按频率 bin 合并或抽稀）
    - `max_cells`（默认 200k；超限返回 `downsample_info`）
- 数据下采样（可视化必需）
  - `plot_max_points_per_trace: 5000`（默认）
  - `downsample_method: lttb|uniform`（默认 lttb；无依赖则降级 uniform）
  - 下采样必须打标：spec 的 `meta` 写入 `downsampled` 与方法、点数（plotly 用 layout.meta；echarts 用 option.__meta__）

**验收（客观）**

- pytest + httpx API 冒烟测试：200 + 字段齐全（Raw/Standard/Linked/Features）
- `/events/{id}/plots`：返回 JSON 可直接渲染；spec/meta 含 `params_hash`（plotly=layout.meta；echarts=option.__meta__）
- 时间轴必须为 UTC（x 轴显示带 `Z` 或明确标注 UTC）

---

> 目的：把 pipeline 的“证据”从 JSON/Parquet 扩展到 **可交互图表**（时间序列、谱图/热力图、空间分布、DQ），形成论文/答辩可直接展示的 Dashboard。  
> 原则：**图 = 可复现产物**（同数据 + 同 config → 同图），并且前端尽量轻量（避免引入过多工程复杂度）。

### H. 可视化产物（Plot Spec / Figure Spec）

#### H1 图表清单（必须实现的最小集合）

1) **事件窗多源对齐曲线（时间序列）**  
   - 地磁/AEF：直接画标量序列（缺失断线，不补成连续）  
   - 地震：默认画窗口特征（RMS、STA/LTA、主频、P/S marker 等），不直接全量画 raw 波形  
   - VLF：默认画 bandpower/peak 等标量特征；若需要谱图，用 spectrogram 切片画 heatmap

2) **VLF 频谱热力图（可选增强，但非常“答辩友好”）**  
   - 输入：`/raw/query?source=vlf&start&end&freq_min&freq_max&downsample_s&freq_downsample_bins`  
   - 输出：二维矩阵（time × freq）+ NS/EW 两通道可切换（前端用 heatmap 渲染）

3) **台站空间分布（地图 + 异常强度）**  
   - 输入：`/events/{id}/linked` 的 stations + `/events/{id}/anomaly`

4) **滤波效果证据图（前后对比）**  
   - 输入：`filter_effect.json` + 抽样时段序列（带通/去噪前后）

5) **DQ 页面（阶段指标汇总 + 单事件 drill-down）**  
   - 输入：`outputs/reports/*.json` + `outputs/events/<event_id>/reports/*.json`

#### H2 图表存储（可复现产物）

> 为了不把“画图逻辑”绑死在某一个前端库：推荐存 **Plot Spec**（一种与你选择 ECharts/Plotly 无关的中间表示），前端再转换成具体库的 option/figure；如果你更想省事，也可以直接存 ECharts option JSON。

- 产物目录（建议）：
  - `outputs/plots/spec/<event_id>/plot_<kind>.json`（通用 Plot Spec：含数据 + meta）
  - `outputs/plots/echarts/<event_id>/plot_<kind>.json`（可选：直接存 ECharts option）
  - `outputs/plots/html/<event_id>/plot_<kind>.html`（可选离线 HTML：答辩无需跑服务也能打开）
  - `outputs/plots/png/<event_id>/plot_<kind>.png`（可选：用于 event_summary.md 直接嵌图；缺失则用 html 链接替代）
  - `outputs/reports/dq_plots.json`
- spec 的 `meta` 必须包含：`pipeline_version, params_hash, data_snapshot, downsample_info, event_id`

**验收（客观）**

- `/ui` 能对 MVP 事件渲染 ≥ 4 张核心图
- `dq_plots.json`：render_success_rate=1.0（对 MVP 事件）
- trace 点数受控：`max_points` 生效（后端分页/下采样）



**答辩准备（MVP 事件）**：只需选择并跑通 *1 个代表性事件*（event_id 固定写入 `configs/demo.yaml`），生成 `outputs/events/<event_id>/` + `event_bundle.zip` 作为展示主线。
### I. 前端展示（Dashboard，尽量不复杂）

**推荐实现（最简单可落地）：FastAPI + 静态 HTML + ECharts（CDN 引入，交互式）**  
- 优点：无需 Node/Vite；一份 `index.html` 就能做列表页和详情页；非常适合毕业设计“能跑 + 能演示”。  
- 如果你更熟 Vue：可以用 Vue3（CDN）+ ECharts（CDN），依然不需要构建工具（可选增强）。

**必须页面（最小集合）**

1) 事件列表页：event_id/time/mag/lat/lon + READY 状态（基于 `DONE` + `artifacts_manifest.json` 的 completeness_ratio_required；点击可进入事件详情）
2) 事件详情页（按 Tab 展示）：对齐曲线 / VLF 热力图 / 地图 / 滤波证据 / summary + event_report
3) DQ 页面：全局 DQ 汇总 + 点击某事件查看 `dq_event_*`

**可选增强（但不强制）**

- “导出本事件包”按钮：调用 `/events/{id}/bundle` 下载 `event_bundle.zip`
- “图表离线查看”链接：直接打开 `outputs/plots/html/<event_id>/...`

---


## 5. 代码结构、可执行命令与 CI（工程闭环：可跑、可验收、可复现）

> 目的：把本计划从“描述”落成“可执行的工程系统”。本节明确**仓库结构、统一运行入口、严格模式、测试与CI**，避免出现“计划很好但跑不起来/不可复现”的风险。

### 5.1 仓库目录约定（强制，避免产物散落/路径混乱）

- `configs/`：YAML 配置（`default.yaml`、`demo.yaml`、`local.yaml`）
- `src/`：核心代码（按 stage 拆分模块，禁止脚本里堆逻辑）
  - `src/pipeline/`：stage 编排（A/A′/B/E/F/G/H/I）
  - `src/io/`：各数据源解析（IAGA2002、MiniSEED、StationXML、CDF）
  - `src/store/`：Parquet/Zarr/MiniSEED 写入与读取（含分区与 chunk）
  - `src/dq/`：DQ 统计与报告生成（统一 JSON schema）
  - `src/plots/`：Plot spec 生成 + HTML 渲染（Plotly/ECharts）
  - `src/api/`：FastAPI app（只做路由 + 读存储层，不做重计算）
- `scripts/`：薄脚本入口（只做参数解析 + 调用 `src/`）
  - `scripts/pipeline_run.py`：统一 stage 入口（强制顺序与依赖检查）
  - `scripts/finalize_event_package.py`：事件目录原子化收口 + `DONE/FAIL`（失败写 `reports/finalize_fail.json`）
  - `scripts/render_event_summary.py`：渲染 `event_summary.md`（Jinja2）
  - `scripts/make_event_bundle.py`：打包 `event_bundle.zip`
- `tests/`：pytest（unit + integration + e2e-smoke）
- `fixtures/`：最小样例数据（可合法分享的裁剪片段；用于 CI）
- `outputs/`：所有运行产物（必须 gitignore；由脚本自动生成）
- `docs/`：文档（本文 + 数据字典 + API 文档导出）

### 5.2 统一运行入口：`scripts/pipeline_run.py`（强制顺序 + 可分阶段）

> 关键设计：**任何人都只能通过一个入口跑 pipeline**，避免“手工顺序跑错/漏跑/用错参数”。入口会：
> 1) 生成 `run_id`；2) 计算 `params_hash`；3) 写入 `config_snapshot.yaml`；4) 做依赖检查；5) 产出 stage DQ；6) 可选 strict 失败即停。

- 基本用法（示例）：
```bash
# 0) 扫描 manifest（不解析数据）
python scripts/pipeline_run.py --stages manifest --config configs/default.yaml

# 1) 全量解析 + Raw 入库（禁止事件筛选）
python scripts/pipeline_run.py --stages ingest,raw --config configs/default.yaml

# 2) Standard（清洗/滤波/补缺）+ DQ/证据
python scripts/pipeline_run.py --stages standard --config configs/default.yaml

# 3) 针对一个事件：Link → Features → Plots → Finalize（生成 event 目录与 DONE）
python scripts/pipeline_run.py --stages link,features,plots --event_id <event_id> --config configs/demo.yaml
python scripts/finalize_event_package.py --event_id <event_id> --strict
python scripts/make_event_bundle.py --event_id <event_id>
```

- 运行规则（必须实现）：
  - 不允许跳过依赖：例如 `--stages features` 必须先存在 `outputs/linked/<event_id>/aligned.parquet`
  - `--event_id` 为空时：只允许运行全量 stage（manifest/ingest/raw/standard），禁止 link/features/plots
  - 所有 stage 都必须写入：`outputs/reports/dq_<stage>.json`（以及必要时写入 `filter_effect.json` 等证据）

### 5.3 严格模式（`--strict`）与“失败即停”的客观门槛（可配置）

> strict 的意义：让“READY”具有工程可信度，而不是“跑完了但其实缺一堆东西”。

- strict 默认门槛（可在 config 覆盖；但必须有默认值）：
  - `dq_raw.rows > 0` 且 `ts_min < ts_max`
  - `station_match.matched_ratio >= 0.95`（不足则 READY=false 并写明原因）
  - `dq_event_link.join_coverage >= 0.3`（数据极差时允许 READY=false，但必须仍能生成报告）
  - `dq_event_features.baseline_min_samples >= baseline_min_samples` 或触发降级策略并记录
  - `artifacts_manifest.required_missing_count == 0` 才允许写 `DONE`
- strict 行为：
  - 不在中途抛异常导致产物缺失；而是**写入 DQ 与 MISSING 原因**，最后由 `finalize` 决定是否写 `DONE`

### 5.4 测试与 CI（保证“每一步可验证”）

- `pytest -m unit`：解析器、时间转换、距离计算、flags 判定、参数校验
- `pytest -m integ`：用 fixtures 跑完 `ingest→raw→standard`，验证 DQ JSON schema 与关键指标
- `pytest -m smoke`：启动 FastAPI（TestClient/httpx）验证 `/health`、`/raw/query`、`/standard/query`、`/events/{id}/summary` 返回 200 且字段齐全
- 静态检查（建议 pre-commit）：
  - ruff/flake8：lint
  - black：格式化
  - mypy：类型检查（至少对 API layer/IO layer 覆盖）
- CI 产物（可选但强烈建议）：
  - 上传 `outputs/reports/` 作为 artifacts（便于回归对比）


## 6. 证据与产物目录（必须落盘）

> 说明：既要有**全局汇总报告**（便于整体验收/回归），也要有**事件级目录**（便于答辩展示/逐事件复现与归档）。

### 6.1 顶层分层产物（面向工程流水线）

- `outputs/manifests/`：文件清单 + hash（可复现扫描）
- `outputs/raw/`：Raw/Bronze（结构化原始可查询）
- `outputs/standard/`：Standard/Silver（清洗后的标准化可查询）
- `outputs/linked/`：Linked/Gold（按 event_id 的事件关联数据集，核心输入：E.Link）
- `outputs/features/`：Features/Gold（特征与异常分，核心输入：F.Features）
- `outputs/models/`：rulebook/阈值/权重等口径
- `outputs/plots/`：可视化产物（figure JSON/HTML）
- `outputs/reports/`：**全局**客观证据报告（按 stage 汇总）

### 6.2 事件级聚合目录（面向展示/归档，建议新增）

- `outputs/events/<event_id>/`：该事件的一揽子产物（linked + features + plots + reports + exports）
  - `event.json`：事件元信息 + 参数快照（N/M/K、align_interval、params_hash）
  - `linked/`：同 `outputs/linked/<event_id>/`
  - `features/`：同 `outputs/features/<event_id>/`
  - `plots/`：同 `outputs/plots/*/<event_id>/`
  - `reports/`：**事件级**DQ 与“一页摘要报告”
  - `exports/`：按事件窗裁剪导出的 CSV/HDF5（用于论文附录/交付）
- `outputs/events/<event_id>/event_bundle.zip`（可选）：打包下载/提交/备份



#### 6.2.1 事件产物完整性清单（per-event `artifacts_manifest.json`，强烈建议新增）

> 目的：让“这个事件到底产出了什么、缺了什么”**一眼可见**，并支撑 `/ui` 列表页的“就绪/缺失”状态展示；同时作为 `event_bundle.zip` 的自带说明与验收证据。

- 位置（固定）：`outputs/events/<event_id>/reports/artifacts_manifest.json`
- 生成时机：建议在 `render_event_summary.py` 之前生成（因为 summary 也可引用完整性结果）
- 内容建议（最小字段；全部可由“文件存在性+文件大小+元信息”得到，不需要重新计算数据）：
  - `event_id, pipeline_version, params_hash, generated_at_utc`
  - `required_files`: [{`path`, `purpose`, `exists`, `bytes`, `mtime_utc`}]
  - `optional_files`: 同上（例如 VLF spectrogram 图、png 等）
  - `completeness_ratio_required`: required 中 exists=true 的比例（0–1）
  - `missing_required`: 缺失 required 的 path 列表
  - `notes`: 例如 “本事件无 VLF 数据，谱图标记为 optional”

**required_files（建议固定，避免 UI/脚本到处写判断）**
- `event.json`
- `linked/summary.json` + `linked/aligned.parquet` + `linked/stations.json`
- `features/summary.json` + `features/features.parquet` + `features/anomaly.parquet`（若模型不产 anomaly，可改成 optional，但必须写清）
- `plots/html/plot_aligned_timeseries.html`
- `plots/html/plot_station_map.html`
- `plots/html/plot_filter_effect.html`
- `reports/dq_event_link.json`
- `reports/dq_event_features.json`
- `reports/dq_plots.json`
- `reports/filter_effect.json`
- `reports/event_summary.md`
- （若 finalize 失败）`reports/finalize_fail.json` + 根标记 `FAIL`（不写 `DONE`）

> VLF：若该事件窗内确实存在 VLF 数据，则 `plot_vlf_spectrogram.html` 作为 required；否则为 optional 且在 notes 写明“无 VLF 覆盖”。

#### 6.2.2 事件目录生成“原子化”（atomic finalize）与就绪标记（`DONE`）

> 目的：避免 UI/API 读取到“半生成”的事件目录（例如 summary 已写但 plots 还没写完），造成前端报错或展示混乱。

- 事件目录的生成/更新**不在** E/F/H 阶段零散写入，而是由一个“收口脚本”统一完成：
  - `scripts/finalize_event_package.py --event_id <id> [--strict]`
  - 行为：从 `outputs/linked/`、`outputs/features/`、`outputs/plots/` 等产物中汇总（symlink 或 copy），生成 `artifacts_manifest.json`、`event_summary.md`，校验通过才写入 `DONE`；否则写入 `FAIL` + `reports/finalize_fail.json`（不写 DONE）。
  - 收口清单（写入到 `outputs/events/<event_id>/`，保证 event_bundle 自包含）：
    - `event.json`（事件元信息 + 参数快照 + params_hash）
    - `linked/`：从 `outputs/linked/<event_id>/` 复制/软链接（`aligned.parquet`、`summary.json`、`stations.json`）
    - `features/`：从 `outputs/features/<event_id>/` 复制/软链接（`features.parquet`、`anomaly.parquet`、`summary.json`）
    - `plots/html/` 与 `plots/spec/`：从 `outputs/plots/{html,spec}/<event_id>/` 复制/软链接（必需图 + 可选图）
    - `reports/`：
      - `dq_event_link.json`（来自 link stage）
      - `dq_event_features.json`（来自 features stage）
      - `dq_plots.json`（来自 plots stage；若 plots 产出按 event_id 命名，finalize 必须重命名为该固定名）
      - `filter_effect.json`（优先用事件级证据；若只有全局 `outputs/reports/filter_effect.json`，则复制一份到此处并在 summary 中说明）
      - `artifacts_manifest.json` + `event_summary.md`
- 原子化写入规则（POSIX 上 rename 原子；Windows 允许降级 copy+swap，但必须先写 tmp）：
  1) 写入到临时目录：`outputs/events/<event_id>/.tmp_<run_id>/`
  2) 生成全部文件（含 manifest、summary）并做一次“required 完整性校验”
  3) **若 required 缺失 / 校验失败（strict fail）**：
     - 在临时目录写入 `reports/finalize_fail.json`（missing_required + failing_checks + run_id + timestamp）
     - 在临时目录根写入标记文件 `FAIL`，并 **不写 `DONE`**
     - 若存在旧的 READY 目录（已有 `DONE`）：**不替换**旧目录；把临时目录重命名为 `outputs/events/<event_id>/.failed_<run_id>/` 留作证据
     - 若不存在旧目录：将该失败目录原子落盘为 `outputs/events/<event_id>/`（至少包含 `FAIL` + `reports/finalize_fail.json`），避免出现“空目录”
     - 退出码非 0（便于 CI/脚本感知失败）
  4) **若校验通过**：原子替换为正式目录 `outputs/events/<event_id>/`
  5) 最后在正式目录根写入空文件 `DONE`（建议根目录）作为“就绪标记”，并确保 `FAIL` 不存在（若曾失败，success 必须清理/覆盖 FAIL 标记）

**UI/API 默认只展示 READY（`DONE` 且无 `FAIL`）的事件**
- `/events` 默认只返回存在 `DONE` 且 **不存在 `FAIL`** 的事件；需要看未完成/失败事件时，用 `?include_incomplete=true`
- `/events?include_incomplete=false` 时服务端必须过滤 `FAIL`（避免 finalize 失败但目录存在导致“空事件”被展示）
- `/ui` 列表页同理：默认只展示 READY；可选提供勾选显示 INCOMPLETE/FAIL（并在列表上用 badge 区分）
### 6.3 报告口径（避免“全局报告看不出单个事件发生了什么”）

- 全局报告（stage 汇总）：继续放在 `outputs/reports/`（例如 `dq_standard.json`、`dq_linked.json` 等）
- 事件报告（per-event）：放到 `outputs/events/<event_id>/reports/`，至少包含：
  - `dq_event_link.json`（本事件站点/覆盖率/缺失/降级）
  - `dq_event_features.json`（本事件特征缺失/基线样本数/异常分布）
  - `event_summary.md`（答辩展示友好：关键图 + Top 异常点 + 结论摘要）


### 6.4 事件一页报告（event_summary.md）：模板 + 自动生成（答辩化但不复杂）

> 目标：让每个事件都有一份“一页纸”能讲清楚：**事件是什么、关联到了哪些站/数据、质量如何、哪些地方最异常、证据图在哪里、如何复现**。  
> 这份报告既能被 `/ui/events/<event_id>` 内嵌展示，也能被打包进 `event_bundle.zip` 离线打开。

#### 6.4.1 生成时机与依赖（避免遗漏/半成品）

- **生成时机**：推荐在 `H_plots_generation_and_dq` 之后执行（因为报告要引用图产物）。  
- **依赖输入（按 event_id）**：
  - `outputs/events/<event_id>/event.json`（事件元信息 + 参数快照）
  - `outputs/events/<event_id>/reports/dq_event_link.json`（站点/覆盖率/缺失/降级原因）
  - `outputs/events/<event_id>/reports/dq_event_features.json`（特征缺失/基线样本数/异常分布）
  - `outputs/events/<event_id>/reports/dq_plots.json`（图产物是否齐全/渲染是否成功）
  - `outputs/events/<event_id>/reports/filter_effect.json`（滤波/去噪的定量证据）
  - `outputs/events/<event_id>/features/anomaly.parquet`（TopN 异常点；若不存在则 TopN 为空但报告仍可生成）
  - 图产物（至少 4 张核心图；缺失时必须在报告中写明“缺失原因”而不是直接报错）：
    - `outputs/events/<event_id>/plots/html/plot_aligned_timeseries.html`
    - `outputs/events/<event_id>/plots/html/plot_vlf_spectrogram.html`（可选；没有 VLF 也允许缺失）
    - `outputs/events/<event_id>/plots/html/plot_station_map.html`
    - `outputs/events/<event_id>/plots/html/plot_filter_effect.html`

> 关键原则：**报告生成脚本不得假设某张图一定存在**；必须以“检测文件存在 → 有则引用，无则写缺失原因”的方式输出（保证流水线可跑通）。

#### 6.4.2 输出位置（强制统一，便于 UI/打包/验收）

- Markdown（必需）：`outputs/events/<event_id>/reports/event_summary.md`
- 可选 HTML（建议用于离线双击查看）：`outputs/events/<event_id>/reports/event_summary.html`
- 生成脚本（建议新增）：`scripts/render_event_summary.py --event_id <id> [--format md|html|both]`
- Bundle 脚本集成：`scripts/make_event_bundle.py` 在打包前**自动调用** `render_event_summary.py`（保证 zip 内一定有一页报告）

#### 6.4.2.1 `render_event_summary.py` 实现要点（防 bug 清单）

- **路径优先级**（避免 bundle 与顶层目录不一致）：
  1) 若存在 `outputs/events/<event_id>/plots/...`，优先引用事件目录下的相对路径（离线可用）
  2) 否则回退引用顶层 `outputs/plots/...`（在线服务可用）
- **TopN 异常点表**：
  - 若 `anomaly.parquet` 不存在 → `top_anomalies_table` 填 “No anomaly file”
  - 若存在但行数为 0 → 填 “No anomalies above threshold”
  - 表格字段建议固定：`rank, source, station_id, ts_utc, feature, score, distance_km`
- **图引用**：
  - 有 png → `aligned_timeseries_png_embed = "![](../plots/png/plot_aligned_timeseries.png)"`
  - 没 png → embed 字段为空字符串（保留 html 链接即可）
  - html 缺失 → 在报告对应位置填入 `MISSING: plot_aligned_timeseries.html (reason=...)`，并把缺失原因写进 `dq_plots`/日志
- **所有数值口径都来自 DQ/summary 文件**（不在脚本里“重新计算”），保证可追溯
- **输出必须幂等**：同一 `event_id + params_hash` 重跑得到相同内容（除非输入文件变化）
- **最小单元测试**（pytest）：
  - 给一个 fake event 目录 + 几个 mock json/parquet → 断言 md 含关键标题与链接


#### 6.4.3 图产物命名规范（减少“引用不到图”的 bug）

为降低耦合，统一用 `<kind>` 固定命名（与 `/events/{id}/plots?kind=...` 一致）：

- `aligned_timeseries` → `plot_aligned_timeseries.(html|png|json)`
- `vlf_spectrogram` → `plot_vlf_spectrogram.(html|png|json)`
- `station_map` → `plot_station_map.(html|png|json)`
- `filter_effect` → `plot_filter_effect.(html|png|json)`

> 建议在 H2 图表存储中同时落 `html`（交互）与 `png`（可在 md 里直接嵌图）。若只做 html，则 md 里用链接替代嵌图。

#### 6.4.4 模板文件（**外置交付物**，避免版本漂移）

- 模板路径（固定）：`templates/event_summary_template_v3.md`
- 渲染规则：`render_event_summary.py` 读取模板并用 **同名占位符**替换（Jinja2 或最小模板引擎均可）。
- 禁止在计划文档内嵌模板正文（避免计划更新与模板更新不同步导致“理论正确但落地偏离”）。
- 模板必须满足：
  - 每个引用的产物路径都以 **事件目录为根的相对路径**给出（zip 解压后双击可用）
  - 缺失图/缺失数据必须写 `MISSING:<reason>`，不得报错中断
  - 必须包含 `params_hash`、`pipeline_version`、复现命令
#### 6.4.5 验收标准（必须可测，避免“看起来有但不可靠”）

- 文件存在：`outputs/events/<event_id>/reports/event_summary.md` 必须生成
- 报告完整性检查（建议写成 pytest）：
  - 必须包含 7 个一级标题（0~6）
  - 必须出现 `params_hash`（保证可追溯）
  - 必须包含：3 个必需图链接（aligned/station_map/filter_effect）+ 2 个 DQ 链接（dq_event_link/dq_event_features）（VLF 视覆盖情况可缺失）
  - 若图缺失：报告中必须出现 `MISSING:` 描述（而不是脚本报错退出）
- TopN 表格：
  - 若 `anomaly.parquet` 存在：必须输出 `TopN>=1` 行
  - 若不存在：必须输出 “No anomaly file” 的说明（可复现性不受影响）


---

## 7. 风险与应对（工程可落地）

- **StationXML 匹配不达标**：输出 `unmatched_keys_topN`，调整 loc 降级策略或时间 epoch 选择规则
- **AEF dummy 值污染**：必须在 ingest 阶段显式标记（sentinel→NaN + flags），禁止进入特征
- **秒级对齐导致“造假”**：禁止插值高频波形；只允许聚合/提特征
- **滤波效果不可验证**：必须用 `filter_effect.json` 给定量证据（dB/ratio）
- **可视化性能不可用（前端卡死）**：服务端下采样 + 限制最大点数；seismic 只展示特征
- **地图底图依赖网络**：默认 `scattergeo` 离线可用；mapbox 仅可选
- **单位/坐标系混乱**：metadata + figure axis title 强制写单位；counts 未去响应必须标注
- **计算成本过高**：默认 align 1min；30s 仅用于小样例或特定需求（并记录）

---

## 8. 最小可交付版本（MVP）

- **跑通 ingest + raw 入库：** IAGA2002（地磁+AEF） + MiniSEED + StationXML join → `outputs/raw/`
- **跑通 preprocess + standard 入库：** 缺失/异常/滤波 + `filter_effect.json` → `outputs/standard/`
- **跑通 link + linked 入库：** 对至少 1 个事件输出 `outputs/linked/<event_id>/aligned.parquet`
- **跑通 features/model + features 入库：** 输出 `features.parquet + anomaly.parquet + rulebook.yaml`
- **跑通 plots：** 至少为 1 个事件输出 4 张核心图（时间序列/热力图/地图/滤波对比）+ `dq_plots.json`
- **API：** raw/standard/linked/features/plots 查询 + 冒烟测试通过
- **UI：** `/ui` 可浏览事件并渲染图（轻量 Dashboard）

---

## 9. project_task_list.csv / issues.csv 任务拆解（无遗漏 + 工程闭环验收）

> 目标：把“计划”映射为**可追踪的任务清单**，并且每条任务都有：输入/输出、禁止项、验证步骤、验收证据路径。  
> 建议做法：维护一份 `project_task_list.csv`（计划级），再按需要导出为 GitHub Issues（或 `issues.csv`）。

### 9.1 `project_task_list.csv` 字段规范（建议固定）

- `task_id`：如 `T09_LINK_EVENT`
- `stage`：`manifest|ingest|raw|standard|spatial|link|features|model|plots|finalize|api|ui|ci|docs`
- `title`：一句话描述
- `depends_on`：逗号分隔 task_id
- `inputs`：关键输入路径/数据源
- `outputs`：交付物路径（必须可指向 `outputs/...`）
- `verify_steps`：可执行的命令/pytest 标记/检查项
- `acceptance`：客观门槛（阈值/文件存在/字段齐全/返回码）
- `evidence`：DQ 报告/截图/图表/日志路径（可在 CI 上传）

### 9.2 任务总表（最小无遗漏集合）

> 说明：以下表格可直接复制为 CSV（用 `,` 分隔即可），也可作为 GitHub Issues 模板。  
> **强制原则**：任何实现不得绕过 A→A′→B→E→F 的依赖顺序；尤其不得在 A/A′ 阶段按 N/M/K 做事件筛选（见 0.3 与 4.A/E）。

| TaskID | Stage | 交付物（outputs） | VerifySteps（可执行） | 验收门槛（客观） | 依赖 |
|---|---|---|---|---|---|
| T00_ENV_SETUP | ci | `requirements.txt`/`environment.yml` + `pre-commit` | `python -V`；`pip install -r ...`；`pre-commit run -a` | CI 环境可一键安装；lint 通过 | - |
| T01_MANIFEST_SCAN | manifest | `outputs/manifests/run_<ts>.json` | `python scripts/pipeline_run.py --stages manifest ...` | 文件数一致；sha256 可复现 | T00 |
| T02_IAGA_PARSER | ingest | `outputs/reports/dq_ingest_iaga.json` | `pytest -m unit -k iaga` | rows>0；sentinel 识别率=100%（fixtures） | T00 |
| T03_MSEED_INGEST | ingest | `outputs/reports/dq_ingest_mseed.json` | `pytest -m unit -k mseed` | trace_count>0；start<end | T00 |
| T04_STATIONXML_JOIN | ingest | `outputs/reports/station_match.json` | `pytest -m unit -k stationxml` | matched_ratio>=0.95；降级原因可追溯 | T03 |
| T05_VLF_CDF_INGEST | ingest | `outputs/raw/vlf/.../spectrogram.zarr` + `outputs/raw/vlf/.../vlf_meta.json` + `outputs/raw/vlf/.../vlf_gap_report.json` + `outputs/raw/vlf/.../vlf_preview.png` + `outputs/raw/vlf_catalog.parquet` + `outputs/reports/dq_ingest_vlf.json` | `pytest -m unit -k vlf` | shape/units/dt_median_s 合法；fill→NaN；gap_report 生成；preview 可打开 | T00 |
| T06_RAW_STORE | raw | `outputs/raw/.../*.parquet` + `outputs/reports/dq_raw.json` + `outputs/reports/compression.json` + `outputs/reports/compression_stats.json` | `python scripts/pipeline_run.py --stages ingest,raw .` | `/raw/query` 可按时空返回；dq_raw.rows>0；lossless 校验通过 | T02,T03,T04,(T05) |
| T07_STANDARD_PREPROCESS | standard | `outputs/standard/.../*.parquet` + `dq_standard.json` + `filter_effect.json` | `python scripts/pipeline_run.py --stages standard ...` | 缺失/异常/插值比例可统计；滤波证据存在 | T06 |
| T08_SPATIAL_INDEX | spatial | `outputs/reports/dq_spatial.json` | `pytest -m unit -k spatial` | rtree 查询 == brute-force | T04 |
| T09_LINK_EVENT | link | `outputs/linked/<event_id>/aligned.parquet` + `summary.json` + `dq_linked.json` | `python scripts/pipeline_run.py --stages link --event_id ...` | aligned 覆盖 N/M；join_coverage 输出且可解释 | T07,T08 |
| T10_FEATURES_EXTRACT | features | `outputs/features/<event_id>/features.parquet` + `dq_features.json` | `python scripts/pipeline_run.py --stages features --event_id ...` | 特征列齐全；NaN_ratio 可控（阈值可配） | T09 |
| T11_MODEL_RULEBOOK | model | `outputs/events/<event_id>/features/anomaly.parquet` + `outputs/models/rulebook.yaml` + `dq_anomaly.json` | `pytest -m integ -k anomaly` | score 范围合法；基线降级写明原因 | T10 |
| T12_PLOTS | plots | `outputs/plots/.../<event_id>/plot_*.{json,html}` + `dq_plots.json` | `python scripts/pipeline_run.py --stages plots --event_id ...` | ≥4 张核心图可渲染；downsample_info 存在 | T09,T11 |
| T13_FINALIZE_EVENT | finalize | `outputs/events/<event_id>/...` + `reports/artifacts_manifest.json` + (`DONE` 或 `FAIL`) + `reports/finalize_fail.json`(仅 FAIL) | `python scripts/finalize_event_package.py --event_id . --strict` | required_missing_count==0 → 写 DONE；否则写 FAIL + finalize_fail.json 且不写 DONE | T09,T11,T12 |
| T14_EVENT_BUNDLE | finalize | `outputs/events/<event_id>/event_bundle.zip` | `python scripts/make_event_bundle.py --event_id ...` | zip 可解压；报告/图链接离线可打开 | T13 |
| T15_FASTAPI | api | FastAPI 服务 + `/health` 等接口 | `pytest -m smoke`；`uvicorn ...` | raw/standard/linked/features/plots 200 + 字段齐全 | T06,T07,T09,T11,T12 |
| T16_UI_DASHBOARD | ui | `/ui` 页面（列表/详情/DQ） | 手工验收 + playwright（可选） | 事件列表显示 READY；详情页可渲染图 | T15 |
| T17_EXPORT | api | CSV/HDF5 导出（事件窗子集） | `GET /events/{id}/export?...` 或脚本 | 仅导出切片；不改 Raw | T15 |
| T18_DOCS | docs | `docs/data_dictionary.md` + `docs/api.md` + 本 plan | 文档自检（链接/路径） | 文档与代码一致；无死链 | T15 |

### 9.3 闭环验收规则（最重要）

- 任一任务完成必须提供**证据路径**（DQ/日志/图/返回 JSON），禁止“口头完成”。
- 端到端 READY 的判定以 `outputs/events/<event_id>/reports/artifacts_manifest.json` + `DONE` 且无 `FAIL` 为准（见 6.2.2）。
- 若数据客观缺失（例如事件窗无 VLF 覆盖），允许 READY=false，但必须：
  1) 生成 `event_summary.md`；2) 在报告中写 `MISSING:<reason>`；3) DQ 明确缺失原因与影响范围。
