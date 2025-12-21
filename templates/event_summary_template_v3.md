# 0. 事件基本信息
- event_id: {{ event_id }}
- name: {{ event_name }}
- origin_time_utc: {{ origin_time_utc }}
- location: ({{ lat }}, {{ lon }})
- params_hash: {{ params_hash }}
- pipeline_version: {{ pipeline_version }}

# 1. 数据覆盖与质量
- dq_event_link: {{ dq_event_link_path }}
- dq_event_features: {{ dq_event_features_path }}
- dq_plots: {{ dq_plots_path }}
- filter_effect: {{ filter_effect_path }}

# 2. 关联结果概览
{{ linked_summary }}

# 3. 特征与异常
{{ top_anomalies_table }}

# 4. 证据图与可视化
- aligned_timeseries: {{ plot_aligned_timeseries_html }} {{ plot_aligned_timeseries_missing }}
- station_map: {{ plot_station_map_html }} {{ plot_station_map_missing }}
- filter_effect: {{ plot_filter_effect_html }} {{ plot_filter_effect_missing }}
- vlf_spectrogram: {{ plot_vlf_spectrogram_html }} {{ plot_vlf_spectrogram_missing }}

# 5. 可复现命令
{{ reproduce_cmd }}

# 6. 备注
{{ notes }}
