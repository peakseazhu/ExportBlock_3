from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from src.store.parquet import read_parquet
from src.utils import ensure_dir, write_json


def _write_plot(fig: go.Figure, spec_path: Path, html_path: Path) -> None:
    ensure_dir(spec_path.parent)
    ensure_dir(html_path.parent)
    spec_path.write_text(pio.to_json(fig), encoding="utf-8")
    fig.write_html(str(html_path), include_plotlyjs="cdn")


def run_plots(
    base_dir: Path,
    config: Dict[str, Any],
    output_paths,
    run_id: str,
    params_hash: str,
    strict: bool,
    event_id: str | None,
) -> None:
    if event_id is None:
        event_id = (config.get("events") or [{}])[0].get("event_id")
    linked_dir = output_paths.linked / event_id
    aligned_path = linked_dir / "aligned.parquet"
    aligned_df = pd.read_parquet(aligned_path) if aligned_path.exists() else pd.DataFrame()

    plots_html_dir = output_paths.plots / "html" / event_id
    plots_spec_dir = output_paths.plots / "spec" / event_id
    dq = {}

    # Plot 1: aligned timeseries (top 3 channels)
    if not aligned_df.empty:
        aligned_df["ts"] = pd.to_datetime(aligned_df["ts_ms"], unit="ms", utc=True)
        top_channels = (
            aligned_df.groupby("channel")["value"].count().sort_values(ascending=False).head(3).index.tolist()
        )
        fig = go.Figure()
        for channel in top_channels:
            subset = aligned_df[aligned_df["channel"] == channel].sort_values("ts")
            fig.add_trace(go.Scatter(x=subset["ts"], y=subset["value"], mode="lines", name=channel))
        fig.update_layout(title="Aligned Timeseries", xaxis_title="Time (UTC)", yaxis_title="Value")
        _write_plot(fig, plots_spec_dir / "plot_aligned_timeseries.json", plots_html_dir / "plot_aligned_timeseries.html")
        dq["aligned_timeseries"] = "ok"
    else:
        dq["aligned_timeseries"] = "missing: no aligned data"

    # Plot 2: station map
    if not aligned_df.empty and aligned_df["lat"].notna().any():
        stations = (
            aligned_df.dropna(subset=["lat", "lon"])[["station_id", "lat", "lon"]]
            .drop_duplicates()
            .reset_index(drop=True)
        )
        fig = go.Figure(
            go.Scattergeo(
                lon=stations["lon"],
                lat=stations["lat"],
                text=stations["station_id"],
                mode="markers",
            )
        )
        fig.update_layout(title="Station Map")
        _write_plot(fig, plots_spec_dir / "plot_station_map.json", plots_html_dir / "plot_station_map.html")
        dq["station_map"] = "ok"
    else:
        dq["station_map"] = "missing: no station coordinates"

    # Plot 3: filter effect
    filter_effect_path = output_paths.reports / "filter_effect.json"
    if filter_effect_path.exists():
        filter_effect = json.loads(filter_effect_path.read_text(encoding="utf-8"))
        sources = list(filter_effect.keys())
        before = [filter_effect[s].get("before_std") for s in sources]
        after = [filter_effect[s].get("after_std") for s in sources]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=sources, y=before, name="before_std"))
        fig.add_trace(go.Bar(x=sources, y=after, name="after_std"))
        fig.update_layout(title="Filter Effect", barmode="group", yaxis_title="Std")
        _write_plot(fig, plots_spec_dir / "plot_filter_effect.json", plots_html_dir / "plot_filter_effect.html")
        dq["filter_effect"] = "ok"
    else:
        dq["filter_effect"] = "missing: filter_effect.json not found"

    # Plot 4: VLF spectrogram (optional)
    vlf_dir = output_paths.raw / "vlf"
    spectro_written = False
    if vlf_dir.exists():
        for station_dir in vlf_dir.glob("*"):
            for run_dir in station_dir.glob("*"):
                zarr_path = run_dir / "spectrogram.zarr"
                if not zarr_path.exists():
                    continue
                import zarr

                root = zarr.open(str(zarr_path), mode="r")
                epoch_ns = root["epoch_ns"][:]
                freq = root["freq_hz"][:]
                ch1 = root["ch1"][:]
                fig = go.Figure(
                    data=go.Heatmap(
                        z=np.log10(ch1 + 1e-12).T,
                        x=pd.to_datetime(epoch_ns, unit="ns"),
                        y=freq,
                        colorscale="Viridis",
                    )
                )
                fig.update_layout(title="VLF Spectrogram (CH1)", xaxis_title="Time", yaxis_title="Freq (Hz)")
                _write_plot(
                    fig,
                    plots_spec_dir / "plot_vlf_spectrogram.json",
                    plots_html_dir / "plot_vlf_spectrogram.html",
                )
                spectro_written = True
                break
            if spectro_written:
                break
    dq["vlf_spectrogram"] = "ok" if spectro_written else "missing: no vlf data"

    write_json(plots_spec_dir / "dq_plots.json", dq)
    write_json(output_paths.reports / "dq_plots.json", dq)
