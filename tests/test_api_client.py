"""Tests for LinqConnectClient HTTP behavior (mocked with aioresponses)."""

import re
from datetime import date

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.linqconnect.api import (
    DistrictNotFoundError,
    LinqConnectApiError,
    LinqConnectClient,
)
from custom_components.linqconnect.const import USER_AGENT

IDENTIFIER_URL = re.compile(r".*FamilyMenuIdentifier.*")
SEARCH_URL = re.compile(r".*FamilyDistrictSearch.*")
MENU_URL = re.compile(r".*FamilyMenu\?.*")


@pytest.fixture
async def session():
    session = aiohttp.ClientSession()
    yield session
    await session.close()


async def test_resolve_identifier_success(session, load_fixture):
    with aioresponses() as mocked:
        mocked.get(IDENTIFIER_URL, payload=load_fixture("family_menu_identifier.json"))
        district = await LinqConnectClient(session).resolve_identifier("AZB89G")
    assert district.name == "Brandon Valley School District"
    assert len(district.buildings) == 3


async def test_sends_browser_user_agent(session, load_fixture):
    with aioresponses() as mocked:
        mocked.get(IDENTIFIER_URL, payload=load_fixture("family_menu_identifier.json"))
        await LinqConnectClient(session).resolve_identifier("AZB89G")
        [request] = [
            call for calls in mocked.requests.values() for call in calls
        ]
    assert request.kwargs["headers"]["User-Agent"] == USER_AGENT


async def test_resolve_identifier_not_found(session):
    with aioresponses() as mocked:
        mocked.get(
            IDENTIFIER_URL,
            status=404,
            payload={"Messages": ["District not found."]},
        )
        with pytest.raises(DistrictNotFoundError):
            await LinqConnectClient(session).resolve_identifier("XXXXXX")


async def test_waf_403_raises_api_error(session):
    with aioresponses() as mocked:
        mocked.get(IDENTIFIER_URL, status=403, body="<html>Forbidden</html>")
        with pytest.raises(LinqConnectApiError, match="WAF"):
            await LinqConnectClient(session).resolve_identifier("AZB89G")


async def test_network_error_raises_api_error(session):
    with aioresponses() as mocked:
        mocked.get(IDENTIFIER_URL, exception=aiohttp.ClientConnectionError("boom"))
        with pytest.raises(LinqConnectApiError):
            await LinqConnectClient(session).resolve_identifier("AZB89G")


async def test_malformed_response_raises_api_error(session):
    with aioresponses() as mocked:
        mocked.get(IDENTIFIER_URL, payload={"unexpected": True})
        with pytest.raises(LinqConnectApiError):
            await LinqConnectClient(session).resolve_identifier("AZB89G")


async def test_search_districts(session, load_fixture):
    with aioresponses() as mocked:
        mocked.get(SEARCH_URL, payload=load_fixture("family_district_search.json"))
        results = await LinqConnectClient(session).search_districts("brandon valley")
    assert [d.name for d in results] == ["Brandon Valley School District"]


async def test_get_menus_formats_dates(session, load_fixture):
    with aioresponses() as mocked:
        mocked.get(MENU_URL, payload=load_fixture("family_menu.json"))
        days = await LinqConnectClient(session).get_menus(
            "district-guid", "building-guid", date(2026, 8, 31), date(2026, 10, 12)
        )
        [request_key] = list(mocked.requests)
    assert len(days) == 3
    query = str(request_key[1])
    assert "startDate=8-31-2026" in query
    assert "endDate=10-12-2026" in query
