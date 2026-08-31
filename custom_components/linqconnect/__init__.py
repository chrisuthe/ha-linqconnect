"""The LINQ Connect Menus integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LinqConnectClient
from .const import CONF_BUILDINGS, DOMAIN
from .coordinator import LinqConnectCoordinator

PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.SENSOR]

type LinqConnectConfigEntry = ConfigEntry[LinqConnectCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: LinqConnectConfigEntry
) -> bool:
    """Set up a district from a config entry."""
    client = LinqConnectClient(async_get_clientsession(hass))
    coordinator = LinqConnectCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: LinqConnectConfigEntry
) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: LinqConnectConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: LinqConnectConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Allow deleting devices for buildings no longer selected."""
    selected = set(entry.options.get(CONF_BUILDINGS, {}))
    return not any(
        identifier[0] == DOMAIN and identifier[1] in selected
        for identifier in device.identifiers
    )
