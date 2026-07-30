"""Ingredient and held-item helpers for Overcooked v2 symbolic gold."""

from __future__ import annotations

MAX_POT_SLOTS = 3
INGREDIENT_NAMES = ("onion", "tomato", "pepper")


def index_to_held(ingredient_index: int) -> str:
    return f"ing_{ingredient_index}"


def held_to_index(held: str | None) -> int | None:
    if held is None:
        return None
    if held == "onion":
        return 0
    if held.startswith("ing_"):
        return int(held.split("_", 1)[1])
    return None


def normalize_held(held: str | None) -> str | None:
    if held == "onion":
        return index_to_held(0)
    return held


def multiset_from_recipe(ingredients: tuple[int, ...]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for index in ingredients:
        counts[index] = counts.get(index, 0) + 1
    return counts


def pot_total(pot_ingredients: dict[int, int]) -> int:
    return sum(pot_ingredients.values())


def pot_matches_recipe(pot_ingredients: dict[int, int], required: tuple[int, ...]) -> bool:
    return multiset_from_recipe(required) == dict(pot_ingredients)


def can_add_to_pot(pot_ingredients: dict[int, int], ingredient_index: int) -> bool:
    if pot_total(pot_ingredients) >= MAX_POT_SLOTS:
        return False
    return True


def add_to_pot(pot_ingredients: dict[int, int], ingredient_index: int) -> dict[int, int]:
    updated = dict(pot_ingredients)
    updated[ingredient_index] = updated.get(ingredient_index, 0) + 1
    return updated


def pot_onion_count(pot_ingredients: dict[int, int]) -> int:
    return int(pot_ingredients.get(0, 0))
