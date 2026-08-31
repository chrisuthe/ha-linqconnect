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
