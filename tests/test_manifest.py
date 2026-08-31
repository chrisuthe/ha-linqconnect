"""Smoke tests: package imports and manifest is sane."""

import json
from pathlib import Path

from custom_components.linqconnect.const import DOMAIN

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_matches_domain():
    manifest = json.loads(
        (ROOT / "custom_components" / "linqconnect" / "manifest.json").read_text()
    )
    assert manifest["domain"] == DOMAIN
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "cloud_polling"
    assert manifest["requirements"] == []
