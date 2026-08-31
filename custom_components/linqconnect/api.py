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
