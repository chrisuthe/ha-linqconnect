"""Tests for the config flow."""

from unittest.mock import patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.linqconnect.api import (
    DistrictNotFoundError,
    LinqConnectApiError,
    parse_district,
    parse_search_results,
)
from custom_components.linqconnect.const import (
    CONF_BUILDINGS,
    CONF_DISTRICT_ID,
    CONF_DISTRICT_NAME,
    CONF_IDENTIFIER,
    CONF_SESSIONS,
    CONF_SHARE_CODE,
    DOMAIN,
)

from .conftest import BUILDING_1, BUILDING_2, DISTRICT_ID


@pytest.fixture
def mock_flow_client(load_fixture):
    """Patch the client class used by the config flow."""
    district = parse_district(load_fixture("family_menu_identifier.json"))
    matches = parse_search_results(load_fixture("family_district_search.json"))
    with patch(
        "custom_components.linqconnect.config_flow.LinqConnectClient", autospec=True
    ) as mock_cls:
        client = mock_cls.return_value
        client.resolve_identifier.return_value = district
        client.search_districts.return_value = matches
        yield client


@pytest.fixture
def mock_setup():
    with patch(
        "custom_components.linqconnect.async_setup_entry", return_value=True
    ) as mock:
        yield mock


async def _start(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )


async def test_share_code_happy_path(hass, mock_flow_client, mock_setup):
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SHARE_CODE: "L36JZQ"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "schools"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BUILDINGS: [BUILDING_1, BUILDING_2], CONF_SESSIONS: ["Lunch"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Brandon Valley School District"
    assert result["data"] == {
        CONF_DISTRICT_ID: DISTRICT_ID,
        CONF_DISTRICT_NAME: "Brandon Valley School District",
        CONF_IDENTIFIER: "AZB89G",
    }
    assert result["options"] == {
        CONF_BUILDINGS: {
            BUILDING_1: "Inspiration Elementary",
            BUILDING_2: "Brandon Elementary",
        },
        CONF_SESSIONS: ["Lunch"],
    }
    assert result["result"].unique_id == DISTRICT_ID


async def test_name_search_happy_path(hass, mock_flow_client, mock_setup):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DISTRICT_NAME: "brandon valley"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_district"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DISTRICT_ID: DISTRICT_ID}
    )
    assert result["step_id"] == "schools"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_BUILDINGS: [BUILDING_1], CONF_SESSIONS: ["Breakfast", "Lunch"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_SESSIONS] == ["Breakfast", "Lunch"]


async def test_code_wins_when_both_fields_filled(hass, mock_flow_client, mock_setup):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SHARE_CODE: "L36JZQ", CONF_DISTRICT_NAME: "some other district"},
    )
    assert result["step_id"] == "schools"
    mock_flow_client.resolve_identifier.assert_awaited_once_with("L36JZQ")
    mock_flow_client.search_districts.assert_not_awaited()


async def test_bad_share_code_shows_error(hass, mock_flow_client):
    mock_flow_client.resolve_identifier.side_effect = DistrictNotFoundError("nope")
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SHARE_CODE: "XXXXXX"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SHARE_CODE: "district_not_found"}


async def test_api_down_shows_error(hass, mock_flow_client):
    mock_flow_client.resolve_identifier.side_effect = LinqConnectApiError("403")
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SHARE_CODE: "L36JZQ"}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_empty_search_shows_error(hass, mock_flow_client):
    mock_flow_client.search_districts.return_value = []
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DISTRICT_NAME: "zzzz"}
    )
    assert result["errors"] == {CONF_DISTRICT_NAME: "no_results"}


async def test_neither_field_shows_error(hass, mock_flow_client):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "missing_input"}


async def test_no_schools_selected_shows_error(hass, mock_flow_client, mock_setup):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SHARE_CODE: "L36JZQ"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_BUILDINGS: [], CONF_SESSIONS: ["Lunch"]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BUILDINGS: "no_schools"}


async def test_no_sessions_selected_shows_error(hass, mock_flow_client, mock_setup):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SHARE_CODE: "L36JZQ"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_BUILDINGS: [BUILDING_1], CONF_SESSIONS: []}
    )
    assert result["errors"] == {CONF_SESSIONS: "no_sessions"}


async def test_duplicate_district_aborts(
    hass, mock_flow_client, mock_config_entry
):
    mock_config_entry.add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SHARE_CODE: "L36JZQ"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
