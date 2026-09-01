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
