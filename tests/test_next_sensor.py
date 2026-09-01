"""Tests for the next-menu sensors."""

from freezegun import freeze_time
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.linqconnect.const import CONF_ROLLOVER_TIME

NEXT = "sensor.inspiration_elementary_next_lunch"


async def _setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


# hass test timezone is US/Pacific; 18:00 UTC = 11:00 local (before 13:00 cutoff)
@freeze_time("2026-08-31 18:00:00")
async def test_shows_today_before_rollover(hass, mock_config_entry, mock_api):
    await _setup(hass, mock_config_entry)
    state = hass.states.get(NEXT)
    assert state is not None
    assert state.state == "Italian Dunkers / Bagel Bag / Garden Bar"
    assert state.attributes["day"] == "Today"
    assert state.attributes["date"] == "2026-08-31"
    assert state.attributes["meal_name"] == "Week 2 Monday"
    assert state.attributes["menu"]["Vegetable"] == ["Green Beans", "Baby Carrots"]
    assert state.attributes["district"] == "Brandon Valley School District"


# 21:30 UTC = 14:30 local (after 13:00 cutoff) → next menu day is 9/1
@freeze_time("2026-08-31 21:30:00")
async def test_shows_tomorrow_after_rollover(hass, mock_config_entry, mock_api):
    await _setup(hass, mock_config_entry)
    state = hass.states.get(NEXT)
    assert state.state == "Crispy Chicken Sandwich"
    assert state.attributes["day"] == "Tomorrow"
    assert state.attributes["date"] == "2026-09-01"


# Saturday 8/29 11:00 local → next menu day is Monday 8/31 → weekday label
@freeze_time("2026-08-29 18:00:00")
async def test_weekend_skips_to_monday(hass, mock_config_entry, mock_api):
    await _setup(hass, mock_config_entry)
    state = hass.states.get(NEXT)
    assert state.state == "Italian Dunkers / Bagel Bag / Garden Bar"
    assert state.attributes["day"] == "Monday"
    assert state.attributes["date"] == "2026-08-31"


# 9/10 is past every fixture menu → nothing upcoming
@freeze_time("2026-09-10 18:00:00")
async def test_unknown_when_no_upcoming_menu(hass, mock_config_entry, mock_api):
    await _setup(hass, mock_config_entry)
    state = hass.states.get(NEXT)
    assert state.state == "unknown"
    assert "menu" not in state.attributes


# 19:00 UTC = 12:00 local — after a custom 11:00 cutoff → tomorrow already
@freeze_time("2026-08-31 19:00:00")
async def test_custom_rollover_time(hass, mock_config_entry, mock_api):
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, CONF_ROLLOVER_TIME: "11:00:00"},
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(NEXT)
    assert state.state == "Crispy Chicken Sandwich"
    assert state.attributes["date"] == "2026-09-01"


async def test_flips_at_rollover_without_refresh(hass, mock_config_entry, mock_api):
    # 12:30 local, before the 13:00 cutoff
    with freeze_time("2026-08-31 19:30:00") as frozen:
        await _setup(hass, mock_config_entry)
        assert hass.states.get(NEXT).state == "Italian Dunkers / Bagel Bag / Garden Bar"

        # cross the cutoff: 13:00:01 local, no coordinator refresh involved
        frozen.move_to("2026-08-31 20:00:01")
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()

        state = hass.states.get(NEXT)
        assert state.state == "Crispy Chicken Sandwich"
        assert state.attributes["day"] == "Tomorrow"
