"""
Weight & Tonnage Conversion Constants
======================================
BUSINESS DECISION: All conversions use commercial industry-standard values.
1 Metric Ton = 2,200 lbs (commercial standard, not scientific 2,204.62).
This aligns with industry partners (GNP, trading documentation).

Billing unit: Net Tons (Short Tons)
All reports, invoices, and customer-facing displays use Net Tons.

Decision made: February 2026
Decision maker: Operations Manager, barge2rail.com
"""
from decimal import Decimal

# === Exact Constants ===
LBS_PER_SHORT_TON = Decimal('2000')        # 1 Short Ton (Net Ton) = 2,000 lbs (exact)
LBS_PER_METRIC_TON = Decimal('2200')       # 1 Metric Ton = 2,200 lbs (commercial standard)
SHORT_TONS_PER_METRIC_TON = Decimal('1.10') # 1 MT = 1.10 NT (derived: 2200 / 2000)


# === Conversion Functions ===
def lbs_to_short_tons(lbs):
    """Convert pounds to Short Tons (Net Tons) — our billing unit."""
    return Decimal(str(lbs)) / LBS_PER_SHORT_TON


def short_tons_to_lbs(short_tons):
    """Convert Short Tons (Net Tons) to pounds."""
    return Decimal(str(short_tons)) * LBS_PER_SHORT_TON


def lbs_to_metric_tons(lbs):
    """Convert pounds to Metric Tons."""
    return Decimal(str(lbs)) / LBS_PER_METRIC_TON


def metric_tons_to_lbs(metric_tons):
    """Convert Metric Tons to pounds."""
    return Decimal(str(metric_tons)) * LBS_PER_METRIC_TON


def metric_tons_to_short_tons(metric_tons):
    """Convert Metric Tons to Short Tons (Net Tons) — our billing unit."""
    return Decimal(str(metric_tons)) * SHORT_TONS_PER_METRIC_TON


def short_tons_to_metric_tons(short_tons):
    """Convert Short Tons (Net Tons) to Metric Tons."""
    return Decimal(str(short_tons)) / SHORT_TONS_PER_METRIC_TON
