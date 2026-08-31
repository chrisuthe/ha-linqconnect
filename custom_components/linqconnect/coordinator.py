"""Data update coordinator: one per district config entry."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import DayMenu, LinqConnectApiError, LinqConnectClient
from .const import (
    CONF_BUILDINGS,
    CONF_DISTRICT_ID,
    DOMAIN,
    FETCH_WINDOW_DAYS,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def fetch_window(today: date) -> tuple[date, date]:
    """Monday of the current week through +FETCH_WINDOW_DAYS days."""
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=FETCH_WINDOW_DAYS)


class LinqConnectCoordinator(DataUpdateCoordinator[dict[str, list[DayMenu]]]):
    """Fetches menus for every selected building in a district."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: LinqConnectClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.title}",
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, list[DayMenu]]:
        district_id: str = self.config_entry.data[CONF_DISTRICT_ID]
        buildings: dict[str, str] = self.config_entry.options[CONF_BUILDINGS]
        start, end = fetch_window(dt_util.now().date())
        data: dict[str, list[DayMenu]] = {}
        for building_id in buildings:
            try:
                data[building_id] = await self.client.get_menus(
                    district_id, building_id, start, end
                )
            except LinqConnectApiError as err:
                raise UpdateFailed(str(err)) from err
        return data
