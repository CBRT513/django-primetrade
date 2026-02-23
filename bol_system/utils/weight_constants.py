"""
Weight & Tonnage Conversion Constants
======================================
BUSINESS DECISION: All conversions use commercial industry-standard values.
1 Metric Ton = 2,200 lbs (commercial standard, not scientific 2,204.62).
This aligns with industry partners (GNP, trading documentation).

Billing unit: Net Tons (Short Tons)
All reports, invoices, and customer-facing displays use Net Tons.

Type safety:
- None input raises TypeError — never silently returns 0 or None
- Empty/whitespace string raises ValueError — never silently returns 0
- Non-numeric string raises InvalidOperation

Decision made: February 2026
Decision maker: Operations Manager, barge2rail.com
"""
from decimal import Decimal

# === Exact Constants ===
LBS_PER_SHORT_TON = Decimal('2000')        # 1 Short Ton (Net Ton) = 2,000 lbs (exact)
LBS_PER_METRIC_TON = Decimal('2200')       # 1 Metric Ton = 2,200 lbs (commercial standard)
SHORT_TONS_PER_METRIC_TON = LBS_PER_METRIC_TON / LBS_PER_SHORT_TON  # = 1.1 (derived, not hardcoded)


def _to_decimal(value):
    """
    Convert input to Decimal safely.

    Accepts: int, float, Decimal, str (non-empty, numeric)
    Returns: Decimal
    Raises:
        TypeError if None
        ValueError if empty/whitespace string
        InvalidOperation if non-numeric string

    Uses Decimal(str(value)) for float inputs to avoid IEEE 754 precision artifacts.
    Example: float 22.05 -> str '22.05' -> Decimal('22.05')
    vs Decimal(22.05) -> Decimal('22.0500000000000006661338147750939...')
    """
    if value is None:
        raise TypeError("Weight conversion received None — check that the source field has a value")
    if isinstance(value, str) and value.strip() == '':
        raise ValueError("Weight conversion received empty string — check that the source field has a value")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


# === Conversion Functions ===
def lbs_to_short_tons(lbs):
    """Convert pounds to Short Tons (Net Tons) — our billing unit."""
    return _to_decimal(lbs) / LBS_PER_SHORT_TON


def short_tons_to_lbs(short_tons):
    """Convert Short Tons (Net Tons) to pounds."""
    return _to_decimal(short_tons) * LBS_PER_SHORT_TON


def lbs_to_metric_tons(lbs):
    """Convert pounds to Metric Tons."""
    return _to_decimal(lbs) / LBS_PER_METRIC_TON


def metric_tons_to_lbs(metric_tons):
    """Convert Metric Tons to pounds."""
    return _to_decimal(metric_tons) * LBS_PER_METRIC_TON


def metric_tons_to_short_tons(metric_tons):
    """Convert Metric Tons to Short Tons (Net Tons) — our billing unit."""
    return _to_decimal(metric_tons) * SHORT_TONS_PER_METRIC_TON


def short_tons_to_metric_tons(short_tons):
    """Convert Short Tons (Net Tons) to Metric Tons."""
    return _to_decimal(short_tons) / SHORT_TONS_PER_METRIC_TON
