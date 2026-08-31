# LINQ Connect Menus — Home Assistant Custom Integration Design

**Date:** 2026-08-31
**Status:** Approved design, pre-implementation
**Repo:** `ha-linqconnect` (HACS custom integration)

## Purpose

Expose school lunch (and optionally breakfast) menus from LINQ Connect
(linqconnect.com) as native Home Assistant calendar entities and "today's
menu" sensors, for one or more schools per district. No official or HACS
integration for LINQ Connect exists today.

## Background: the LINQ Connect API

Undocumented but stable public JSON API at `https://api.linqconnect.com/`,
verified 2026-08-31 against Brandon Valley School District (share code
`L36JZQ`). No authentication of any kind.

### Endpoints used

1. **Resolve share code → district + buildings**

   `GET /api/FamilyMenuIdentifier?identifier=L36JZQ`

   ```json
   {
     "DistrictId": "b1d7358a-818b-ec11-90c7-d2d97b40e955",
     "DistrictName": "Brandon Valley School District",
     "Buildings": [
       {"BuildingId": "0c65b2bc-908d-ec11-8df7-9566c4096294", "Name": "Inspiration Elementary"},
       ...
     ],
     "SelectedBuildingId": "...",
     "MenuNotification": "** Menu Is Subject To Change **",
     "Identifier": "AZB89G"
   }
   ```

   Unknown code → HTTP 404 with `{"Messages": ["District not found."]}`.

2. **Search districts by name** (config flow only)

   `GET /api/FamilyDistrictSearch?currentPage=0&pageSize=20&searchText=<name>`

   Verified 2026-08-31 (the filter param is `searchText`; without it the
   endpoint returns the full district list A→Z). Response:

   ```json
   {
     "Data": [
       {"DistrictId": "b1d7358a-...", "Identifier": "AZB89G",
        "Name": "Brandon Valley School District",
        "City": "Brandon", "State": "South Dakota", "IsActive": true}
     ],
     "CurrentPage": 0, "PageSize": 20, "TotalPages": 1, "TotalRecords": 1
   }
   ```

   The returned `Identifier` is the district's canonical share code, usable
   with endpoint 1 (a district can have multiple valid codes — `L36JZQ`
   and `AZB89G` both resolve to Brandon Valley).

3. **Fetch menus**

   `GET /api/FamilyMenu?buildingId=<guid>&districtId=<guid>&startDate=M-D-YYYY&endDate=M-D-YYYY`

   Note the date format: **`M-D-YYYY`, no zero padding** (e.g. `8-31-2026`).

   Response shape (fields we consume):

   ```
   FamilyMenuSessions[]            e.g. Breakfast, Lunch
     .ServingSession               session display name
     .MenuPlans[]
       .Days[]
         .Date                     "8/31/2026" (M/D/YYYY string, naive)
         .MenuMeals[]              usually 1, may be several
           .MenuMealName           e.g. "Week 2 Monday"
           .RecipeCategories[]
             .CategoryName         e.g. "Main Entrée", "Vegetable", "Fruit", "Milk"
             .Recipes[]
               .RecipeName         e.g. "Italian Dunkers"
               .ServingSize, .Nutrients[], .Allergens[]   (not consumed in v1)
   ```

### Hard constraint: User-Agent

The API sits behind AWS WAF. Default non-browser User-Agents (curl, aiohttp
default) receive **HTTP 403** with an HTML body. A browser-like UA header
is sufficient — no cookie/JS challenge is required (verified with plain
curl + Chrome UA → 200). The client must send a realistic browser
`User-Agent` on every request and treat a 403 as "blocked by WAF" (log a
clear message), distinct from 404 "district not found".

## Architecture

Custom integration (HACS), domain **`linqconnect`**, distributed from this
repo. API client lives inline in the integration (`api.py`) — no separate
PyPI package — but is written HA-free (plain aiohttp + dataclasses) so it
could be extracted later for a core submission.

```
custom_components/linqconnect/
  __init__.py          entry setup: coordinator + platform forward
  api.py               HA-free aiohttp client + dataclasses
  config_flow.py       config + options flow
  coordinator.py       DataUpdateCoordinator
  calendar.py          one CalendarEntity per selected building
  sensor.py            one sensor per (building, session)
  const.py
  manifest.json        config_flow: true, iot_class: cloud_polling,
                       integration_type: hub, version: 0.1.0
  strings.json + translations/en.json
hacs.json
tests/                 pytest + pytest-homeassistant-custom-component
  fixtures/            captured real JSON responses
```

### Data model (`api.py`)

```python
@dataclass
class Building:      building_id: str; name: str
@dataclass
class District:      district_id: str; name: str; identifier: str; buildings: list[Building]
@dataclass
class MenuCategory:  name: str; items: list[str]          # deduped recipe names, API order
@dataclass
class DayMenu:       date: date; session: str; meal_name: str | None
                     categories: list[MenuCategory]
```

Parsing rules:
- One `DayMenu` per (date, session). Multiple `MenuPlans` / `MenuMeals`
  contributing to the same date+session are merged: categories concatenated
  in encounter order, recipe names deduped case-sensitively within a
  category. `meal_name` = first MenuMealName seen.
- `Date` strings are naive `M/D/YYYY`; parsed to `datetime.date`. No
  timezone handling anywhere (all-day semantics).
- Days with no `MenuMeals` or empty sessions simply produce no `DayMenu`
  (no-school days are absent, not empty).

Client methods:
- `resolve_identifier(code) -> District` — raises `DistrictNotFoundError` on 404
- `search_districts(name) -> list[District]` (buildings not populated)
- `get_menus(district_id, building_id, start, end) -> list[DayMenu]`
- All raise `LinqConnectApiError` on network errors / non-2xx (with the
  WAF-403 special-cased in the message).

## Config flow

One **config entry per district**. Entry `unique_id` = `DistrictId` GUID
(prevents duplicate district entries).

- **Step `user`:** single form with two mutually exclusive fields —
  share code (e.g. `L36JZQ`) or district name. Code takes precedence if
  both filled; error `district_not_found` on bad code; empty search results
  → error `no_results`.
- **Step `pick_district`:** only when name search returned matches — select
  one (labeled `"{Name} — {City}, {State}"`); its `Identifier` is then
  resolved via `FamilyMenuIdentifier` to get buildings.
- **Step `schools`:** multi-select of the district's buildings (min 1) +
  multi-select of serving sessions, **default `["Lunch"]`**. Session
  choices offered: Breakfast, Lunch, Snack, Dinner (free-form match against
  API session names, case-insensitive). Session selection applies to all
  schools in the entry.
- **Options flow:** re-shows the `schools` step pre-populated; saving
  reloads the entry. `async_remove_config_entry_device` returns `True` for
  buildings no longer selected so stale devices can be deleted from the UI.

Config entry data: `{district_id, district_name, identifier}`;
options: `{building_ids: [...], sessions: [...]}` (buildings stored as
`{id: name}` mapping so entity setup needs no extra API call).

## Coordinator

One `DataUpdateCoordinator[dict[str, list[DayMenu]]]` per entry
(key = building_id).

- **Update interval: 6 hours.** Menus are published weeks ahead but are
  "subject to change"; 4 fetches/day per school is polite and fresh enough.
- **Window per refresh:** previous Monday → +42 days.
- One `get_menus` call per selected building per refresh, sequential (be
  kind to the API; 8 schools = 8 quick GETs).
- Failures raise `UpdateFailed`; coordinator serves last-good data and
  entities stay available with stale data until recovery (standard
  coordinator behavior). First refresh via
  `async_config_entry_first_refresh` so a dead API fails setup visibly
  (`ConfigEntryNotReady`).

## Entities

**One device per selected building**: identifiers `(DOMAIN, building_id)`,
name = building name, manufacturer "LINQ", via config entry. All entities
use `has_entity_name`.

### Calendar (one per building)

- `unique_id` = `{building_id}` ; entity name `None` → entity takes the
  device (school) name.
- Events generated from coordinator data for the entry's selected sessions:
  - **All-day event** per `DayMenu`: `start = date`,
    `end = date + 1 day` (HA all-day events use an exclusive end date).
  - **Summary:** entrée item names joined `" / "`. Entrée category = first
    category whose name contains `entrée`/`entree` (case-insensitive);
    fallback = first category. When the entry has >1 session selected,
    prefix `"{session}: "`.
  - **Description:** one line per category — `"{name}: {items joined ', '}"`
    — preceded by the `MenuMealName` line when present.
  - **Location:** building name.
- `event` property (next/current event) and `async_get_events(start, end)`
  both read only coordinator data — no I/O.

### Sensor (one per building × selected session)

- `unique_id` = `{building_id}_{session_slug}`; name = session name
  ("Lunch") → shows as "Inspiration Elementary Lunch".
- **State:** today's entrée summary string (same string as the calendar
  event summary, without session prefix), truncated to 255 chars.
  `None` (unknown) when today has no menu.
- **Attributes:** `meal_name`, `menu` (dict of category → item list),
  `district`.

## Error handling summary

| Condition | Behavior |
|---|---|
| WAF 403 | `LinqConnectApiError` with UA hint; `UpdateFailed` / config-flow error `cannot_connect` |
| Unknown share code | Config-flow field error `district_not_found` |
| Name search empty | Config-flow field error `no_results` |
| Network error mid-operation | `UpdateFailed`, last-good data retained |
| API down at setup | `ConfigEntryNotReady` (HA retries with backoff) |
| No menu for a day | No event, sensor unknown — not an error |
| Session not in response (e.g. district publishes no Breakfast) | No events/none state for that session — not an error |

## Testing

pytest + `pytest-homeassistant-custom-component`. Fixture JSON captured
from the real API (Brandon Valley, 2026-08-31): `FamilyMenuIdentifier`
response and a two-week `FamilyMenu` response.

- `api.py`: parse fixtures → correct `DayMenu` list; date parsing; merge
  of multiple MenuMeals; 403 and 404 mapping (aioresponses).
- Config flow: happy path via code; happy path via search; bad code;
  duplicate district aborts; options flow reload.
- Calendar: `async_get_events` window filtering; all-day start/end
  (exclusive end date); summary entrée extraction incl. fallback when no
  entrée-named category; session prefix logic.
- Sensor: state today / unknown on no-school day; attributes.

## Out of scope (v1)

- Nutrition/allergen data (present in API, deliberately unused)
- ICS export, add-on packaging
- Non-menu LINQ Connect features (balances, payments — those need auth)
- HA core submission (would require extracting `api.py` to PyPI)
