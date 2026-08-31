"""Config flow (stub until the real flow lands in Task 7)."""

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class LinqConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Placeholder flow so the config_flow platform imports."""

    VERSION = 1
