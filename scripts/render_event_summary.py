import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from jinja2 import Template

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))


def _load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _load_anomalies(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_parquet(path)


def _format_top_anomalies(df: pd.DataFrame | None) -> str:
    if df is None:
        return "No anomaly file"
    if df.empty:
        return "No anomalies above threshold"
    headers = df.columns.tolist()
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in headers) + " |")
    return "\n".join(lines)


def _plot_ref(report_dir: Path, plot_path: Path) -> str:
    if plot_path.exists():
        event_dir = report_dir.parent
        rel = plot_path.relative_to(event_dir)
        return str(Path("..") / rel)
    return ""


def render_event_summary(
    event_id: str, output_root: Path, format_type: str, event_dir: Path | None = None
) -> Path:
    event_dir = event_dir or (output_root / "events" / event_id)
    report_dir = event_dir / "reports"
    plot_dir = event_dir / "plots" / "html"
    ensure_event_dir = report_dir
    ensure_event_dir.mkdir(parents=True, exist_ok=True)

    event_meta = _load_json(event_dir / "event.json", {})
    linked_summary = _load_json(event_dir / "linked" / "summary.json", {})

    dq_event_link = _load_json(report_dir / "dq_event_link.json") or _load_json(
        output_root / "linked" / event_id / "dq_linked.json", {}
    )
    dq_event_features = _load_json(report_dir / "dq_event_features.json") or _load_json(
        output_root / "features" / event_id / "dq_features.json", {}
    )
    dq_plots = _load_json(report_dir / "dq_plots.json") or _load_json(
        output_root / "plots" / "spec" / event_id / "dq_plots.json", {}
    )
    filter_effect = _load_json(report_dir / "filter_effect.json") or _load_json(
        output_root / "reports" / "filter_effect.json", {}
    )

    anomalies = _load_anomalies(event_dir / "features" / "anomaly.parquet")
    top_anomalies_table = _format_top_anomalies(anomalies)

    plots = {
        "aligned": plot_dir / "plot_aligned_timeseries.html",
        "station": plot_dir / "plot_station_map.html",
        "filter": plot_dir / "plot_filter_effect.html",
        "vlf": plot_dir / "plot_vlf_spectrogram.html",
    }

    context = {
        "event_id": event_meta.get("event_id", event_id),
        "event_name": event_meta.get("name", ""),
        "origin_time_utc": event_meta.get("origin_time_utc", ""),
        "lat": event_meta.get("lat", ""),
        "lon": event_meta.get("lon", ""),
        "params_hash": event_meta.get("params_hash", ""),
        "pipeline_version": event_meta.get("pipeline_version", ""),
        "dq_event_link_path": "dq_event_link.json",
        "dq_event_features_path": "dq_event_features.json",
        "dq_plots_path": "dq_plots.json",
        "filter_effect_path": "filter_effect.json",
        "linked_summary": json.dumps(linked_summary, ensure_ascii=False, indent=2),
        "top_anomalies_table": top_anomalies_table,
        "plot_aligned_timeseries_html": _plot_ref(report_dir, plots["aligned"]) or "",
        "plot_station_map_html": _plot_ref(report_dir, plots["station"]) or "",
        "plot_filter_effect_html": _plot_ref(report_dir, plots["filter"]) or "",
        "plot_vlf_spectrogram_html": _plot_ref(report_dir, plots["vlf"]) or "",
        "plot_aligned_timeseries_missing": "" if plots["aligned"].exists() else "MISSING: plot_aligned_timeseries.html",
        "plot_station_map_missing": "" if plots["station"].exists() else "MISSING: plot_station_map.html",
        "plot_filter_effect_missing": "" if plots["filter"].exists() else "MISSING: plot_filter_effect.html",
        "plot_vlf_spectrogram_missing": "" if plots["vlf"].exists() else "MISSING: plot_vlf_spectrogram.html",
        "reproduce_cmd": f"python scripts/pipeline_run.py --stages link,features,model,plots --event_id {event_id}",
        "notes": json.dumps(
            {
                "dq_event_link": dq_event_link,
                "dq_event_features": dq_event_features,
                "dq_plots": dq_plots,
                "filter_effect": filter_effect,
            },
            ensure_ascii=False,
            indent=2,
        ),
    }

    template_path = ROOT / "templates" / "event_summary_template_v3.md"
    template = Template(template_path.read_text(encoding="utf-8"))
    markdown = template.render(**context)

    md_path = report_dir / "event_summary.md"
    md_path.write_text(markdown, encoding="utf-8")

    if format_type in {"html", "both"}:
        html_path = report_dir / "event_summary.html"
        html_path.write_text(f"<pre>{markdown}</pre>", encoding="utf-8")

    return md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render event summary report.")
    parser.add_argument("--event_id", required=True)
    parser.add_argument("--format", default="md", choices=["md", "html", "both"])
    args = parser.parse_args()
    render_event_summary(args.event_id, ROOT / "outputs", args.format)


if __name__ == "__main__":
    main()
