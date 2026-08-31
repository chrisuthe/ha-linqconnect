"""Tests for entry setup, unload, and device removal."""

from freezegun import freeze_time
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr

from custom_components.linqconnect import async_remove_config_entry_device
from custom_components.linqconnect.api import LinqConnectApiError
from custom_components.linqconnect.const import DOMAIN

from .conftest import BUILDING_1


@freeze_time("2026-08-31 12:00:00")
async def test_setup_and_unload(hass, mock_config_entry, mock_api):
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("calendar.inspiration_elementary") is not None
    assert hass.states.get("sensor.inspiration_elementary_lunch") is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_api_error_at_setup_retries(hass, mock_config_entry, mock_api):
    mock_api.get_menus.side_effect = LinqConnectApiError("down")
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@freeze_time("2026-08-31 12:00:00")
async def test_remove_device_only_for_unselected_buildings(
    hass, mock_config_entry, mock_api
):
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registry = dr.async_get(hass)
    current = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, BUILDING_1)},
    )
    assert current is not None
    assert (
        await async_remove_config_entry_device(hass, mock_config_entry, current)
        is False
    )

    stale = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "stale-building-id")},
    )
    assert (
        await async_remove_config_entry_device(hass, mock_config_entry, stale) is True
    )
