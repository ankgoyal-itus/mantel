"""The dish catalog, and what happens when a plan points at nothing."""

from __future__ import annotations

from datetime import date as Date
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from mantel_api.app import app
from mantel_api.content import Content
from mantel_api.models import Meals, MealsCatalog
from mantel_api.paths import content_dir

SLOTS = {"breakfast", "lunch", "dinner", "snack", "salad"}
PROTEINS = {"veg", "egg", "chicken", "fish"}


def real_catalog() -> MealsCatalog:
    raw = yaml.safe_load((content_dir() / "meals-catalog.yaml").read_text(encoding="utf-8"))
    return MealsCatalog.model_validate(raw)


def test_the_catalog_loads_and_validates() -> None:
    catalog = real_catalog()

    assert catalog.version == 1
    # The sample's thirteen, and the two it never has to write.
    assert len(catalog.dishes) >= 15
    assert len({dish.id for dish in catalog.dishes}) == len(catalog.dishes)

    for dish in catalog.dishes:
        assert dish.slot in SLOTS
        assert dish.protein, f"{dish.id} has no protein"
        assert set(dish.protein) <= PROTEINS
        # Lunch out and Dinner out are places, and take no cooking.
        assert dish.minutes > 0 or dish.id in ("lunch_out", "dinner_out")

    # The built-in two are there whatever the file says.
    names = catalog.names
    assert names["dinner_out"] == "Dinner out"
    assert names["idli_sambar"] == "Idli and sambar"


def test_every_slot_has_something_in_it() -> None:
    catalog = real_catalog()
    # The three the dashboard draws; snack and salad are a family's choice.
    for slot in ("breakfast", "lunch", "dinner"):
        assert catalog.for_slot(slot), f"nothing for {slot}"
    assert len(catalog.for_slot(None)) == len(catalog.dishes)


def test_duplicate_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate dish id"):
        MealsCatalog.model_validate(
            {
                "version": 1,
                "dishes": [
                    {"id": "x", "name": "One", "slot": "lunch", "protein": ["veg"],
                     "cuisine": "indian", "minutes": 10},
                    {"id": "x", "name": "Two", "slot": "lunch", "protein": ["veg"],
                     "cuisine": "indian", "minutes": 10},
                ],
            }
        )


def test_a_dish_needs_at_least_one_protein() -> None:
    with pytest.raises(ValidationError):
        MealsCatalog.model_validate(
            {
                "version": 1,
                "dishes": [
                    {"id": "x", "name": "One", "slot": "lunch", "protein": [],
                     "cuisine": "indian", "minutes": 10},
                ],
            }
        )


def test_an_unknown_dish_id_in_the_plan_fails(content: Content, content_dir: Path) -> None:
    (content_dir / "meals.yaml").write_text(
        "2026-09-23:\n  dinner: {id: not_a_dish}\n", encoding="utf-8"
    )
    content.load_all()

    assert content.meals.status.startswith("error:")
    assert "not_a_dish" in content.meals.status
    # The last good plan keeps serving.
    current = content.meals.current
    assert current is not None
    assert current.root


real_client = TestClient(app)


def test_the_real_plan_serves_resolved_names() -> None:
    """Every dish id in the real plan resolves to a name from the catalog.

    This used to name the dinner on one Thursday, and it broke the first time
    somebody changed what the house was eating — which is a thing that
    happens weekly, and now also happens whenever a child uses the picker.
    What is worth asserting is the join: an id in meals.yaml becomes a name,
    a protein and a note, for every day of the plan and not just one.
    """
    names = {dish.id: dish.name for dish in real_catalog().dishes}
    for day in real_client.get("/api/agenda?days=14").json():
        for slot in ("breakfast", "lunch", "dinner", "snack"):
            cell = day["meals"][slot]
            if cell is None:
                continue
            assert cell["name"], f"{day['date']} {slot} resolved to nothing"
            if cell["id"]:
                assert cell["name"] in names.values(), f"{slot} is not a dish in the catalog"


def test_a_note_with_a_comma_survives_the_flow_scalar() -> None:
    """Said of a plan written here rather than of the family's: since 24 Sep
    2026 the week is picked from the catalog, so the real plan may have no
    notes at all on a given day, and that is the family, not the parser."""
    text = (
        "2026-10-08:\n"
        '  lunch: {id: dal_rice, note: "from last night, lunchbox"}\n'
        "  breakfast: {id: veggie_omelette, kids_protein: egg}\n"
    )
    meals = Meals.model_validate(
        yaml.safe_load(text), context={"dish_names": real_catalog().names}
    )
    day = meals.on(Date(2026, 10, 8))
    assert day.lunch is not None and day.lunch.note == "from last night, lunchbox"
    assert day.breakfast is not None and day.breakfast.kids_protein == "egg"


def test_health_reports_the_catalog() -> None:
    assert real_client.get("/api/health").json()["content"]["meals-catalog"] == "ok"


def test_the_catalog_endpoint_filters_by_slot() -> None:
    every = real_client.get("/api/meals/catalog").json()
    dinners = real_client.get("/api/meals/catalog?slot=dinner").json()

    assert len(every) == len(real_catalog().dishes)
    assert 0 < len(dinners) < len(every)
    assert {dish["slot"] for dish in dinners} == {"dinner"}
    assert real_client.get("/api/meals/catalog?slot=dessert").status_code == 422
