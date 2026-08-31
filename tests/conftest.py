"""Shared test fixtures."""

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow tests to load custom_components/linqconnect."""
    yield


@pytest.fixture
def load_fixture():
    """Return a loader for JSON fixture files."""

    def _load(name: str) -> dict:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    return _load
