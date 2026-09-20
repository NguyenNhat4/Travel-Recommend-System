"""Deterministic, data-free normalization of extracted trip intent; catalog values come from the catalog."""
from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from typing import Any


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.replace("đ", "d").replace("Đ", "D"))
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def fold(value: str | None) -> str:
    """Accent-, case-, punctuation- and whitespace-insensitive matching key."""
    text = strip_accents((value or "").casefold())
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def match_destination(value: str, supported: list[str]) -> str | None:
    """Return the one catalog name equal to value ignoring accents, case and punctuation."""
    key = fold(value)
    matches = [name for name in supported if fold(name) == key]
    return matches[0] if key and len(matches) == 1 else None


def clean_interests(values: list[str] | None) -> list[str]:
    seen: set[str] = set()
    cleaned = []
    for value in values or []:
        text = " ".join(str(value).split())
        if text and fold(text) not in seen:
            seen.add(fold(text))
            cleaned.append(text)
    return cleaned[:20]


def normalize_party(intent: dict[str, Any], constraints: dict[str, Any]) -> bool:
    """A family-with-kids party without any child is a guessed count: keep only the type hint."""
    party = intent.get("party")
    if party and party.get("type") == "FAMILY_WITH_KIDS" and not party.get("children"):
        intent["party"] = None
        constraints["party_type_hint"] = "FAMILY_WITH_KIDS"
        return True
    return False


def normalize_intent(intent: dict[str, Any], constraints: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Normalize contract fields that do not need the catalog; returns copies and the changed field names."""
    intent, constraints, changed = deepcopy(intent), deepcopy(constraints), []
    interests = clean_interests(intent.get("interests"))
    if interests != (intent.get("interests") or []):
        intent["interests"] = interests
        changed.append("interests")
    if normalize_party(intent, constraints):
        changed.append("party")
    taxonomies = sorted(set(constraints.get("exclude_taxonomies", [])))
    if taxonomies != constraints.get("exclude_taxonomies", []) and "exclude_taxonomies" in constraints:
        constraints["exclude_taxonomies"] = taxonomies
        changed.append("exclude_taxonomies")
    for key in ("specific_hotel", "specific_activity"):
        if isinstance(constraints.get(key), str):
            text = " ".join(constraints[key].split())
            if text != constraints[key]:
                constraints[key] = text
                changed.append(key)
    return intent, constraints, changed
