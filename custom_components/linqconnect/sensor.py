"""Menu sensors: today's and next upcoming, per (building, serving session)."""

from __future__ import annotations

from datetime import date, time, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from . import LinqConnectConfigEntry
from .api import DayMenu
from .const import (
    CONF_BUILDINGS,
    CONF_DISTRICT_NAME,
    CONF_ROLLOVER_TIME,
    CONF_SESSIONS,
    DEFAULT_ROLLOVER_TIME,
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
    """Set up today's and next-menu sensors per building per selected session."""
    coordinator = entry.runtime_data
    district_name = entry.data[CONF_DISTRICT_NAME]
    rollover = time.fromisoformat(
        entry.options.get(CONF_ROLLOVER_TIME, DEFAULT_ROLLOVER_TIME)
    )
    entities: list[SensorEntity] = []
    for building_id, name in entry.options[CONF_BUILDINGS].items():
        for session in entry.options[CONF_SESSIONS]:
            entities.append(
                LinqConnectMenuSensor(
                    coordinator, building_id, name, session, district_name
                )
            )
            entities.append(
                LinqConnectNextMenuSensor(
                    coordinator, building_id, name, session, district_name, rollover
                )
            )
    async_add_entities(entities)


class LinqConnectBaseMenuSensor(
    CoordinatorEntity[LinqConnectCoordinator], SensorEntity
):
    """Common device, availability, and data access for menu sensors."""

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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, building_id)},
            name=building_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        """Stay available on stale data while the API is unreachable."""
        return (
            super().available
            or self._building_id in (self.coordinator.data or {})
        )

    def _session_days(self) -> list[DayMenu]:
        """This building's menus for this session, sorted by date."""
        return sorted(
            (
                day
                for day in (self.coordinator.data or {}).get(self._building_id, [])
                if day.session.casefold() == self._session.casefold()
            ),
            key=lambda day: day.date,
        )


class LinqConnectMenuSensor(LinqConnectBaseMenuSensor):
    """Today's menu for one school and serving session."""

    def __init__(
        self,
        coordinator: LinqConnectCoordinator,
        building_id: str,
        building_name: str,
        session: str,
        district_name: str,
    ) -> None:
        super().__init__(
            coordinator, building_id, building_name, session, district_name
        )
        self._attr_name = session
        self._attr_unique_id = f"{building_id}_{slugify(session)}"

    def _today(self) -> DayMenu | None:
        today = dt_util.now().date()
        for day in self._session_days():
            if day.date == today:
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


class LinqConnectNextMenuSensor(LinqConnectBaseMenuSensor):
    """The next upcoming menu: today's until the rollover time, then the next
    day that has a published menu (skipping weekends and no-school days)."""

    def __init__(
        self,
        coordinator: LinqConnectCoordinator,
        building_id: str,
        building_name: str,
        session: str,
        district_name: str,
        rollover: time,
    ) -> None:
        super().__init__(
            coordinator, building_id, building_name, session, district_name
        )
        self._rollover = rollover
        self._attr_name = f"Next {session}"
        self._attr_unique_id = f"{building_id}_next_{slugify(session)}"

    async def async_added_to_hass(self) -> None:
        """Re-render when the clock crosses the rollover time or midnight."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_change(
                self.hass,
                self._handle_clock,
                hour=self._rollover.hour,
                minute=self._rollover.minute,
                second=self._rollover.second,
            )
        )
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._handle_clock, hour=0, minute=0, second=0
            )
        )

    @callback
    def _handle_clock(self, now) -> None:
        self.async_write_ha_state()

    def _next(self) -> DayMenu | None:
        now = dt_util.now()
        for day in self._session_days():
            if day.date > now.date() or (
                day.date == now.date() and now.time() < self._rollover
            ):
                return day
        return None

    def _day_label(self, target: date) -> str:
        today = dt_util.now().date()
        if target == today:
            return "Today"
        if target == today + timedelta(days=1):
            return "Tomorrow"
        return target.strftime("%A")

    @property
    def native_value(self) -> str | None:
        day = self._next()
        if day is None:
            return None
        return summary(day)[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        day = self._next()
        if day is None:
            return {"district": self._district_name}
        return {
            "district": self._district_name,
            "date": day.date.isoformat(),
            "day": self._day_label(day.date),
            "meal_name": day.meal_name,
            "menu": menu_dict(day),
        }
