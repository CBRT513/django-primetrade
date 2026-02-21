# Weight & Tonnage Standards
**Effective:** February 2026
**Decision Authority:** Operations Manager, barge2rail.com

## Billing Unit
All billing, inventory reports, and customer-facing documents use **Net Tons (Short Tons)**.

## Constants (Commercial Industry Standard)
| Constant | Value | Usage |
|----------|-------|-------|
| 1 Short Ton (Net Ton) | 2,000 lbs | Exact, by definition |
| 1 Metric Ton | 2,200 lbs | Commercial industry standard |
| 1 Metric Ton | 1.10 Short Tons | Derived: 2,200 / 2,000 |

**Note:** The scientific value for 1 MT is 2,204.62 lbs. We use the commercial standard of 2,200 lbs per industry practice (ref: GNP). This is a deliberate business decision.

## Approved Display Labels
| Label | Meaning | When to Use |
|-------|---------|-------------|
| **NT** | Net Tons (Short Tons, 2,000 lbs) | Billing, inventory, customer docs |
| **MT** | Metric Tons (2,200 lbs) | Supplier/import data only |
| **lbs** | Pounds | Weights in pounds |

### Prohibited Labels
- Bare "T" or "t"
- "Tons" or "tons" without NT/MT qualifier
- "Tonnage" without unit context
- Any weight value displayed without a unit label

## Code Requirements
1. **Never hardcode conversion factors.** Import from `weight_constants.py`.
2. **Every weight model field** must have `help_text` specifying the unit.
3. **Every API response** returning weight must include the unit label or a `"unit"` key.
4. **Every UI display** of weight must show NT, MT, or lbs.
5. **Every generated document** (PDF, CSV, Excel, email) must label all weight values.

## Conversion Functions
Use the shared `weight_constants.py` module in each codebase:
- `lbs_to_short_tons(lbs)`
- `short_tons_to_lbs(short_tons)`
- `lbs_to_metric_tons(lbs)`
- `metric_tons_to_lbs(metric_tons)`
- `metric_tons_to_short_tons(metric_tons)`
- `short_tons_to_metric_tons(short_tons)`

## Code Review Checklist (Weight Items)
When reviewing any PR that touches weight data:
- [ ] Uses constants from `weight_constants.py` (no hardcoded 2000, 2200, etc.)
- [ ] New weight fields have `help_text` with unit
- [ ] UI displays include unit label (NT, MT, or lbs)
- [ ] API responses include unit
- [ ] Generated documents label all weight values
- [ ] No bare "T", "tons", or unlabeled weights introduced
