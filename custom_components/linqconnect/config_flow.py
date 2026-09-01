"""Config flow for LINQ Connect Menus."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TimeSelector

from .api import (
    District,
    DistrictNotFoundError,
    LinqConnectApiError,
    LinqConnectClient,
)
from .const import (
    CONF_BUILDINGS,
    CONF_DISTRICT_ID,
    CONF_DISTRICT_NAME,
    CONF_IDENTIFIER,
    CONF_ROLLOVER_TIME,
    CONF_SESSIONS,
    CONF_SHARE_CODE,
    DEFAULT_ROLLOVER_TIME,
    DEFAULT_SESSIONS,
    DOMAIN,
    SESSION_CHOICES,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SHARE_CODE): str,
        vol.Optional(CONF_DISTRICT_NAME): str,
    }
)


class LinqConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Identify a district, then pick its schools and serving sessions."""

    VERSION = 1

    def __init__(self) -> None:
        self._district: District | None = None
        self._matches: list[District] = []

    def _client(self) -> LinqConnectClient:
        return LinqConnectClient(async_get_clientsession(self.hass))

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Accept a share code or a district name to search for."""
        errors: dict[str, str] = {}
        if user_input is not None:
            code = (user_input.get(CONF_SHARE_CODE) or "").strip()
            name = (user_input.get(CONF_DISTRICT_NAME) or "").strip()
            if code:
                try:
                    self._district = await self._client().resolve_identifier(code)
                except DistrictNotFoundError:
                    errors[CONF_SHARE_CODE] = "district_not_found"
                except LinqConnectApiError as err:
                    _LOGGER.warning("LINQ Connect API error: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    return await self._async_district_resolved()
            elif name:
                try:
                    self._matches = await self._client().search_districts(name)
                except LinqConnectApiError as err:
                    _LOGGER.warning("LINQ Connect API error: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    if not self._matches:
                        errors[CONF_DISTRICT_NAME] = "no_results"
                    else:
                        return await self.async_step_pick_district()
            else:
                errors["base"] = "missing_input"
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_pick_district(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick one district from the search results."""
        errors: dict[str, str] = {}
        options = {
            d.district_id: f"{d.name} — {d.city}, {d.state}" for d in self._matches
        }
        if user_input is not None:
            match = next(
                d
                for d in self._matches
                if d.district_id == user_input[CONF_DISTRICT_ID]
            )
            try:
                self._district = await self._client().resolve_identifier(
                    match.identifier
                )
            except LinqConnectApiError as err:
                _LOGGER.warning("LINQ Connect API error: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return await self._async_district_resolved()
        return self.async_show_form(
            step_id="pick_district",
            data_schema=vol.Schema(
                {vol.Required(CONF_DISTRICT_ID): vol.In(options)}
            ),
            errors=errors,
        )

    async def _async_district_resolved(self) -> ConfigFlowResult:
        assert self._district is not None
        await self.async_set_unique_id(self._district.district_id)
        self._abort_if_unique_id_configured()
        return await self.async_step_schools()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> LinqConnectOptionsFlow:
        """Return the options flow."""
        return LinqConnectOptionsFlow()

    async def async_step_schools(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick schools and serving sessions."""
        assert self._district is not None
        errors: dict[str, str] = {}
        buildings = {b.building_id: b.name for b in self._district.buildings}
        if user_input is not None:
            if not user_input[CONF_BUILDINGS]:
                errors[CONF_BUILDINGS] = "no_schools"
            elif not user_input[CONF_SESSIONS]:
                errors[CONF_SESSIONS] = "no_sessions"
            else:
                return self.async_create_entry(
                    title=self._district.name,
                    data={
                        CONF_DISTRICT_ID: self._district.district_id,
                        CONF_DISTRICT_NAME: self._district.name,
                        CONF_IDENTIFIER: self._district.identifier,
                    },
                    options={
                        CONF_BUILDINGS: {
                            building_id: buildings[building_id]
                            for building_id in user_input[CONF_BUILDINGS]
                        },
                        CONF_SESSIONS: user_input[CONF_SESSIONS],
                    },
                )
        return self.async_show_form(
            step_id="schools",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BUILDINGS, default=[]): cv.multi_select(
                        buildings
                    ),
                    vol.Required(
                        CONF_SESSIONS, default=DEFAULT_SESSIONS
                    ): cv.multi_select(SESSION_CHOICES),
                }
            ),
            errors=errors,
        )


class LinqConnectOptionsFlow(OptionsFlow):
    """Change selected schools and sessions; building list is re-fetched."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self.config_entry
        client = LinqConnectClient(async_get_clientsession(self.hass))
        try:
            district = await client.resolve_identifier(entry.data[CONF_IDENTIFIER])
        except LinqConnectApiError as err:
            _LOGGER.warning("LINQ Connect API error: %s", err)
            return self.async_abort(reason="cannot_connect")
        buildings = {b.building_id: b.name for b in district.buildings}
        if user_input is not None:
            if not user_input[CONF_BUILDINGS]:
                errors[CONF_BUILDINGS] = "no_schools"
            elif not user_input[CONF_SESSIONS]:
                errors[CONF_SESSIONS] = "no_sessions"
            else:
                return self.async_create_entry(
                    data={
                        CONF_BUILDINGS: {
                            building_id: buildings[building_id]
                            for building_id in user_input[CONF_BUILDINGS]
                        },
                        CONF_SESSIONS: user_input[CONF_SESSIONS],
                        CONF_ROLLOVER_TIME: user_input[CONF_ROLLOVER_TIME],
                    }
                )
        current = entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BUILDINGS,
                        default=list(current.get(CONF_BUILDINGS, {})),
                    ): cv.multi_select(buildings),
                    vol.Required(
                        CONF_SESSIONS,
                        default=current.get(CONF_SESSIONS, DEFAULT_SESSIONS),
                    ): cv.multi_select(SESSION_CHOICES),
                    vol.Required(
                        CONF_ROLLOVER_TIME,
                        default=current.get(
                            CONF_ROLLOVER_TIME, DEFAULT_ROLLOVER_TIME
                        ),
                    ): TimeSelector(),
                }
            ),
            errors=errors,
        )
