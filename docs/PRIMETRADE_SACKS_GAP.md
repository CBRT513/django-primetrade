# PrimeTrade ↔ Sacks Gap Analysis

**Generated:** 2026-01-06 (architecture unchanged, validated 2026-01-13)  
**Purpose:** Phase 0 Discovery - Document 6 of 6

---

## Executive Summary

Sacks has **70% of required infrastructure** for PrimeTrade migration. Key gaps are:
- BOL generation and PDF workflow
- Weight variance tracking
- Chemistry/lot management
- AI-powered release parsing

The Composable Architecture (Universal + Extension + Config) maps well to PrimeTrade's needs.

---

## Architecture Comparison

| Aspect | PrimeTrade | Sacks | Gap |
|--------|------------|-------|-----|
| Multi-tenant | Single tenant (bugs) | Proper row-level isolation | ✅ Sacks better |
| Customer model | Flat with ShipTo | Universal + TenantCustomer | ✅ Sacks better |
| Product tracking | Product + Lot + Chemistry | Item + Sort + attributes | 🔄 Adapt |
| Release workflow | Release → Load → BOL | Release → Line → Allocation | 🔄 Adapt |
| BOL generation | Full PDF workflow | BOLSequence only | ❌ Build |
| Weight tracking | net_tons + official_weight | None | ❌ Build |
| Inventory | Product-level | Location-level (Sort) | 🔄 Adapt |
| Audit trail | AuditLog table | django-simple-history | ✅ Sacks better |

---

## Model Mapping

### ✅ Direct Mappings (Ready)

| PrimeTrade | Sacks | Notes |
|------------|-------|-------|
| Tenant | Tenant | Add product_type='pigiron' |
| Customer | Customer (universal) | Already composable |
| CustomerShipTo | TenantCustomer | Includes address fields |
| Carrier | Carrier | Already tenant-scoped |
| Truck | Truck | Identical structure |

### 🔄 Adaptation Required

| PrimeTrade | Sacks | Adaptation |
|------------|-------|------------|
| Product | Item | Add chemistry fields to Item or use Sort.attributes |
| Lot | Sort | Map lot_number + chemistry → Sort with attributes |
| Release | Release | Different status flow - see workflow section |
| ReleaseLoad | ReleaseLine | PRT has dates/tonnage, Sacks has qty/allocation |

### ❌ Must Build

| PrimeTrade Model | Description | Build Effort |
|------------------|-------------|--------------|
| BOL | Bill of Lading with PDF | MEDIUM |
| BOLCounter | Yearly sequence | Already exists (BOLSequence) |
| Weight fields | official_weight_tons, variance | LOW |
| Chemistry fields | c, si, s, p, mn | LOW |

---

## Feature Gap Analysis

### 1. Release Workflow

**PrimeTrade Flow:**
```
Upload PDF → AI Parse → Approve → Create Loads → Schedule → Create BOL → Ship
```

**Sacks Flow:**
```
Create Release → Allocate (FIFO) → Stage → Verify → Ship
```

**Gap:** PrimeTrade is **document-driven** (PDF parsing), Sacks is **inventory-driven** (allocation).

**Adaptation Strategy:**
- Add `source_pdf_url` to Release (exists as pdf_s3_key)
- Create PigIronReleaseLine extending ReleaseLine concept
- Add `scheduled_date`, `planned_tons` to line model
- Skip allocation step for tonnage-based products

### 2. BOL Generation

**PrimeTrade Has:**
- BOL model with 30+ fields
- PDF generation (ReportLab)
- S3 storage (pdf_url, pdf_key)
- Email notification
- Stamped PDF with official weights

**Sacks Has:**
- BOLSequence (number generation)
- No BOL entity
- No PDF generation

**Build Requirements:**
```python
class BOL(models.Model):
    tenant = FK(Tenant)
    bol_number = CharField  # From BOLSequence
    release_line = FK(ReleaseLine)
    
    # Snapshot fields
    customer_name = CharField
    ship_to = TextField
    carrier_name = CharField
    truck_number = CharField
    
    # Weight (PigIron specific)
    net_tons = DecimalField
    official_weight_tons = DecimalField(null=True)
    weight_variance_tons = DecimalField(null=True)
    
    # PDF
    pdf_url = URLField
    pdf_key = CharField  # S3 key
    stamped_pdf_url = URLField
    
    # Void support
    is_void = BooleanField
    voided_at = DateTimeField(null=True)
```

**Effort:** 2-3 days (model + PDF generator + views)

### 3. Weight Tracking

**PrimeTrade Has:**
- `net_tons` - CBRT scale weight (estimate)
- `official_weight_tons` - Certified scale (entered later)
- `weight_variance_tons` - Calculated difference
- `weight_variance_percent` - Percentage
- Stamped PDF with official weight

**Sacks Has:**
- `Sort.weight` - Weight per sack (fixed)
- No variance tracking

**Build Requirements:**
- Add weight fields to BOL model
- Create weight entry view
- Create stamped PDF generator
- Add variance calculation logic

**Effort:** 1 day

### 4. Chemistry Tracking

**PrimeTrade Has:**
- Lot.c, si, s, p, mn (chemistry values)
- Product mirrors latest lot chemistry
- Chemistry validation on release approval (tolerance check)
- Chemistry display on BOL

**Sacks Has:**
- Sort.attributes (JSONB - flexible)
- No chemistry validation

**Adaptation Strategy:**
Option A: Add chemistry fields to Item model
```python
class Item(models.Model):
    # ... existing fields ...
    chemistry = JSONField(default=dict)  # {"c": 4.286, "si": 0.025, ...}
```

Option B: Use Sort.attributes for chemistry
```python
sort.attributes = {
    "chemistry": {"c": 4.286, "si": 0.025, "s": 0.011, "p": 0.038, "mn": 0.027},
    "lot_code": "CRT 050N711A"
}
```

**Recommendation:** Option B - keeps Sacks flexible, chemistry in attributes

**Effort:** 0.5 days

### 5. AI Release Parsing

**PrimeTrade Has:**
- PDF text extraction (pypdf)
- Regex patterns for common fields
- Gemini 1.5 Flash for complex parsing
- Special instructions extraction

**Sacks Has:**
- None

**Build Requirements:**
- Port `release_parser.py` to Sacks
- Add Gemini API integration
- Create approval UI for parsed data

**Effort:** 2 days (can reuse PrimeTrade code)

### 6. Client Portal

**PrimeTrade Has:**
- UserCustomerAccess table (not in use)
- Client role with filtered views
- Customer-scoped inventory/releases/BOLs

**Sacks Has:**
- TenantUser with roles
- No customer-level access control

**Build Requirements:**
- Add customer_access to TenantUser or separate model
- Create client-filtered views
- Extend role permissions

**Effort:** 1-2 days

---

## Status Flow Comparison

### Release Status

| PrimeTrade | Sacks | Mapping |
|------------|-------|---------|
| OPEN | pending | ✅ Direct |
| - | allocated | Skip for tonnage |
| - | staged | Skip for tonnage |
| - | verified | Skip for tonnage |
| COMPLETE | shipped | ✅ Direct |
| CANCELLED | (soft delete) | Use is_active=False |

### Load/Line Status

| PrimeTrade (ReleaseLoad) | Sacks (ReleaseLine) | Notes |
|--------------------------|---------------------|-------|
| PENDING | pending | ✅ Direct |
| SHIPPED | verified | Map to verified |
| CANCELLED | (delete) | Soft delete |

**Key Difference:** PrimeTrade loads have `scheduled_date` and `planned_tons`. Sacks lines have `qty_ordered` and FIFO allocation.

---

## Tenant Configuration

Sacks `TenantPolicy` and `TenantConfig` can handle PrimeTrade specifics:

```python
# TenantConfig for Liberty Steel
{
    "bol_format": {
        "prefix": "PRT",
        "reset": "yearly",  # Reset sequence each year
        "digits": 4
    },
    "features": {
        "ai_parsing": true,
        "weight_variance": true,
        "chemistry_tracking": true,
        "client_portal": false  # Not used
    },
    "pdf_template": "pigiron_bol",
    "weight_unit": "tons",
    "chemistry_tolerance": 0.01
}
```

---

## Security Gap Comparison

| Issue | PrimeTrade | Sacks |
|-------|------------|-------|
| Tenant isolation | 18 HIGH bugs | Proper middleware |
| Query filtering | Missing in 18 views | get_tenant_filter() |
| Object creation | Missing tenant assignment | Middleware sets tenant |
| Cross-tenant queries | pending_loads() bug | N/A |

**Verdict:** Sacks architecture is sound. Migration eliminates PrimeTrade security issues.

---

## Migration Complexity by Entity

| Entity | Records | Complexity | Notes |
|--------|---------|------------|-------|
| Tenant | 1 | LOW | Create new tenant |
| Product → Item | 1 | LOW | Map fields |
| Lot → Sort | 2 | LOW | Chemistry in attributes |
| Customer | 7 | LOW | Direct mapping |
| CustomerShipTo → TenantCustomer | 12 | MEDIUM | Merge with customer |
| Carrier | 5 | LOW | Dedupe first |
| Truck | 11 | LOW | Direct mapping |
| Release | 16 | MEDIUM | Status mapping |
| ReleaseLoad → ReleaseLine | 50 | MEDIUM | Add scheduled_date |
| BOL | 28 | HIGH | New model + PDFs |
| AuditLog | 141 | LOW | Import to history |

---

## Build vs Adapt Summary

### Build New (Estimated: 5-7 days)
1. **BOL Model** - 2 days
2. **PDF Generator** - 1 day  
3. **Weight Tracking** - 0.5 days
4. **AI Parser Integration** - 2 days
5. **Client Portal** - 1 day (if needed)

### Adapt Existing (Estimated: 2-3 days)
1. **Release workflow** - Simplify for tonnage
2. **Item/Sort** - Add chemistry to attributes
3. **TenantConfig** - PigIron settings
4. **Views/Templates** - PigIron-specific

### Total Estimated Build: **7-10 days**

---

## Recommended Migration Approach

### Phase 1: Foundation (Week 1)
- Create Liberty Steel tenant with product_type='pigiron'
- Migrate Customer/Carrier/Truck (simple entities)
- Create BOL model with PDF generation

### Phase 2: Inventory (Week 2)  
- Map Product → Item
- Map Lot → Sort with chemistry attributes
- Create pigiron-specific views

### Phase 3: Workflow (Week 3)
- Adapt Release model for tonnage workflow
- Migrate Release/ReleaseLoad data
- Create BOL creation flow

### Phase 4: Data & Cutover (Week 4)
- Migrate historical BOLs
- Parallel operation
- Cutover

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| PDF format differences | MEDIUM | LOW | Template per tenant |
| Weight calculation bugs | LOW | MEDIUM | Unit tests |
| Chemistry validation | LOW | LOW | Keep tolerance configurable |
| Data loss during migration | LOW | HIGH | Backup + parallel operation |
| BOL number collision | LOW | HIGH | Tenant-scoped sequences |

---

## Conclusion

Sacks provides a solid foundation for PrimeTrade migration. The Composable Architecture handles the Universal (shared logistics) + Extension (tenant-specific) pattern well. 

**Primary work items:**
1. Build BOL model with PDF generation
2. Add weight variance tracking
3. Port AI release parser
4. Adapt Release workflow for tonnage (simpler than sacks allocation)

**Why migrate vs fix PrimeTrade:**
- 18 HIGH security bugs in PrimeTrade
- Sacks has proper multi-tenant architecture
- Shared infrastructure (Carrier, Truck, Customer) already exists
- Single codebase for all product types

---

*Document 6 of 6 - Phase 0 Discovery Complete*
