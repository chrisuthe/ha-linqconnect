"""Tests for the calendar platform."""

from freezegun import freeze_time

from custom_components.linqconnect.api import LinqConnectApiError
from custom_components.linqconnect.const import CONF_SESSIONS

CAL = "calendar.inspiration_elementary"
SENSOR = "sensor.inspiration_elementary_lunch"


async def _setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _get_events(hass, start, end):
    result = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": CAL,
            "start_date_time": start,
            "end_date_time": end,
        },
        blocking=True,
        return_response=True,
    )
    return result[CAL]["events"]


@freeze_time("2026-08-31 18:00:00")
async def test_all_day_lunch_events(hass, mock_config_entry, mock_api):
    await _setup(hass, mock_config_entry)

    state = hass.states.get(CAL)
    assert state is not None
    # today's lunch is the current event
    assert state.state == "on"
    assert state.attributes["all_day"] is True
    assert state.attributes["message"] == "Italian Dunkers / Bagel Bag / Garden Bar"

    events = await _get_events(hass, "2026-08-31 00:00:00", "2026-09-04 00:00:00")
    # Lunch only (Breakfast filtered out): 8/31 and 9/1
    assert len(events) == 2
    assert events[0]["summary"] == "Italian Dunkers / Bagel Bag / Garden Bar"
    assert events[0]["start"] == "2026-08-31"
    assert events[0]["end"] == "2026-09-01"  # exclusive end
    assert "Vegetable: Green Beans, Baby Carrots" in events[0]["description"]
    assert events[0]["location"] == "Inspiration Elementary"
    assert events[1]["summary"] == "Crispy Chicken Sandwich"


@freeze_time("2026-08-31 18:00:00")
async def test_window_filtering(hass, mock_config_entry, mock_api):
    await _setup(hass, mock_config_entry)
    events = await _get_events(hass, "2026-09-01 00:00:00", "2026-09-04 00:00:00")
    assert [e["summary"] for e in events] == ["Crispy Chicken Sandwich"]


@freeze_time("2026-08-31 18:00:00")
async def test_stays_available_on_failed_refresh(hass, mock_config_entry, mock_api):
    await _setup(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    mock_api.get_menus.side_effect = LinqConnectApiError("down")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    cal_state = hass.states.get(CAL)
    assert cal_state.state == "on"
    sensor_state = hass.states.get(SENSOR)
    assert sensor_state.state == "Italian Dunkers / Bagel Bag / Garden Bar"


@freeze_time("2026-08-31 18:00:00")
async def test_multi_session_prefixes_summary(hass, mock_config_entry, mock_api):
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
    events = await _get_events(hass, "2026-08-31 00:00:00", "2026-09-01 00:00:00")
    assert [e["summary"] for e in events] == [
        "Breakfast: French Toast Sticks / Cereal Variety",
        "Lunch: Italian Dunkers / Bagel Bag / Garden Bar",
    ]
