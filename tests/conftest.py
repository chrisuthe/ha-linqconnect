"""Shared test fixtures."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.linqconnect.api import parse_district, parse_menus
from custom_components.linqconnect.const import (
    CONF_BUILDINGS,
    CONF_DISTRICT_ID,
    CONF_DISTRICT_NAME,
    CONF_IDENTIFIER,
    CONF_SESSIONS,
    DOMAIN,
)

FIXTURES = Path(__file__).parent / "fixtures"

DISTRICT_ID = "b1d7358a-818b-ec11-90c7-d2d97b40e955"
BUILDING_1 = "0c65b2bc-908d-ec11-8df7-9566c4096294"
BUILDING_2 = "041717d0-8f8d-ec11-8df7-eb7b319a32d1"


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


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A configured Brandon Valley entry with one school, Lunch only."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Brandon Valley School District",
        unique_id=DISTRICT_ID,
        data={
            CONF_DISTRICT_ID: DISTRICT_ID,
            CONF_DISTRICT_NAME: "Brandon Valley School District",
            CONF_IDENTIFIER: "AZB89G",
        },
        options={
            CONF_BUILDINGS: {BUILDING_1: "Inspiration Elementary"},
            CONF_SESSIONS: ["Lunch"],
        },
    )


@pytest.fixture
def mock_api(load_fixture):
    """Patch the client class used by async_setup_entry; yield its instance."""
    district = parse_district(load_fixture("family_menu_identifier.json"))
    menus = parse_menus(load_fixture("family_menu.json"))
    with patch(
        "custom_components.linqconnect.LinqConnectClient", autospec=True
    ) as mock_cls:
        client = mock_cls.return_value
        client.resolve_identifier.return_value = district
        client.get_menus.return_value = menus
        yield client
