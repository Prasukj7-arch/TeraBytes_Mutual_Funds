"""Display formatting utilities for the Mutual Fund Analytics Platform.

All currency helpers default to the Indian numbering system
(lakhs / crores) with the ₹ prefix.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Union

import pandas as pd


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _indian_comma_format(integer_part: int) -> str:
    """Format an integer using the Indian comma grouping system.

    The rightmost three digits form the first group, and every subsequent
    group contains two digits.  E.g. 12,50,000 instead of 1,250,000.
    """
    s = str(abs(integer_part))
    if len(s) <= 3:
        return s
    last_three = s[-3:]
    remaining = s[:-3]
    # Group the remaining digits in pairs from the right
    groups: list[str] = []
    while len(remaining) > 2:
        groups.append(remaining[-2:])
        remaining = remaining[:-2]
    if remaining:
        groups.append(remaining)
    groups.reverse()
    return ",".join(groups) + "," + last_three


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_currency(value: float, prefix: str = "₹") -> str:
    """Format a number as currency with Indian comma grouping.

    Args:
        value: The numeric value to format.
        prefix: Currency symbol prefix.

    Returns:
        Formatted string, e.g. ``'₹1,25,000'`` or ``'-₹1,25,000'``.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return f"{prefix}0"
    sign = "-" if value < 0 else ""
    abs_val = abs(value)
    integer_part = int(abs_val)
    decimal_part = abs_val - integer_part
    formatted_int = _indian_comma_format(integer_part)
    if decimal_part > 0.005:
        return f"{sign}{prefix}{formatted_int}.{round(decimal_part * 100):02d}"
    return f"{sign}{prefix}{formatted_int}"


def format_currency_cr(value: float) -> str:
    """Format a large number in crores.

    Args:
        value: Absolute value (not already in crores).

    Returns:
        E.g. ``'₹1,250 Cr'``.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "₹0 Cr"
    cr_value = value / 1e7
    if abs(cr_value) >= 100:
        return f"₹{cr_value:,.0f} Cr"
    if abs(cr_value) >= 1:
        return f"₹{cr_value:,.2f} Cr"
    return f"₹{cr_value:,.3f} Cr"


def format_currency_lakhs(value: float) -> str:
    """Format a large number in lakhs.

    Args:
        value: Absolute value.

    Returns:
        E.g. ``'₹12.5 L'``.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "₹0 L"
    lakh_value = value / 1e5
    if abs(lakh_value) >= 100:
        return f"₹{lakh_value:,.0f} L"
    return f"₹{lakh_value:,.1f} L"


def format_pct(value: float, decimals: int = 2) -> str:
    """Format a decimal as a signed percentage string.

    Args:
        value: Decimal value (0.12 → +12.00%).
        decimals: Number of decimal places.

    Returns:
        E.g. ``'+12.50%'`` or ``'-3.20%'``.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "0.00%"
    pct = value * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.{decimals}f}%"


def format_number(value: float, decimals: int = 2) -> str:
    """Format a number with standard comma separation.

    Args:
        value: Numeric value.
        decimals: Decimal places.

    Returns:
        E.g. ``'1,234.56'``.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "0"
    return f"{value:,.{decimals}f}"


def format_large_number(value: float) -> str:
    """Auto-format a number as Cr / L / K depending on magnitude.

    Args:
        value: Numeric value.

    Returns:
        Human-readable string with appropriate suffix.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "₹0"
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1e7:
        return f"{sign}₹{abs_val / 1e7:,.2f} Cr"
    if abs_val >= 1e5:
        return f"{sign}₹{abs_val / 1e5:,.2f} L"
    if abs_val >= 1e3:
        return f"{sign}₹{abs_val / 1e3:,.2f} K"
    return f"{sign}₹{abs_val:,.2f}"


def format_delta(value: float) -> str:
    """Format a value with ▲ / ▼ directional indicators.

    Args:
        value: Decimal value representing change.

    Returns:
        E.g. ``'▲ 12.50%'`` or ``'▼ 3.20%'``.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "— 0.00%"
    pct = value * 100
    if pct > 0:
        return f"▲ {pct:.2f}%"
    if pct < 0:
        return f"▼ {abs(pct):.2f}%"
    return f"— {pct:.2f}%"


def get_color_for_value(value: float) -> str:
    """Return a CSS-style hex colour based on sign.

    Args:
        value: Numeric value.

    Returns:
        Green hex for positive/zero, red hex for negative.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "#94A3B8"  # muted grey
    if value > 0:
        return "#10B981"  # emerald / success
    if value < 0:
        return "#EF4444"  # red / danger
    return "#94A3B8"


def format_risk_level(score: int) -> str:
    """Convert a 1-10 risk score to a human-readable label.

    Args:
        score: Risk score from 1 to 10.

    Returns:
        ``'Low'``, ``'Medium'``, or ``'High'``.
    """
    if score <= 3:
        return "Low"
    if score <= 6:
        return "Medium"
    return "High"


def truncate_text(text: str, max_len: int = 30) -> str:
    """Truncate text to a maximum length, appending ``'…'`` if needed.

    Args:
        text: Input string.
        max_len: Maximum output length including the ellipsis.

    Returns:
        Truncated string.
    """
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def format_date(date_val: Union[str, date, datetime, pd.Timestamp]) -> str:
    """Format a date value as ``'DD MMM YYYY'``.

    Args:
        date_val: Date-like object or ISO string.

    Returns:
        E.g. ``'23 Jun 2026'``.
    """
    if date_val is None:
        return ""
    if isinstance(date_val, str):
        try:
            date_val = pd.to_datetime(date_val)
        except (ValueError, TypeError):
            return date_val
    if isinstance(date_val, (datetime, date, pd.Timestamp)):
        return date_val.strftime("%d %b %Y")
    return str(date_val)
