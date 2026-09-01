"""Tests for the data update coordinator."""

from datetime import date
from unittest.mock import AsyncMock

import pytest
from freezegun import freeze_time
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.linqconnect.api import LinqConnectApiError, parse_menus
from custom_components.linqconnect.const import (
    CONF_BUILDINGS,
    CONF_DISTRICT_ID,
    CONF_DISTRICT_NAME,
    CONF_IDENTIFIER,
    CONF_SESSIONS,
    DOMAIN,
)
from custom_components.linqconnect.coordinator import (
    LinqConnectCoordinator,
    fetch_window,
)

DISTRICT_ID = "b1d7358a-818b-ec11-90c7-d2d97b40e955"
BUILDING_1 = "0c65b2bc-908d-ec11-8df7-9566c4096294"


def _entry() -> MockConfigEntry:
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


def test_fetch_window_on_a_monday():
    assert fetch_window(date(2026, 8, 31)) == (date(2026, 8, 31), date(2026, 10, 12))


def test_fetch_window_mid_week_snaps_to_monday():
    assert fetch_window(date(2026, 9, 3)) == (date(2026, 8, 31), date(2026, 10, 12))


@freeze_time("2026-08-31 12:00:00")
async def test_update_fetches_each_building(hass, load_fixture):
    entry = _entry()
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.get_menus.return_value = parse_menus(load_fixture("family_menu.json"))
    coordinator = LinqConnectCoordinator(hass, entry, client)

    data = await coordinator._async_update_data()

    assert set(data) == {BUILDING_1}
    assert len(data[BUILDING_1]) == 3
    client.get_menus.assert_awaited_once_with(
        DISTRICT_ID, BUILDING_1, date(2026, 8, 31), date(2026, 10, 12)
    )


async def test_api_error_becomes_update_failed(hass):
    entry = _entry()
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.get_menus.side_effect = LinqConnectApiError("WAF blocked")
    coordinator = LinqConnectCoordinator(hass, entry, client)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
