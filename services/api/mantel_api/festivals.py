"""The festivals the diet rules name, as a family says them.

settings.yaml matches observances by substring, so one festival is often
written two or three ways — "navaratri" and "navratri", "karwa chauth",
"karva chauth" and "karaka chaturthi" — because the feeds spell it
differently from year to year. That is right for matching and wrong for a
screen: a parent should see Navratri once, with one span. The aliases stay
in the file and never render.
"""

from __future__ import annotations

from .models import FestivalGroup, FestivalRule

#: Alias (a `match:` in settings.yaml) to the name a parent reads.
CANONICAL: dict[str, str] = {
    "navaratri": "Navratri",
    "navratri": "Navratri",
    "dussehra": "Dussehra",
    "durga": "Durga Puja",
    "shivaratri": "Shivaratri",
    "shivratri": "Shivaratri",
    "dhanteras": "Dhanteras",
    "diwali": "Diwali",
    "janmashtami": "Janmashtami",
    "ganesh chaturthi": "Ganesh Chaturthi",
    "ram navami": "Ram Navami",
    "hanuman jayanti": "Hanuman Jayanti",
    "karwa chauth": "Karwa Chauth",
    "karva chauth": "Karwa Chauth",
    "karaka chaturthi": "Karwa Chauth",
    "sharad purnima": "Sharad Purnima",
    "kojagiri": "Sharad Purnima",
    "naraka chaturdasi": "Naraka Chaturdasi",
    "govardhan": "Govardhan Puja",
    "bhai d": "Bhai Dooj",
    "holi": "Holi",
    "raksha bandhan": "Raksha Bandhan",
    "makar sankranti": "Makar Sankranti",
}


def name_of(match: str) -> str:
    """The festival an alias belongs to; one nobody listed says itself."""
    key = match.strip().lower()
    return CANONICAL.get(key) or key.title()


def groups(rules: list[FestivalRule]) -> list[FestivalGroup]:
    """One entry per festival, in the order the file first names it. Its
    span is the longest any of its aliases asks for."""
    found: dict[str, FestivalGroup] = {}
    for rule in rules:
        name = name_of(rule.match)
        group = found.get(name)
        if group is None:
            found[name] = FestivalGroup(name=name, span_days=rule.span_days, matches=[rule.match])
        else:
            group.matches.append(rule.match)
            group.span_days = max(group.span_days, rule.span_days)
    return list(found.values())
