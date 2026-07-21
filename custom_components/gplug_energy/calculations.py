"""Pure calculation and unit helpers for gPlug Energy Cockpit."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def numeric_value(raw_state: Any) -> float | None:
    """Parse a numeric Home Assistant state."""
    if raw_state is None or str(raw_state).lower() in {"unknown", "unavailable"}:
        return None
    try:
        return float(Decimal(str(raw_state).strip().replace(",", ".")))
    except (InvalidOperation, ValueError):
        return None


def power_in_watts(raw_state: Any, unit: Any) -> float | None:
    value = numeric_value(raw_state)
    if value is None:
        return None
    normalized = str(unit or "W").strip().lower().replace(" ", "")
    if normalized in {"w", "watt", "watts"}:
        return value
    if normalized in {"kw", "kilowatt", "kilowatts"}:
        return value * 1000
    if normalized in {"mw", "milliwatt", "milliwatts"}:
        return value / 1000
    return None


def energy_in_kwh(raw_state: Any, unit: Any) -> float | None:
    value = numeric_value(raw_state)
    if value is None:
        return None
    normalized = str(unit or "kWh").strip().lower().replace(" ", "")
    if normalized in {"kwh", "kilowatthour", "kilowattstunden"}:
        return value
    if normalized in {"wh", "watthour", "wattstunden"}:
        return value / 1000
    if normalized in {"mwh", "megawatthour", "megawattstunden"}:
        return value * 1000
    return None


def scaled_value(raw_state: Any, unit: Any, target: str) -> float | None:
    value = numeric_value(raw_state)
    if value is None:
        return None
    normalized = str(unit or target).strip().lower().replace(" ", "")
    if target == "V":
        return value * 1000 if normalized == "kv" else value
    if target == "A":
        return value / 1000 if normalized == "ma" else value
    if target == "Hz":
        return value
    return value


def percentage_difference(reference: float, comparison: float, minimum: float) -> float | None:
    if reference == 0 or abs(reference) < minimum:
        return None
    return abs(reference - comparison) / abs(reference) * 100

