"""Today's-menu sensors: one per (building, serving session)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from . import LinqConnectConfigEntry
from .api import DayMenu
from .const import (
    CONF_BUILDINGS,
    CONF_DISTRICT_NAME,
    CONF_SESSIONS,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .coordinator import LinqConnectCoordinator
from .menu_format import menu_dict, summary


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinqConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one sensor per building per selected session."""
    coordinator = entry.runtime_data
    district_name = entry.data[CONF_DISTRICT_NAME]
    async_add_entities(
        LinqConnectMenuSensor(coordinator, building_id, name, session, district_name)
        for building_id, name in entry.options[CONF_BUILDINGS].items()
        for session in entry.options[CONF_SESSIONS]
    )


class LinqConnectMenuSensor(
    CoordinatorEntity[LinqConnectCoordinator], SensorEntity
):
    """Today's menu for one school and serving session."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LinqConnectCoordinator,
        building_id: str,
        building_name: str,
        session: str,
        district_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._building_id = building_id
        self._session = session
        self._district_name = district_name
        self._attr_name = session
        self._attr_unique_id = f"{building_id}_{slugify(session)}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, building_id)},
            name=building_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    def _today(self) -> DayMenu | None:
        today = dt_util.now().date()
        for day in (self.coordinator.data or {}).get(self._building_id, []):
            if day.date == today and day.session.casefold() == self._session.casefold():
                return day
        return None

    @property
    def native_value(self) -> str | None:
        day = self._today()
        if day is None:
            return None
        return summary(day)[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        day = self._today()
        if day is None:
            return {"district": self._district_name}
        return {
            "district": self._district_name,
            "meal_name": day.meal_name,
            "menu": menu_dict(day),
        }
