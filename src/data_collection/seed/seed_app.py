"""App-side projection of the history seed.

The persona trips are generated together with CDP events so the purchase and
booking share one event_group_id.  This module keeps the app-table boundary
explicit without duplicating that business rule.
"""
from __future__ import annotations


def rows_from_history(history: dict) -> dict[str, list[dict]]:
    """Select the rows owned by schema ``app`` from a history result."""
    return {
        "users": history["users"],
        "bookings": history["bookings"],
        "booking_items": history["booking_items"],
    }

