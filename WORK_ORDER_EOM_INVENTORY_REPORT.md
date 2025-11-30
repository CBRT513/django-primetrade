# Work Order: EOM Inventory Report Feature

**Created:** 2025-11-28
**Priority:** Normal
**Risk Level:** LOW (new feature, no existing data changes)

---

## Overview

Add End-of-Month (EOM) Inventory Report to PrimeTrade. Admin and Office users can select a date range and see:
- Beginning inventory (as of from_date)
- BOLs shipped during the period (with official weights)
- Ending inventory (as of to_date)

Output: On-screen HTML table + PDF download option.

---

## Requirements

### Functional
1. Date range selector (from_date, to_date)
2. Report shows per Product:
   - Beginning Inventory = `Product.start_tons` minus all BOLs shipped BEFORE from_date
   - Shipped During Period = SUM of `BOL.official_weight_tons` (or `net_tons` if official not set) for BOLs with date in range
   - Ending Inventory = Beginning minus Shipped
3. BOL detail rows showing individual shipments in the period
4. PDF download button generates branded report
5. Access restricted to Admin and Office roles

### Non-Functional
- Follow existing view patterns in `bol_system/views.py`
- Use `@require_role('Admin', 'Office')` decorator
- Match existing UI styling (Tailwind CSS)

---

## Technical Specification

### Files to Create/Modify

#### 1. New Template: `templates/inventory-report.html`
- Date range inputs (from_date, to_date)
- Submit button to filter
- Results table with columns:
  - Product Name
  - Beginning Inventory (tons)
  - Shipped This Period (tons)
  - Ending Inventory (tons)
- Expandable detail rows showing BOLs per product
- PDF Download button
- Style: Match existing templates like `releases.html`

#### 2. Modify: `bol_system/views.py`
Add new view function:

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_role('Admin', 'Office')
def inventory_report(request):
    """
    EOM Inventory Report with date range filtering.
    
    Query params:
    - from_date: Start of period (YYYY-MM-DD)
    - to_date: End of period (YYYY-MM-DD)
    - format: 'json' (default) or 'pdf'
    """
```

Logic:
```python
# For each active Product:
# 1. Beginning = start_tons - SUM(official_weight_tons or net_tons) WHERE date < from_date
# 2. Shipped = SUM(official_weight_tons or net_tons) WHERE from_date <= date <= to_date
# 3. Ending = Beginning - Shipped
# 4. Include BOL details for the period
```

#### 3. Modify: `bol_system/urls.py`
Add route:
```python
path('inventory-report/', views.inventory_report, name='inventory_report'),
```

#### 4. Modify: `primetrade_project/urls.py`
Add template route:
```python
path('inventory-report/', TemplateView.as_view(template_name='inventory-report.html'), name='inventory_report_page'),
```

#### 5. New/Modify: `bol_system/inventory_report_pdf.py`
Create PDF generator function based on existing `generate_inventory_report.py` pattern:
```python
def generate_eom_inventory_pdf(report_data, from_date, to_date):
    """
    Generate branded PDF for EOM inventory report.
    Returns: PDF bytes or file path
    """
```

---

## Data Model Reference

### BOL Model (relevant fields)
```python
class BOL(TimestampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    date = models.CharField(max_length=20)  # String format, needs parsing
    net_tons = models.DecimalField(max_digits=10, decimal_places=2)
    official_weight_tons = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
```

### Product Model (relevant fields)
```python
class Product(TimestampedModel):
    name = models.CharField(max_length=200, unique=True)
    start_tons = models.DecimalField(max_digits=10, decimal_places=2, default=0)
```

### Important Notes
- `BOL.date` is a STRING field (not DateField) - parse with multiple formats
- Use `official_weight_tons` if available, fall back to `net_tons`
- Existing helper in views.py: `_parse_date_any()` handles date parsing

---

## Calculation Example

Given:
- Product "Nodular Pig Iron" with `start_tons = 10,000`
- BOLs before Nov 1: 3,000 tons shipped
- BOLs Nov 1-30: 1,500 tons shipped

Report for Nov 1-30:
- Beginning: 10,000 - 3,000 = **7,000 tons**
- Shipped: **1,500 tons**
- Ending: 7,000 - 1,500 = **5,500 tons**

---

## UI Mockup (ASCII)

```
┌─────────────────────────────────────────────────────────────┐
│  INVENTORY REPORT                          [Download PDF]   │
├─────────────────────────────────────────────────────────────┤
│  From: [2025-11-01]  To: [2025-11-30]  [Generate Report]   │
├─────────────────────────────────────────────────────────────┤
│  Product          │ Beginning │ Shipped │ Ending           │
├───────────────────┼───────────┼─────────┼──────────────────┤
│  ▶ Nodular Pig    │  7,000.00 │ 1,500.00│  5,500.00        │
│    └─ PRT-2025-01 │           │   500.00│  (Nov 5)         │
│    └─ PRT-2025-02 │           │   450.00│  (Nov 12)        │
│    └─ PRT-2025-03 │           │   550.00│  (Nov 20)        │
├───────────────────┼───────────┼─────────┼──────────────────┤
│  TOTALS           │  7,000.00 │ 1,500.00│  5,500.00        │
└─────────────────────────────────────────────────────────────┘
```

---

## Testing Checklist

- [ ] Date range filters work correctly
- [ ] Beginning inventory calculation correct (start_tons minus pre-period BOLs)
- [ ] Shipped calculation uses official_weight_tons when available
- [ ] Ending = Beginning - Shipped
- [ ] PDF downloads with correct data
- [ ] Admin can access
- [ ] Office can access  
- [ ] Client cannot access (403)
- [ ] Empty date range shows all-time data or error message

---

## Acceptance Criteria

1. ✅ Admin/Office users see "Inventory Report" link in navigation
2. ✅ Date range selection works
3. ✅ Report shows correct Beginning/Shipped/Ending per product
4. ✅ BOL details expandable per product
5. ✅ PDF download generates branded report
6. ✅ Client users get 403 forbidden

---

## Reference Files

- Existing views pattern: `bol_system/views.py` (see `balances()` function)
- Existing PDF generation: `generate_inventory_report.py`
- Template examples: `templates/releases.html`, `templates/release_detail.html`
- RBAC decorator: `primetrade_project/decorators.py`
- Date parsing: `_parse_date_any()` in `bol_system/views.py`

---

## Handoff Notes

This is a LOW RISK feature addition:
- No changes to existing data
- New endpoints only
- Follows established patterns
- Can be tested locally before deploy

Start with the API endpoint, verify calculations work, then build the template.
