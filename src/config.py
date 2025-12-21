import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def compute_params_hash(config: Dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def get_event(config: Dict[str, Any], event_id: Optional[str]) -> Dict[str, Any]:
    events = config.get("events") or []
    if event_id is None:
        if not events:
            raise ValueError("No events configured and no event_id provided.")
        return events[0]
    for event in events:
        if event.get("event_id") == event_id:
            return event
    raise ValueError(f"Event_id not found in config: {event_id}")
