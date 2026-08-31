# LINQ Connect Menus Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A HACS custom integration (domain `linqconnect`) exposing LINQ Connect school menus as one calendar entity per school plus per-session "today's menu" sensors.

**Architecture:** Inline HA-free API client (`api.py`) → one `DataUpdateCoordinator` per district config entry → calendar/sensor entities grouped into one device per school. Config flow identifies a district by share code or name search, then multi-selects schools and serving sessions.

**Tech Stack:** Python 3.13, Home Assistant custom integration APIs, aiohttp, pytest + pytest-homeassistant-custom-component + aioresponses, ruff.

**Spec:** `docs/superpowers/specs/2026-08-31-linqconnect-integration-design.md` — read it first; every behavior below is argued from it.

## Global Constraints

- Domain is exactly `linqconnect`; repo layout is `custom_components/linqconnect/`.
- Every API request MUST send header `User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36` — the WAF returns 403 to default client UAs.
- API base is `https://api.linqconnect.com/api`. Query dates are `M-D-YYYY` no zero padding (`8-31-2026`); response dates are `M/D/YYYY` (`8/31/2026`). All dates are naive `datetime.date` — no timezones.
- All-day calendar events use exclusive end: `start=date`, `end=date + 1 day`.
- Coordinator polls every 6 hours over a window of Monday-of-current-week → +42 days.
- Commit messages: plain imperative, NO AI attribution, NO Co-Authored-By lines.
- Dev commands below assume Git Bash from repo root `C:\CodeProjects\ha-linqconnect` with the venv at `.venv` (created in Task 1). Run tests as `./.venv/Scripts/python -m pytest`.

---

### Task 1: Dev environment + integration skeleton

**Files:**
- Create: `.gitignore`, `requirements-dev.txt`, `pyproject.toml`
- Create: `custom_components/linqconnect/__init__.py` (empty for now), `custom_components/linqconnect/const.py`, `custom_components/linqconnect/manifest.json`
- Create: `tests/__init__.py` (empty — makes `tests` a package so test modules can `from .conftest import ...`), `tests/conftest.py`, `tests/fixtures/` (dir)
- Test: `tests/test_manifest.py`

**Interfaces:**
- Produces: `const.py` names used by every later task: `DOMAIN`, `API_BASE`, `USER_AGENT`, `CONF_SHARE_CODE`, `CONF_DISTRICT_NAME`, `CONF_DISTRICT_ID`, `CONF_IDENTIFIER`, `CONF_BUILDINGS`, `CONF_SESSIONS`, `DEFAULT_SESSIONS`, `SESSION_CHOICES`, `UPDATE_INTERVAL`, `FETCH_WINDOW_DAYS`, `MANUFACTURER`, `MODEL`.
- Produces: pytest environment with `hass` fixture available and custom integrations enabled.

- [ ] **Step 1: Create venv and install dev deps**

Create the files first so install has context:

`requirements-dev.txt`:
```
pytest-homeassistant-custom-component
aioresponses
ruff
```

`.gitignore`:
```
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
*.pyc
```

`pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py313"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "W"]
```

Then:
```bash
uv venv .venv --python 3.13
uv pip install --python .venv/Scripts/python -r requirements-dev.txt
```
If `uv` is unavailable: `py -3.13 -m venv .venv && ./.venv/Scripts/python -m pip install -r requirements-dev.txt`. (`pytest-homeassistant-custom-component` pulls in a matching `homeassistant`, `pytest`, and `freezegun`.) If a dependency fails to build on Windows, stop and report — do not swap in different package versions silently.

- [ ] **Step 2: Write the integration skeleton**

`custom_components/linqconnect/const.py`:
```python
"""Constants for the LINQ Connect Menus integration."""

from datetime import timedelta

DOMAIN = "linqconnect"

API_BASE = "https://api.linqconnect.com/api"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

CONF_SHARE_CODE = "share_code"
CONF_DISTRICT_NAME = "district_name"
CONF_DISTRICT_ID = "district_id"
CONF_IDENTIFIER = "identifier"
CONF_BUILDINGS = "buildings"
CONF_SESSIONS = "sessions"

DEFAULT_SESSIONS = ["Lunch"]
SESSION_CHOICES = ["Breakfast", "Lunch", "Snack", "Dinner"]

UPDATE_INTERVAL = timedelta(hours=6)
FETCH_WINDOW_DAYS = 42

MANUFACTURER = "LINQ"
MODEL = "School menu"
```

`custom_components/linqconnect/manifest.json`:
```json
{
  "domain": "linqconnect",
  "name": "LINQ Connect Menus",
  "codeowners": ["@chrisuthe"],
  "config_flow": true,
  "documentation": "https://github.com/chrisuthe/ha-linqconnect",
  "integration_type": "hub",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/chrisuthe/ha-linqconnect/issues",
  "requirements": [],
  "version": "0.1.0"
}
```

`custom_components/linqconnect/__init__.py`:
```python
"""The LINQ Connect Menus integration."""
```

`tests/conftest.py`:
```python
"""Shared test fixtures."""

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow tests to load custom_components/linqconnect."""
    yield


@pytest.fixture
def load_fixture():
    """Return a loader for JSON fixture files."""

    def _load(name: str) -> dict:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    return _load
```

- [ ] **Step 3: Write the smoke test**

`tests/test_manifest.py`:
```python
"""Smoke tests: package imports and manifest is sane."""

import json
from pathlib import Path

from custom_components.linqconnect.const import DOMAIN

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_matches_domain():
    manifest = json.loads(
        (ROOT / "custom_components" / "linqconnect" / "manifest.json").read_text()
    )
    assert manifest["domain"] == DOMAIN
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "cloud_polling"
    assert manifest["requirements"] == []
```

- [ ] **Step 4: Run tests, verify pass**

Run: `./.venv/Scripts/python -m pytest tests/ -v`
Expected: 1 passed (and no collection errors — proves the HA test plugin loads).

- [ ] **Step 5: Commit**

```bash
git add .gitignore requirements-dev.txt pyproject.toml custom_components tests
git commit -m "Add integration skeleton and dev environment"
```

---

### Task 2: API models, parsing, and fixtures

**Files:**
- Create: `custom_components/linqconnect/api.py`
- Create: `tests/fixtures/family_menu_identifier.json`, `tests/fixtures/family_menu.json`, `tests/fixtures/family_district_search.json`
- Test: `tests/test_api_parsing.py`

**Interfaces:**
- Consumes: `const.py` (nothing else).
- Produces (used by every later task):
  - `@dataclass Building(building_id: str, name: str)`
  - `@dataclass District(district_id: str, name: str, identifier: str, buildings: list[Building] = [], city: str | None = None, state: str | None = None)`
  - `@dataclass MenuCategory(name: str, items: list[str])`
  - `@dataclass DayMenu(date: datetime.date, session: str, meal_name: str | None, categories: list[MenuCategory])`
  - `parse_api_date(value: str) -> date`, `format_api_date(value: date) -> str`
  - `parse_district(data: dict) -> District`, `parse_search_results(data: dict) -> list[District]`, `parse_menus(data: dict) -> list[DayMenu]`
  - Exceptions: `LinqConnectApiError(Exception)`, `DistrictNotFoundError(LinqConnectApiError)`

- [ ] **Step 1: Create the fixtures** (shapes verified against the live API 2026-08-31; see spec)

`tests/fixtures/family_menu_identifier.json`:
```json
{
  "DistrictId": "b1d7358a-818b-ec11-90c7-d2d97b40e955",
  "DistrictName": "Brandon Valley School District",
  "Buildings": [
    {"BuildingId": "0c65b2bc-908d-ec11-8df7-9566c4096294", "Name": "Inspiration Elementary"},
    {"BuildingId": "041717d0-8f8d-ec11-8df7-eb7b319a32d1", "Name": "Brandon Elementary"},
    {"BuildingId": "2e94e37a-8f8d-ec11-8df7-eb7b319a32d1", "Name": "Brandon Valley Middle School"}
  ],
  "SelectedBuildingId": "0c65b2bc-908d-ec11-8df7-9566c4096294",
  "MenuNotification": "** Menu Is Subject To Change **",
  "Identifier": "AZB89G"
}
```

`tests/fixtures/family_district_search.json`:
```json
{
  "Data": [
    {
      "DistrictId": "b1d7358a-818b-ec11-90c7-d2d97b40e955",
      "Identifier": "AZB89G",
      "Name": "Brandon Valley School District",
      "City": "Brandon",
      "State": "South Dakota",
      "IsActive": true
    },
    {
      "DistrictId": "00000000-0000-0000-0000-000000000001",
      "Identifier": "ZZZZZZ",
      "Name": "Brandon Closed District",
      "City": "Nowhere",
      "State": "South Dakota",
      "IsActive": false
    }
  ],
  "CurrentPage": 0,
  "PageSize": 20,
  "TotalPages": 1,
  "TotalRecords": 2
}
```

`tests/fixtures/family_menu.json` — exercises: two sessions; two `MenuMeals` on the same day (merge + dedupe "Bagel Bag"); a day with empty `MenuMeals` (no-school day → absent from output):
```json
{
  "FamilyMenuSessions": [
    {
      "ServingSession": "Breakfast",
      "MenuPlans": [
        {
          "MenuPlanName": "All Schools Breakfast 26/27",
          "Days": [
            {
              "Date": "8/31/2026",
              "MenuMeals": [
                {
                  "MenuMealName": "Week 2 Monday",
                  "RecipeCategories": [
                    {
                      "CategoryName": "Main Entrée",
                      "Recipes": [
                        {"RecipeName": "French Toast Sticks"},
                        {"RecipeName": "Cereal Variety"}
                      ]
                    },
                    {"CategoryName": "Fruit", "Recipes": [{"RecipeName": "Banana"}]}
                  ]
                }
              ]
            }
          ]
        }
      ]
    },
    {
      "ServingSession": "Lunch",
      "MenuPlans": [
        {
          "MenuPlanName": "Elementary Lunch 26/27",
          "Days": [
            {
              "Date": "8/31/2026",
              "MenuMeals": [
                {
                  "MenuMealName": "Week 2 Monday",
                  "RecipeCategories": [
                    {
                      "CategoryName": "Main Entrée",
                      "Recipes": [
                        {"RecipeName": "Italian Dunkers"},
                        {"RecipeName": "Bagel Bag"}
                      ]
                    },
                    {
                      "CategoryName": "Vegetable",
                      "Recipes": [
                        {"RecipeName": "Green Beans"},
                        {"RecipeName": "Baby Carrots"}
                      ]
                    },
                    {"CategoryName": "Fruit", "Recipes": [{"RecipeName": "Sliced Peaches"}]},
                    {
                      "CategoryName": "Milk",
                      "Recipes": [
                        {"RecipeName": "1% Milk"},
                        {"RecipeName": "Chocolate Milk"}
                      ]
                    }
                  ]
                },
                {
                  "MenuMealName": "Garden Bar",
                  "RecipeCategories": [
                    {
                      "CategoryName": "Main Entrée",
                      "Recipes": [
                        {"RecipeName": "Garden Bar"},
                        {"RecipeName": "Bagel Bag"}
                      ]
                    },
                    {"CategoryName": "Condiments", "Recipes": [{"RecipeName": "Ranch Dressing"}]}
                  ]
                }
              ]
            },
            {
              "Date": "9/1/2026",
              "MenuMeals": [
                {
                  "MenuMealName": "Week 2 Tuesday",
                  "RecipeCategories": [
                    {
                      "CategoryName": "Main Entrée",
                      "Recipes": [{"RecipeName": "Crispy Chicken Sandwich"}]
                    },
                    {"CategoryName": "Vegetable", "Recipes": [{"RecipeName": "Corn"}]}
                  ]
                }
              ]
            },
            {"Date": "9/2/2026", "MenuMeals": []}
          ]
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Write the failing tests**

`tests/test_api_parsing.py`:
```python
"""Tests for api.py pure parsing functions."""

from datetime import date

from custom_components.linqconnect.api import (
    format_api_date,
    parse_api_date,
    parse_district,
    parse_menus,
    parse_search_results,
)


def test_parse_api_date():
    assert parse_api_date("8/31/2026") == date(2026, 8, 31)
    assert parse_api_date("12/1/2026") == date(2026, 12, 1)


def test_format_api_date_no_zero_padding():
    assert format_api_date(date(2026, 8, 31)) == "8-31-2026"
    assert format_api_date(date(2026, 12, 1)) == "12-1-2026"


def test_parse_district(load_fixture):
    district = parse_district(load_fixture("family_menu_identifier.json"))
    assert district.district_id == "b1d7358a-818b-ec11-90c7-d2d97b40e955"
    assert district.name == "Brandon Valley School District"
    assert district.identifier == "AZB89G"
    assert len(district.buildings) == 3
    assert district.buildings[0].name == "Inspiration Elementary"
    assert district.buildings[0].building_id == "0c65b2bc-908d-ec11-8df7-9566c4096294"


def test_parse_search_results_filters_inactive(load_fixture):
    results = parse_search_results(load_fixture("family_district_search.json"))
    assert len(results) == 1
    assert results[0].name == "Brandon Valley School District"
    assert results[0].city == "Brandon"
    assert results[0].state == "South Dakota"
    assert results[0].buildings == []


def test_parse_menus_merges_and_dedupes(load_fixture):
    days = parse_menus(load_fixture("family_menu.json"))
    # breakfast 8/31, lunch 8/31, lunch 9/1 — the empty 9/2 day is absent
    assert [(d.date, d.session) for d in days] == [
        (date(2026, 8, 31), "Breakfast"),
        (date(2026, 8, 31), "Lunch"),
        (date(2026, 9, 1), "Lunch"),
    ]
    lunch = days[1]
    assert lunch.meal_name == "Week 2 Monday"  # first MenuMealName wins
    assert [c.name for c in lunch.categories] == [
        "Main Entrée",
        "Vegetable",
        "Fruit",
        "Milk",
        "Condiments",
    ]
    # second MenuMeal merged into the same category, "Bagel Bag" deduped
    assert lunch.categories[0].items == ["Italian Dunkers", "Bagel Bag", "Garden Bar"]


def test_parse_menus_empty_response():
    assert parse_menus({"FamilyMenuSessions": []}) == []
    assert parse_menus({}) == []
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `./.venv/Scripts/python -m pytest tests/test_api_parsing.py -v`
Expected: FAIL — `ModuleNotFoundError` / `ImportError` (api.py doesn't exist).

- [ ] **Step 4: Implement `api.py` (models + parsing only — the HTTP client class comes in Task 3)**

`custom_components/linqconnect/api.py`:
```python
"""HA-free client for the LINQ Connect public menu API.

Kept free of Home Assistant imports so it could be extracted to a
standalone library later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import aiohttp

from .const import API_BASE, USER_AGENT


class LinqConnectApiError(Exception):
    """The API could not be reached or returned an error."""


class DistrictNotFoundError(LinqConnectApiError):
    """A share code did not resolve to a district."""


@dataclass
class Building:
    building_id: str
    name: str


@dataclass
class District:
    district_id: str
    name: str
    identifier: str
    buildings: list[Building] = field(default_factory=list)
    city: str | None = None
    state: str | None = None


@dataclass
class MenuCategory:
    name: str
    items: list[str]


@dataclass
class DayMenu:
    date: date
    session: str
    meal_name: str | None
    categories: list[MenuCategory]


def parse_api_date(value: str) -> date:
    """Parse an API response date like '8/31/2026'."""
    month, day, year = (int(part) for part in value.split("/"))
    return date(year, month, day)


def format_api_date(value: date) -> str:
    """Format a query-param date: M-D-YYYY, no zero padding."""
    return f"{value.month}-{value.day}-{value.year}"


def parse_district(data: dict) -> District:
    """Parse a FamilyMenuIdentifier response."""
    return District(
        district_id=data["DistrictId"],
        name=data["DistrictName"],
        identifier=data["Identifier"],
        buildings=[
            Building(building_id=b["BuildingId"], name=b["Name"])
            for b in data.get("Buildings", [])
        ],
    )


def parse_search_results(data: dict) -> list[District]:
    """Parse a FamilyDistrictSearch response, dropping inactive districts."""
    return [
        District(
            district_id=d["DistrictId"],
            name=d["Name"],
            identifier=d["Identifier"],
            city=d.get("City"),
            state=d.get("State"),
        )
        for d in data.get("Data", [])
        if d.get("IsActive", True)
    ]


def parse_menus(data: dict) -> list[DayMenu]:
    """Flatten a FamilyMenu response into one DayMenu per (date, session).

    Multiple MenuPlans/MenuMeals contributing to the same date+session are
    merged: same-named categories combine, item names dedupe, the first
    MenuMealName seen wins.
    """
    merged: dict[tuple[date, str], DayMenu] = {}
    for session_data in data.get("FamilyMenuSessions", []):
        session = session_data.get("ServingSession", "")
        for plan in session_data.get("MenuPlans", []):
            for day_data in plan.get("Days", []):
                day_date = parse_api_date(day_data["Date"])
                for meal in day_data.get("MenuMeals", []):
                    key = (day_date, session)
                    day = merged.get(key)
                    if day is None:
                        day = DayMenu(
                            date=day_date,
                            session=session,
                            meal_name=meal.get("MenuMealName"),
                            categories=[],
                        )
                        merged[key] = day
                    for cat_data in meal.get("RecipeCategories", []):
                        cat_name = cat_data.get("CategoryName", "")
                        category = next(
                            (c for c in day.categories if c.name == cat_name), None
                        )
                        if category is None:
                            category = MenuCategory(name=cat_name, items=[])
                            day.categories.append(category)
                        for recipe in cat_data.get("Recipes", []):
                            name = recipe.get("RecipeName")
                            if name and name not in category.items:
                                category.items.append(name)
    return sorted(merged.values(), key=lambda d: (d.date, d.session))
```

- [ ] **Step 5: Run tests, verify pass**

Run: `./.venv/Scripts/python -m pytest tests/test_api_parsing.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add custom_components/linqconnect/api.py tests/fixtures tests/test_api_parsing.py
git commit -m "Add API models, parsing, and captured fixtures"
```

---

### Task 3: API HTTP client

**Files:**
- Modify: `custom_components/linqconnect/api.py` (append the client class)
- Test: `tests/test_api_client.py`

**Interfaces:**
- Consumes: Task 2's parse functions and exceptions.
- Produces:
  - `class LinqConnectClient:`
    - `__init__(self, session: aiohttp.ClientSession) -> None`
    - `async resolve_identifier(self, code: str) -> District`
    - `async search_districts(self, name: str) -> list[District]`
    - `async get_menus(self, district_id: str, building_id: str, start: date, end: date) -> list[DayMenu]`
  - Raises `DistrictNotFoundError` on HTTP 404, `LinqConnectApiError` on 403/5xx/network errors.

- [ ] **Step 1: Write the failing tests**

`tests/test_api_client.py`:
```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `./.venv/Scripts/python -m pytest tests/test_api_client.py -v`
Expected: FAIL — `ImportError: cannot import name 'LinqConnectClient'`.

- [ ] **Step 3: Append the client class to `api.py`**

```python
class LinqConnectClient:
    """Thin async client; the caller owns the aiohttp session."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _get(self, path: str, params: dict) -> dict:
        try:
            async with self._session.get(
                f"{API_BASE}/{path}",
                params=params,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 404:
                    raise DistrictNotFoundError(f"{path}: not found")
                if resp.status == 403:
                    raise LinqConnectApiError(
                        "Blocked by LINQ Connect WAF (HTTP 403); "
                        "the User-Agent header may need updating"
                    )
                resp.raise_for_status()
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LinqConnectApiError(f"Error calling {path}: {err}") from err

    async def resolve_identifier(self, code: str) -> District:
        """Resolve a share code (e.g. 'AZB89G') to a District with buildings."""
        data = await self._get("FamilyMenuIdentifier", {"identifier": code})
        return parse_district(data)

    async def search_districts(self, name: str) -> list[District]:
        """Search districts by name; results have no buildings populated."""
        data = await self._get(
            "FamilyDistrictSearch",
            {"currentPage": 0, "pageSize": 20, "searchText": name},
        )
        return parse_search_results(data)

    async def get_menus(
        self, district_id: str, building_id: str, start: date, end: date
    ) -> list[DayMenu]:
        """Fetch parsed menus for one building over [start, end]."""
        data = await self._get(
            "FamilyMenu",
            {
                "districtId": district_id,
                "buildingId": building_id,
                "startDate": format_api_date(start),
                "endDate": format_api_date(end),
            },
        )
        return parse_menus(data)
```

- [ ] **Step 4: Run tests, verify pass**

Run: `./.venv/Scripts/python -m pytest tests/test_api_client.py tests/test_api_parsing.py -v`
Expected: all pass. If the `test_sends_browser_user_agent` unpacking fails, inspect `mocked.requests` structure (dict of (method, URL) → list of calls) and fix the test's extraction, not the client.

- [ ] **Step 5: Commit**

```bash
git add custom_components/linqconnect/api.py tests/test_api_client.py
git commit -m "Add LINQ Connect HTTP client"
```

---

### Task 4: Presentation helpers (`menu_format.py`)

**Files:**
- Create: `custom_components/linqconnect/menu_format.py`
- Test: `tests/test_menu_format.py`

**Interfaces:**
- Consumes: `DayMenu`, `MenuCategory` from `api.py`.
- Produces (used by calendar.py and sensor.py):
  - `entree_items(day: DayMenu) -> list[str]`
  - `summary(day: DayMenu) -> str`
  - `description(day: DayMenu) -> str`
  - `menu_dict(day: DayMenu) -> dict[str, list[str]]`

- [ ] **Step 1: Write the failing tests**

`tests/test_menu_format.py`:
```python
"""Tests for pure presentation helpers."""

from datetime import date

from custom_components.linqconnect.api import DayMenu, MenuCategory
from custom_components.linqconnect.menu_format import (
    description,
    entree_items,
    menu_dict,
    summary,
)


def _day(categories, meal_name="Week 2 Monday"):
    return DayMenu(
        date=date(2026, 8, 31),
        session="Lunch",
        meal_name=meal_name,
        categories=categories,
    )


ENTREE = MenuCategory(name="Main Entrée", items=["Italian Dunkers", "Bagel Bag"])
VEG = MenuCategory(name="Vegetable", items=["Green Beans"])


def test_entree_items_matches_accented_category():
    assert entree_items(_day([VEG, ENTREE])) == ["Italian Dunkers", "Bagel Bag"]


def test_entree_items_matches_unaccented_category():
    plain = MenuCategory(name="MAIN ENTREE", items=["Pizza"])
    assert entree_items(_day([VEG, plain])) == ["Pizza"]


def test_entree_items_falls_back_to_first_category():
    assert entree_items(_day([VEG])) == ["Green Beans"]


def test_entree_items_empty_day():
    assert entree_items(_day([])) == []


def test_summary_joins_with_slashes():
    assert summary(_day([ENTREE, VEG])) == "Italian Dunkers / Bagel Bag"


def test_description_includes_meal_name_and_categories():
    assert description(_day([ENTREE, VEG])) == (
        "Week 2 Monday\n"
        "Main Entrée: Italian Dunkers, Bagel Bag\n"
        "Vegetable: Green Beans"
    )


def test_description_without_meal_name():
    assert description(_day([VEG], meal_name=None)) == "Vegetable: Green Beans"


def test_menu_dict():
    assert menu_dict(_day([ENTREE, VEG])) == {
        "Main Entrée": ["Italian Dunkers", "Bagel Bag"],
        "Vegetable": ["Green Beans"],
    }
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `./.venv/Scripts/python -m pytest tests/test_menu_format.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`custom_components/linqconnect/menu_format.py`:
```python
"""Pure presentation helpers shared by the calendar and sensor entities."""

from __future__ import annotations

import unicodedata

from .api import DayMenu


def _normalize(text: str) -> str:
    """Lowercase and strip accents so 'Entrée' matches 'entree'."""
    return (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    )


def entree_items(day: DayMenu) -> list[str]:
    """Items of the first entrée-named category, else the first category."""
    if not day.categories:
        return []
    for category in day.categories:
        if "entree" in _normalize(category.name):
            return category.items
    return day.categories[0].items


def summary(day: DayMenu) -> str:
    """One-line menu summary: entrée items joined with slashes."""
    return " / ".join(entree_items(day))


def description(day: DayMenu) -> str:
    """Full menu text: optional meal name line, then one line per category."""
    lines = []
    if day.meal_name:
        lines.append(day.meal_name)
    lines.extend(
        f"{category.name}: {', '.join(category.items)}" for category in day.categories
    )
    return "\n".join(lines)


def menu_dict(day: DayMenu) -> dict[str, list[str]]:
    """Category name → item list, for sensor attributes."""
    return {category.name: list(category.items) for category in day.categories}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `./.venv/Scripts/python -m pytest tests/test_menu_format.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add custom_components/linqconnect/menu_format.py tests/test_menu_format.py
git commit -m "Add menu presentation helpers"
```

---

### Task 5: Coordinator

**Files:**
- Create: `custom_components/linqconnect/coordinator.py`
- Test: `tests/test_coordinator.py`

**Interfaces:**
- Consumes: `LinqConnectClient`, `DayMenu`, `LinqConnectApiError` from `api.py`; `CONF_DISTRICT_ID`, `CONF_BUILDINGS`, `UPDATE_INTERVAL`, `FETCH_WINDOW_DAYS`, `DOMAIN` from `const.py`.
- Produces:
  - `fetch_window(today: date) -> tuple[date, date]` — Monday of current week → +42 days.
  - `class LinqConnectCoordinator(DataUpdateCoordinator[dict[str, list[DayMenu]]])` with `__init__(self, hass, entry, client)` and attribute `client`. `coordinator.data` maps building_id → `list[DayMenu]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_coordinator.py`:
```python
"""Tests for the data update coordinator."""

from datetime import date
from unittest.mock import AsyncMock

import pytest
from freezegun import freeze_time
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.linqconnect.api import LinqConnectApiError, parse_menus
from custom_components.linqconnect.const import (
    CONF_BUILDINGS,
    CONF_DISTRICT_ID,
    CONF_DISTRICT_NAME,
    CONF_IDENTIFIER,
    CONF_SESSIONS,
    DOMAIN,
)
from custom_components.linqconnect.coordinator import (
    LinqConnectCoordinator,
    fetch_window,
)

DISTRICT_ID = "b1d7358a-818b-ec11-90c7-d2d97b40e955"
BUILDING_1 = "0c65b2bc-908d-ec11-8df7-9566c4096294"


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Brandon Valley School District",
        unique_id=DISTRICT_ID,
        data={
            CONF_DISTRICT_ID: DISTRICT_ID,
            CONF_DISTRICT_NAME: "Brandon Valley School District",
            CONF_IDENTIFIER: "AZB89G",
        },
        options={
            CONF_BUILDINGS: {BUILDING_1: "Inspiration Elementary"},
            CONF_SESSIONS: ["Lunch"],
        },
    )


def test_fetch_window_on_a_monday():
    assert fetch_window(date(2026, 8, 31)) == (date(2026, 8, 31), date(2026, 10, 12))


def test_fetch_window_mid_week_snaps_to_monday():
    assert fetch_window(date(2026, 9, 3)) == (date(2026, 8, 31), date(2026, 10, 12))


@freeze_time("2026-08-31 12:00:00")
async def test_update_fetches_each_building(hass, load_fixture):
    entry = _entry()
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.get_menus.return_value = parse_menus(load_fixture("family_menu.json"))
    coordinator = LinqConnectCoordinator(hass, entry, client)

    data = await coordinator._async_update_data()

    assert set(data) == {BUILDING_1}
    assert len(data[BUILDING_1]) == 3
    client.get_menus.assert_awaited_once_with(
        DISTRICT_ID, BUILDING_1, date(2026, 8, 31), date(2026, 10, 12)
    )


async def test_api_error_becomes_update_failed(hass):
    entry = _entry()
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.get_menus.side_effect = LinqConnectApiError("WAF blocked")
    coordinator = LinqConnectCoordinator(hass, entry, client)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `./.venv/Scripts/python -m pytest tests/test_coordinator.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`custom_components/linqconnect/coordinator.py`:
```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `./.venv/Scripts/python -m pytest tests/test_coordinator.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add custom_components/linqconnect/coordinator.py tests/test_coordinator.py
git commit -m "Add district data update coordinator"
```

---

### Task 6: Entry setup, unload, and device removal (`__init__.py`)

**Files:**
- Modify: `custom_components/linqconnect/__init__.py` (replace the docstring-only file)
- Modify: `tests/conftest.py` (add shared `mock_config_entry` + `mock_api` fixtures)
- Test: `tests/test_init.py`

**Interfaces:**
- Consumes: `LinqConnectCoordinator`, `LinqConnectClient`.
- Produces (used by platform tasks and their tests):
  - `type LinqConnectConfigEntry = ConfigEntry[LinqConnectCoordinator]` — `entry.runtime_data` is the coordinator.
  - `async_setup_entry`, `async_unload_entry`, `async_remove_config_entry_device`.
  - `PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]`.
  - conftest fixtures: `mock_config_entry` (Brandon Valley, one building "Inspiration Elementary", sessions `["Lunch"]`) and `mock_api` (patches `custom_components.linqconnect.LinqConnectClient`, returns fixture-parsed data; yields the mock client instance). Also conftest constants `DISTRICT_ID`, `BUILDING_1`, `BUILDING_2`.

- [ ] **Step 1: Add shared fixtures to `tests/conftest.py`** (append; keep existing content)

```python
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.linqconnect.api import parse_district, parse_menus
from custom_components.linqconnect.const import (
    CONF_BUILDINGS,
    CONF_DISTRICT_ID,
    CONF_DISTRICT_NAME,
    CONF_IDENTIFIER,
    CONF_SESSIONS,
    DOMAIN,
)

DISTRICT_ID = "b1d7358a-818b-ec11-90c7-d2d97b40e955"
BUILDING_1 = "0c65b2bc-908d-ec11-8df7-9566c4096294"
BUILDING_2 = "041717d0-8f8d-ec11-8df7-eb7b319a32d1"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A configured Brandon Valley entry with one school, Lunch only."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Brandon Valley School District",
        unique_id=DISTRICT_ID,
        data={
            CONF_DISTRICT_ID: DISTRICT_ID,
            CONF_DISTRICT_NAME: "Brandon Valley School District",
            CONF_IDENTIFIER: "AZB89G",
        },
        options={
            CONF_BUILDINGS: {BUILDING_1: "Inspiration Elementary"},
            CONF_SESSIONS: ["Lunch"],
        },
    )


@pytest.fixture
def mock_api(load_fixture):
    """Patch the client class used by async_setup_entry; yield its instance."""
    district = parse_district(load_fixture("family_menu_identifier.json"))
    menus = parse_menus(load_fixture("family_menu.json"))
    with patch(
        "custom_components.linqconnect.LinqConnectClient", autospec=True
    ) as mock_cls:
        client = mock_cls.return_value
        client.resolve_identifier.return_value = district
        client.get_menus.return_value = menus
        yield client
```

- [ ] **Step 2: Write the failing tests**

`tests/test_init.py`:
```python
"""Tests for entry setup, unload, and device removal."""

from freezegun import freeze_time
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr

from custom_components.linqconnect import async_remove_config_entry_device
from custom_components.linqconnect.api import LinqConnectApiError
from custom_components.linqconnect.const import DOMAIN

from .conftest import BUILDING_1


@freeze_time("2026-08-31 12:00:00")
async def test_setup_and_unload(hass, mock_config_entry, mock_api):
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("calendar.inspiration_elementary") is not None
    assert hass.states.get("sensor.inspiration_elementary_lunch") is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_api_error_at_setup_retries(hass, mock_config_entry, mock_api):
    mock_api.get_menus.side_effect = LinqConnectApiError("down")
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@freeze_time("2026-08-31 12:00:00")
async def test_remove_device_only_for_unselected_buildings(
    hass, mock_config_entry, mock_api
):
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registry = dr.async_get(hass)
    current = registry.async_get_device(identifiers={(DOMAIN, BUILDING_1)})
    assert current is not None
    assert (
        await async_remove_config_entry_device(hass, mock_config_entry, current)
        is False
    )

    stale = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "stale-building-id")},
    )
    assert (
        await async_remove_config_entry_device(hass, mock_config_entry, stale) is True
    )
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `./.venv/Scripts/python -m pytest tests/test_init.py -v`
Expected: FAIL — `ImportError` (no `async_remove_config_entry_device`), then setup failures (no `async_setup_entry`). Note: the first test also needs calendar.py/sensor.py (Tasks 8–9). To keep this task independently verifiable, create **placeholder platform modules** now — minimal but real:

`custom_components/linqconnect/calendar.py` (placeholder, replaced in Task 8):
```python
"""Calendar platform (placeholder until entities land)."""


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up no entities yet."""
```

`custom_components/linqconnect/sensor.py` (placeholder, replaced in Task 9): same shape, docstring "Sensor platform (placeholder until entities land)."

With placeholders, `test_setup_and_unload` still fails on the missing entity states — that is expected and stays red until Tasks 8–9. Mark it so: add `import pytest` to the test file's imports and put `@pytest.mark.xfail(reason="entities land in tasks 8-9", strict=True)` above `test_setup_and_unload`, **removing both again in Task 9, step 4.** The other two tests must pass in this task.

- [ ] **Step 4: Implement `__init__.py`**

```python
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
```

- [ ] **Step 5: Run tests, verify pass (with the one xfail)**

Run: `./.venv/Scripts/python -m pytest tests/test_init.py -v`
Expected: 2 passed, 1 xfailed.

- [ ] **Step 6: Commit**

```bash
git add custom_components/linqconnect tests/conftest.py tests/test_init.py
git commit -m "Add config entry setup, unload, and device removal"
```

---

### Task 7: Config flow + translations

**Files:**
- Create: `custom_components/linqconnect/config_flow.py`
- Create: `custom_components/linqconnect/strings.json`, `custom_components/linqconnect/translations/en.json`
- Test: `tests/test_config_flow.py`

**Interfaces:**
- Consumes: `LinqConnectClient` (patched in tests at `custom_components.linqconnect.config_flow.LinqConnectClient`), `District`/`Building` dataclasses, const keys.
- Produces: `LinqConnectConfigFlow` — steps `user` → (`pick_district`) → `schools`. Entry `data={district_id, district_name, identifier}`, `options={buildings: {id: name}, sessions: [str]}`, `unique_id=district_id`, `title=district name`. (Options flow is Task 10.)

- [ ] **Step 1: Write the failing tests**

`tests/test_config_flow.py`:
```python
"""Tests for the config flow."""

from unittest.mock import AsyncMock, patch

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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `./.venv/Scripts/python -m pytest tests/test_config_flow.py -v`
Expected: FAIL — flow handler not registered / module missing.

- [ ] **Step 3: Implement `config_flow.py`**

```python
"""Config flow for LINQ Connect Menus."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    CONF_SESSIONS,
    CONF_SHARE_CODE,
    DEFAULT_SESSIONS,
    DOMAIN,
    SESSION_CHOICES,
)

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
                except LinqConnectApiError:
                    errors["base"] = "cannot_connect"
                else:
                    return await self._async_district_resolved()
            elif name:
                try:
                    self._matches = await self._client().search_districts(name)
                except LinqConnectApiError:
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
            except LinqConnectApiError:
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
```

`custom_components/linqconnect/strings.json` (and an identical copy at `translations/en.json`):
```json
{
  "config": {
    "step": {
      "user": {
        "title": "Find your district",
        "description": "Enter the share code from your district's public menu link (linqconnect.com/public/menu/CODE), or search by district name.",
        "data": {
          "share_code": "Share code",
          "district_name": "District name"
        }
      },
      "pick_district": {
        "title": "Select district",
        "data": {
          "district_id": "District"
        }
      },
      "schools": {
        "title": "Choose schools and meals",
        "data": {
          "buildings": "Schools",
          "sessions": "Serving sessions"
        }
      }
    },
    "error": {
      "district_not_found": "No district found for that share code.",
      "no_results": "No districts matched that name.",
      "cannot_connect": "Could not reach LINQ Connect.",
      "missing_input": "Enter a share code or a district name.",
      "no_schools": "Select at least one school.",
      "no_sessions": "Select at least one serving session."
    },
    "abort": {
      "already_configured": "This district is already configured."
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Schools and meals",
        "data": {
          "buildings": "Schools",
          "sessions": "Serving sessions"
        }
      }
    },
    "error": {
      "no_schools": "Select at least one school.",
      "no_sessions": "Select at least one serving session."
    },
    "abort": {
      "cannot_connect": "Could not reach LINQ Connect."
    }
  }
}
```

- [ ] **Step 4: Run tests, verify pass**

Run: `./.venv/Scripts/python -m pytest tests/test_config_flow.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add custom_components/linqconnect/config_flow.py custom_components/linqconnect/strings.json custom_components/linqconnect/translations tests/test_config_flow.py
git commit -m "Add config flow with share-code and name-search paths"
```

---

### Task 8: Calendar platform

**Files:**
- Modify: `custom_components/linqconnect/calendar.py` (replace the Task 6 placeholder)
- Test: `tests/test_calendar.py`

**Interfaces:**
- Consumes: `entry.runtime_data` (coordinator), `entry.options[CONF_BUILDINGS/CONF_SESSIONS]`, `menu_format.summary/description`, `DayMenu`.
- Produces: `LinqConnectCalendar(CoordinatorEntity, CalendarEntity)` — `unique_id = building_id`, entity named after its school device, all-day events with exclusive end.

- [ ] **Step 1: Write the failing tests**

`tests/test_calendar.py`:
```python
"""Tests for the calendar platform."""

from freezegun import freeze_time

from custom_components.linqconnect.const import CONF_SESSIONS

CAL = "calendar.inspiration_elementary"


async def _setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _get_events(hass, start, end):
    result = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": CAL,
            "start_date_time": start,
            "end_date_time": end,
        },
        blocking=True,
        return_response=True,
    )
    return result[CAL]["events"]


@freeze_time("2026-08-31 18:00:00")
async def test_all_day_lunch_events(hass, mock_config_entry, mock_api):
    await _setup(hass, mock_config_entry)

    state = hass.states.get(CAL)
    assert state is not None
    # today's lunch is the current event
    assert state.state == "on"
    assert state.attributes["all_day"] is True
    assert state.attributes["message"] == "Italian Dunkers / Bagel Bag / Garden Bar"

    events = await _get_events(hass, "2026-08-31 00:00:00", "2026-09-04 00:00:00")
    # Lunch only (Breakfast filtered out): 8/31 and 9/1
    assert len(events) == 2
    assert events[0]["summary"] == "Italian Dunkers / Bagel Bag / Garden Bar"
    assert events[0]["start"] == "2026-08-31"
    assert events[0]["end"] == "2026-09-01"  # exclusive end
    assert "Vegetable: Green Beans, Baby Carrots" in events[0]["description"]
    assert events[0]["location"] == "Inspiration Elementary"
    assert events[1]["summary"] == "Crispy Chicken Sandwich"


@freeze_time("2026-08-31 18:00:00")
async def test_window_filtering(hass, mock_config_entry, mock_api):
    await _setup(hass, mock_config_entry)
    events = await _get_events(hass, "2026-09-01 00:00:00", "2026-09-04 00:00:00")
    assert [e["summary"] for e in events] == ["Crispy Chicken Sandwich"]


@freeze_time("2026-08-31 18:00:00")
async def test_multi_session_prefixes_summary(hass, mock_config_entry, mock_api):
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_SESSIONS: ["Breakfast", "Lunch"],
        },
    )
    await _setup(hass, mock_config_entry)
    events = await _get_events(hass, "2026-08-31 00:00:00", "2026-09-01 00:00:00")
    assert [e["summary"] for e in events] == [
        "Breakfast: French Toast Sticks / Cereal Variety",
        "Lunch: Italian Dunkers / Bagel Bag / Garden Bar",
    ]
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `./.venv/Scripts/python -m pytest tests/test_calendar.py -v`
Expected: FAIL — no `calendar.inspiration_elementary` state (placeholder adds no entities).

- [ ] **Step 3: Implement `calendar.py`** (replace placeholder entirely)

```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run: `./.venv/Scripts/python -m pytest tests/test_calendar.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add custom_components/linqconnect/calendar.py tests/test_calendar.py
git commit -m "Add per-school menu calendar entities"
```

---

### Task 9: Sensor platform

**Files:**
- Modify: `custom_components/linqconnect/sensor.py` (replace the Task 6 placeholder)
- Modify: `tests/test_init.py` (remove the `xfail` marker from `test_setup_and_unload`)
- Test: `tests/test_sensor.py`

**Interfaces:**
- Consumes: coordinator data, `menu_format.summary/menu_dict`, `CONF_DISTRICT_NAME` from entry data.
- Produces: `LinqConnectMenuSensor` — `unique_id = f"{building_id}_{slugify(session)}"`, name = session, state = today's summary truncated to 255, attributes `district`/`meal_name`/`menu`.

- [ ] **Step 1: Write the failing tests**

`tests/test_sensor.py`:
```python
"""Tests for the today's-menu sensors."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from freezegun import freeze_time

from custom_components.linqconnect.api import DayMenu, MenuCategory
from custom_components.linqconnect.const import CONF_SESSIONS
from custom_components.linqconnect.sensor import LinqConnectMenuSensor

from .conftest import BUILDING_1

SENSOR = "sensor.inspiration_elementary_lunch"


async def _setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@freeze_time("2026-08-31 18:00:00")
async def test_today_state_and_attributes(hass, mock_config_entry, mock_api):
    await _setup(hass, mock_config_entry)
    state = hass.states.get(SENSOR)
    assert state is not None
    assert state.state == "Italian Dunkers / Bagel Bag / Garden Bar"
    assert state.attributes["meal_name"] == "Week 2 Monday"
    assert state.attributes["menu"]["Vegetable"] == ["Green Beans", "Baby Carrots"]
    assert state.attributes["district"] == "Brandon Valley School District"


@freeze_time("2026-09-02 18:00:00")
async def test_no_school_day_is_unknown(hass, mock_config_entry, mock_api):
    # fixture has an empty 9/2 → no DayMenu for today
    await _setup(hass, mock_config_entry)
    state = hass.states.get(SENSOR)
    assert state.state == "unknown"
    assert "menu" not in state.attributes


@freeze_time("2026-08-31 18:00:00")
async def test_one_sensor_per_session(hass, mock_config_entry, mock_api):
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_SESSIONS: ["Breakfast", "Lunch"],
        },
    )
    await _setup(hass, mock_config_entry)
    breakfast = hass.states.get("sensor.inspiration_elementary_breakfast")
    assert breakfast is not None
    assert breakfast.state == "French Toast Sticks / Cereal Variety"
    assert hass.states.get(SENSOR) is not None


@freeze_time("2026-08-31 18:00:00")
def test_state_truncated_to_255():
    from datetime import date

    long_day = DayMenu(
        date=date(2026, 8, 31),
        session="Lunch",
        meal_name=None,
        categories=[
            MenuCategory(name="Main Entrée", items=["X" * 300])
        ],
    )
    coordinator = MagicMock()
    coordinator.data = {BUILDING_1: [long_day]}
    sensor = LinqConnectMenuSensor(
        coordinator, BUILDING_1, "Inspiration Elementary", "Lunch", "District"
    )
    assert len(sensor.native_value) == 255
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `./.venv/Scripts/python -m pytest tests/test_sensor.py -v`
Expected: FAIL — no sensor states / no `LinqConnectMenuSensor`.

- [ ] **Step 3: Implement `sensor.py`** (replace placeholder entirely)

```python
"""Today's-menu sensors: one per (building, serving session)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util, slugify

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
```

- [ ] **Step 4: Remove the xfail marker from `tests/test_init.py`** — delete the `@pytest.mark.xfail(...)` line above `test_setup_and_unload` and the now-unused `import pytest` line.

- [ ] **Step 5: Run the full suite, verify pass**

Run: `./.venv/Scripts/python -m pytest tests/ -v`
Expected: all pass, 0 xfailed.

- [ ] **Step 6: Commit**

```bash
git add custom_components/linqconnect/sensor.py tests/test_sensor.py tests/test_init.py
git commit -m "Add today's-menu sensors"
```

---

### Task 10: Options flow

**Files:**
- Modify: `custom_components/linqconnect/config_flow.py` (add options flow)
- Test: `tests/test_options_flow.py`

**Interfaces:**
- Consumes: `entry.data[CONF_IDENTIFIER]` to re-fetch the fresh building list; existing options as defaults.
- Produces: `LinqConnectOptionsFlow` (step `init`) and `LinqConnectConfigFlow.async_get_options_flow`. Saving updates `entry.options` which triggers the Task 6 update listener → entry reload.

- [ ] **Step 1: Write the failing tests**

`tests/test_options_flow.py`:
```python
"""Tests for the options flow."""

from unittest.mock import patch

from freezegun import freeze_time
from homeassistant.data_entry_flow import FlowResultType

from custom_components.linqconnect.api import parse_district
from custom_components.linqconnect.const import CONF_BUILDINGS, CONF_SESSIONS

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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `./.venv/Scripts/python -m pytest tests/test_options_flow.py -v`
Expected: FAIL — options flow not implemented (`UnknownHandler` or similar).

- [ ] **Step 3: Implement — append to `config_flow.py`**

Add imports at the top of the file: `from homeassistant.config_entries import OptionsFlow` (extend the existing import) and `from homeassistant.core import callback`.

Add to `LinqConnectConfigFlow`:
```python
    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> LinqConnectOptionsFlow:
        """Return the options flow."""
        return LinqConnectOptionsFlow()
```

Add at module level:
```python
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
        except LinqConnectApiError:
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
                }
            ),
            errors=errors,
        )
```

- [ ] **Step 4: Run the full suite, verify pass**

Run: `./.venv/Scripts/python -m pytest tests/ -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add custom_components/linqconnect/config_flow.py tests/test_options_flow.py
git commit -m "Add options flow for changing schools and sessions"
```

---

### Task 11: HACS packaging, README, lint, final sweep

**Files:**
- Create: `hacs.json`, `README.md`
- Modify: anything ruff flags

**Interfaces:** none — packaging and polish only.

- [ ] **Step 1: Create `hacs.json`**

```json
{
  "name": "LINQ Connect Menus",
  "render_readme": true
}
```

- [ ] **Step 2: Create `README.md`**

```markdown
# LINQ Connect Menus for Home Assistant

School breakfast/lunch menus from [LINQ Connect](https://linqconnect.com)
as native Home Assistant calendars and sensors. No account required — uses
the same public API as your district's shared menu link.

## What you get

- One **calendar** per school: an all-day event per school day, entrées in
  the title, the full categorized menu in the description.
- One **sensor** per school per serving session (default: Lunch) with
  today's entrées as its state and the full menu as attributes — handy for
  dashboards and TTS ("what's for lunch today?").

## Installation

1. Add this repository to HACS as a custom repository (type: Integration),
   then install **LINQ Connect Menus** and restart Home Assistant.
2. Settings → Devices & Services → Add Integration → **LINQ Connect Menus**.
3. Enter the share code from your district's public menu link
   (`https://linqconnect.com/public/menu/<CODE>`) — or search by district
   name — then pick your schools and serving sessions.

Each district is one config entry; add the integration again for a second
district. Change schools/sessions later via the entry's **Configure** button.

## Notes

- Menus refresh every 6 hours, fetching Monday of the current week through
  six weeks out. Days without a published menu produce no events.
- Not affiliated with LINQ. The API is undocumented and could change.
```

- [ ] **Step 3: Lint and fix**

Run: `./.venv/Scripts/python -m ruff check custom_components tests --fix`
Then: `./.venv/Scripts/python -m ruff check custom_components tests`
Expected: clean. Fix any remaining findings by hand (do not add `noqa`).

- [ ] **Step 4: Full suite, final verification**

Run: `./.venv/Scripts/python -m pytest tests/ -v`
Expected: all pass. Paste the summary line into the commit body if convenient.

- [ ] **Step 5: Commit**

```bash
git add hacs.json README.md custom_components tests
git commit -m "Add HACS metadata and README"
```

---

## Post-plan follow-ups (not tasks)

- Create the GitHub repo `chrisuthe/ha-linqconnect` and push (user's call on timing).
- Live smoke test: copy `custom_components/linqconnect` into a real HA instance, add Brandon Valley via code `L36JZQ`, confirm calendar + sensors populate.
