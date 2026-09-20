"""Constants for the PiHerder Home Assistant integration (Slice 1)."""
from __future__ import annotations

import json
from pathlib import Path

DOMAIN = "piherder"


def _manifest_version() -> str:
    try:
        raw = Path(__file__).with_name("manifest.json").read_text(encoding="utf-8")
        return str(json.loads(raw).get("version") or "0")
    except Exception:
        return "0"


INTEGRATION_VERSION = _manifest_version()
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15
MAX_SCAN_INTERVAL = 600
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"
