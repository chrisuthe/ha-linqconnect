"""Tests for the options flow."""

from unittest.mock import patch

from freezegun import freeze_time
from homeassistant.data_entry_flow import FlowResultType

from custom_components.linqconnect.api import parse_district
from custom_components.linqconnect.const import (
    CONF_BUILDINGS,
    CONF_ROLLOVER_TIME,
    CONF_SESSIONS,
)

from .conftest import BUILDING_1, BUILDING_2


@freeze_time("2026-08-31 18:00:00")
async def test_options_flow_updates_and_reloads(
    hass, mock_config_entry, mock_api, load_fixture
):
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    district = parse_district(load_fixture("family_menu_identifier.json"))
    with patch(
        "custom_components.linqconnect.config_flow.LinqConnectClient", autospec=True
    ) as mock_cls:
        mock_cls.return_value.resolve_identifier.return_value = district
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_BUILDINGS: [BUILDING_1, BUILDING_2],
                CONF_SESSIONS: ["Breakfast", "Lunch"],
            },
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_BUILDINGS] == {
        BUILDING_1: "Inspiration Elementary",
        BUILDING_2: "Brandon Elementary",
    }
    assert mock_config_entry.options[CONF_SESSIONS] == ["Breakfast", "Lunch"]
    # reload happened: new building's entities exist now
    assert hass.states.get("calendar.brandon_elementary") is not None
    assert hass.states.get("sensor.brandon_elementary_breakfast") is not None


@freeze_time("2026-08-31 18:00:00")
async def test_options_flow_no_schools_error(
    hass, mock_config_entry, mock_api, load_fixture
):
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    district = parse_district(load_fixture("family_menu_identifier.json"))
    with patch(
        "custom_components.linqconnect.config_flow.LinqConnectClient", autospec=True
    ) as mock_cls:
        mock_cls.return_value.resolve_identifier.return_value = district
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_BUILDINGS: [], CONF_SESSIONS: ["Lunch"]},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BUILDINGS: "no_schools"}


@freeze_time("2026-08-31 18:00:00")
async def test_options_flow_saves_rollover_time(
    hass, mock_config_entry, mock_api, load_fixture
):
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    district = parse_district(load_fixture("family_menu_identifier.json"))
    with patch(
        "custom_components.linqconnect.config_flow.LinqConnectClient", autospec=True
    ) as mock_cls:
        mock_cls.return_value.resolve_identifier.return_value = district
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_BUILDINGS: [BUILDING_1],
                CONF_SESSIONS: ["Lunch"],
                CONF_ROLLOVER_TIME: "11:30:00",
            },
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_ROLLOVER_TIME] == "11:30:00"


@freeze_time("2026-08-31 18:00:00")
async def test_options_flow_defaults_rollover_time(
    hass, mock_config_entry, mock_api, load_fixture
):
    # submitting without the field fills the 13:00 default
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    district = parse_district(load_fixture("family_menu_identifier.json"))
    with patch(
        "custom_components.linqconnect.config_flow.LinqConnectClient", autospec=True
    ) as mock_cls:
        mock_cls.return_value.resolve_identifier.return_value = district
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_BUILDINGS: [BUILDING_1], CONF_SESSIONS: ["Lunch"]},
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_ROLLOVER_TIME] == "13:00:00"
