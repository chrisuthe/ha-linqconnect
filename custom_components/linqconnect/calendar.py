"""Calendar entities: one per selected school building."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import LinqConnectConfigEntry
from .api import DayMenu
from .const import CONF_BUILDINGS, CONF_SESSIONS, DOMAIN, MANUFACTURER, MODEL
from .coordinator import LinqConnectCoordinator
from .menu_format import description, summary


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinqConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one calendar per selected building."""
    coordinator = entry.runtime_data
    sessions: list[str] = entry.options[CONF_SESSIONS]
    async_add_entities(
        LinqConnectCalendar(coordinator, building_id, name, sessions)
        for building_id, name in entry.options[CONF_BUILDINGS].items()
    )


class LinqConnectCalendar(
    CoordinatorEntity[LinqConnectCoordinator], CalendarEntity
):
    """All-day menu events for one school."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: LinqConnectCoordinator,
        building_id: str,
        building_name: str,
        sessions: list[str],
    ) -> None:
        super().__init__(coordinator)
        self._building_id = building_id
        self._building_name = building_name
        self._sessions = {s.casefold() for s in sessions}
        self._multi_session = len(sessions) > 1
        self._attr_unique_id = building_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, building_id)},
            name=building_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    def _days(self) -> list[DayMenu]:
        return sorted(
            (
                day
                for day in (self.coordinator.data or {}).get(self._building_id, [])
                if day.session.casefold() in self._sessions
            ),
            key=lambda day: (day.date, day.session),
        )

    def _to_event(self, day: DayMenu) -> CalendarEvent:
        event_summary = summary(day)
        if self._multi_session:
            event_summary = f"{day.session}: {event_summary}"
        return CalendarEvent(
            summary=event_summary,
            start=day.date,
            end=day.date + timedelta(days=1),
            description=description(day),
            location=self._building_name,
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Today's event (current until midnight) or the next upcoming one."""
        today = dt_util.now().date()
        for day in self._days():
            if day.date >= today:
                return self._to_event(day)
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return events overlapping [start_date, end_date)."""
        events = []
        for day in self._days():
            ev_start = dt_util.start_of_local_day(day.date)
            if ev_start < end_date and ev_start + timedelta(days=1) > start_date:
                events.append(self._to_event(day))
        return events
