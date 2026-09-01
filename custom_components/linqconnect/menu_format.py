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
