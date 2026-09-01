"""Tests for the today's-menu sensors."""

from unittest.mock import MagicMock

from freezegun import freeze_time

from custom_components.linqconnect.api import DayMenu, MenuCategory
from custom_components.linqconnect.const import CONF_SESSIONS
from custom_components.linqconnect.sensor import LinqConnectMenuSensor

from .conftest import BUILDING_1

SENSOR = "sensor.inspiration_elementary_lunch"


async def _setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@freeze_time("2026-08-31 18:00:00")
async def test_today_state_and_attributes(hass, mock_config_entry, mock_api):
    await _setup(hass, mock_config_entry)
    state = hass.states.get(SENSOR)
    assert state is not None
    assert state.state == "Italian Dunkers / Bagel Bag / Garden Bar"
    assert state.attributes["meal_name"] == "Week 2 Monday"
    assert state.attributes["menu"]["Vegetable"] == ["Green Beans", "Baby Carrots"]
    assert state.attributes["district"] == "Brandon Valley School District"


@freeze_time("2026-09-02 18:00:00")
async def test_no_school_day_is_unknown(hass, mock_config_entry, mock_api):
    # fixture has an empty 9/2 → no DayMenu for today
    await _setup(hass, mock_config_entry)
    state = hass.states.get(SENSOR)
    assert state.state == "unknown"
    assert "menu" not in state.attributes


@freeze_time("2026-08-31 18:00:00")
async def test_one_sensor_per_session(hass, mock_config_entry, mock_api):
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_SESSIONS: ["Breakfast", "Lunch"],
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    breakfast = hass.states.get("sensor.inspiration_elementary_breakfast")
    assert breakfast is not None
    assert breakfast.state == "French Toast Sticks / Cereal Variety"
    assert hass.states.get(SENSOR) is not None


@freeze_time("2026-08-31 18:00:00")
def test_state_truncated_to_255():
    from datetime import date

    long_day = DayMenu(
        date=date(2026, 8, 31),
        session="Lunch",
        meal_name=None,
        categories=[
            MenuCategory(name="Main Entrée", items=["X" * 300])
        ],
    )
    coordinator = MagicMock()
    coordinator.data = {BUILDING_1: [long_day]}
    sensor = LinqConnectMenuSensor(
        coordinator, BUILDING_1, "Inspiration Elementary", "Lunch", "District"
    )
    assert len(sensor.native_value) == 255
