# PrimeTrade Migration Plan

**Generated:** 2026-01-13 (refreshed with live data)
**Purpose:** Phase 0 Discovery - Document 6 of 6
**Prerequisite Docs:** Schema, Screens, Workflows, Data Samples, Sacks Gap Analysis

---

## Executive Summary

Migrate PrimeTrade (pig iron BOL system) from standalone Django app to Sacks Composable Architecture.

**Record Counts (Jan 13, 2026):**
- 36 BOLs, 18 Releases, 56 Release Loads
- 8 Customers, 9 Carriers (some bad data), 16 Trucks
- 1 Product, 2 Lots
- 168 Audit Logs

**Estimated Effort:** 7-10 days implementation after Phase 0

---

## Table Migration Order

Based on foreign key dependencies, migrate in this order:

```
Phase 1: Foundation (No FK dependencies)
  1. Tenant
  2. Product → Item
  3. Customer (universal)
  4. Carrier

Phase 2: Dependent Entities
  5. CustomerShipTo → TenantCustomer
  6. Truck (depends on Carrier)
  7. Lot → Sort (depends on Item/Product)

Phase 3: Transactional Data
  8. Release (depends on Customer, Carrier, Lot)
  9. ReleaseLoad → ReleaseLine (depends on Release)
  10. BOL (depends on Release, ReleaseLoad, Customer, Carrier, Truck, Lot)

Phase 4: System Data
  11. BOLCounter → BOLSequence
  12. AuditLog → django-simple-history
  13. RoleRedirectConfig → TenantConfig
```

---

## Field Mappings

### 1. Tenant

**PrimeTrade:** `bol_system_tenant` (1 row)
**Sacks:** `inventory_tenant`

| PrimeTrade Field | Sacks Field | Transformation |
|------------------|-------------|----------------|
| id | - | New ID in Sacks |
| name | name | Direct: "Liberty Steel" |
| code | code | Direct: "LIBERTY" |
| is_active | is_active | Direct |
| created_at | created_at | PRESERVE ORIGINAL |
| - | product_type | Set: "pigiron" |
| - | config | Set TenantConfig (see below) |

**TenantConfig for Liberty Steel:**
```json
{
  "bol_format": {
    "prefix": "PRT",
    "reset": "yearly",
    "digits": 4
  },
  "features": {
    "ai_parsing": true,
    "weight_variance": true,
    "chemistry_tracking": true
  },
  "weight_unit": "tons",
  "chemistry_tolerance": 0.01
}
```

---

### 2. Product → Item

**PrimeTrade:** `bol_system_product` (1 row)
**Sacks:** `inventory_item`

| PrimeTrade Field | Sacks Field | Transformation |
|------------------|-------------|----------------|
| id | - | New ID |
| tenant_id | tenant_id | Lookup new tenant ID |
| name | name | Direct: "NODULAR PIG IRON" |
| start_tons | - | Store in TenantConfig or separate inventory |
| is_active | is_active | Direct |
| last_lot_code | - | Derived from Sort relationship |
| c, si, s, p, mn | attributes.chemistry | JSON: {"c": 4.286, "si": 0.025, ...} |
| created_at | created_at | PRESERVE ORIGINAL |
| updated_at | updated_at | PRESERVE ORIGINAL |

**Note:** `start_tons` becomes initial inventory record or tenant config value.

---

### 3. Customer (Universal)

**PrimeTrade:** `bol_system_customer` (7 rows)
**Sacks:** `inventory_customer` (universal, not tenant-scoped)

| PrimeTrade Field | Sacks Field | Transformation |
|------------------|-------------|----------------|
| id | - | New ID |
| customer | name | Direct |
| address | - | Moved to TenantCustomer |
| address2 | - | Moved to TenantCustomer |
| city | - | Moved to TenantCustomer |
| state | - | Moved to TenantCustomer |
| zip | - | Moved to TenantCustomer |
| is_active | is_active | Direct |
| logo_url | - | TenantCustomer.config |
| primary_color | - | TenantCustomer.config |
| secondary_color | - | TenantCustomer.config |
| created_at | created_at | PRESERVE ORIGINAL |

**Data Quality Fix:** ST. MARYS has malformed address - fix during migration:
```
Before: address="", city="405-409 E. South St. Saint Marys"
After:  address="405-409 E. South St.", city="Saint Marys"
```

---

### 4. Carrier

**PrimeTrade:** `bol_system_carrier` (5 rows, 1 duplicate)
**Sacks:** `inventory_carrier`

| PrimeTrade Field | Sacks Field | Transformation |
|------------------|-------------|----------------|
| id | - | New ID |
| tenant_id | tenant_id | Lookup new tenant ID |
| carrier_name | name | Direct |
| contact_name | contact_name | Direct |
| phone | phone | Direct |
| email | email | Direct |
| is_active | is_active | Direct |
| created_at | created_at | PRESERVE ORIGINAL |

**Data Quality Fix:** Merge duplicate carriers:
```
DELETE: id=13, "R & J Trucking" (inactive, 0 trucks)
KEEP:   id=14, "R&J Trucking" (active, 2 trucks)
```

---

### 5. CustomerShipTo → TenantCustomer

**PrimeTrade:** `bol_system_customershipto` (12 rows)
**Sacks:** `inventory_tenantcustomer`

| PrimeTrade Field | Sacks Field | Transformation |
|------------------|-------------|----------------|
| id | - | New ID |
| tenant_id | tenant_id | Lookup new tenant ID |
| customer_id | customer_id | Lookup new universal customer ID |
| name | display_name | Direct |
| street | address_line1 | Direct |
| street2 | address_line2 | Direct |
| city | city | Direct |
| state | state | Direct |
| zip | postal_code | Direct |
| is_active | is_active | Direct |
| created_at | created_at | PRESERVE ORIGINAL |

**Note:** Also create TenantCustomer for each Customer (headquarters address).

---

### 6. Truck

**PrimeTrade:** `bol_system_truck` (11 rows)
**Sacks:** `inventory_truck`

| PrimeTrade Field | Sacks Field | Transformation |
|------------------|-------------|----------------|
| id | - | New ID |
| carrier_id | carrier_id | Lookup new carrier ID |
| truck_number | truck_number | Direct |
| trailer_number | trailer_number | Direct |
| is_active | is_active | Direct |
| created_at | created_at | PRESERVE ORIGINAL |

---

### 7. Lot → Sort

**PrimeTrade:** `bol_system_lot` (2 rows)
**Sacks:** `inventory_sort`

| PrimeTrade Field | Sacks Field | Transformation |
|------------------|-------------|----------------|
| id | - | New ID |
| tenant_id | tenant_id | Lookup new tenant ID |
| code | code | Direct: "CRT 050N711A" |
| product_id | item_id | Lookup new item ID |
| c | attributes.chemistry.c | JSON nested |
| si | attributes.chemistry.si | JSON nested |
| s | attributes.chemistry.s | JSON nested |
| p | attributes.chemistry.p | JSON nested |
| mn | attributes.chemistry.mn | JSON nested |
| created_at | created_at | PRESERVE ORIGINAL |

**Example Sort.attributes:**
```json
{
  "chemistry": {
    "c": 4.286,
    "si": 0.025,
    "s": 0.011,
    "p": 0.038,
    "mn": 0.027
  },
  "lot_code": "CRT 050N711A"
}
```

---

### 8. Release

**PrimeTrade:** `bol_system_release` (16 rows)
**Sacks:** `inventory_release` (extended for pigiron)

| PrimeTrade Field | Sacks Field | Transformation |
|------------------|-------------|----------------|
| id | - | New ID |
| tenant_id | tenant_id | Lookup |
| release_number | release_number | Direct |
| release_date | release_date | Direct |
| status | status | Map: OPEN→pending, COMPLETE→shipped, CANCELLED→cancelled |
| customer_id_text | - | Denormalized, use customer_ref |
| customer_po | customer_po | Direct |
| ship_via | ship_via | Direct |
| fob | fob | Direct |
| ship_to_name | - | Use ship_to_ref |
| ship_to_street | - | Use ship_to_ref |
| ship_to_street2 | - | Use ship_to_ref |
| ship_to_city | - | Use ship_to_ref |
| ship_to_state | - | Use ship_to_ref |
| ship_to_zip | - | Use ship_to_ref |
| lot | - | Use lot_ref |
| material_description | - | Use item relationship |
| quantity_net_tons | quantity_ordered | Direct |
| special_instructions | special_instructions | Direct |
| care_of_co | care_of_co | Direct |
| customer_ref_id | customer_id | Lookup new customer ID |
| ship_to_ref_id | ship_to_id | Lookup new TenantCustomer ID |
| carrier_ref_id | carrier_id | Lookup new carrier ID |
| lot_ref_id | sort_id | Lookup new sort ID |
| created_at | created_at | PRESERVE ORIGINAL |

**Status Mapping:**
| PrimeTrade | Sacks | Notes |
|------------|-------|-------|
| OPEN | pending | Active release |
| COMPLETE | shipped | All loads shipped |
| CANCELLED | cancelled | Add is_active=False |

---

### 9. ReleaseLoad → ReleaseLine

**PrimeTrade:** `bol_system_releaseload` (50 rows)
**Sacks:** `inventory_releaseline` (extended for pigiron)

| PrimeTrade Field | Sacks Field | Transformation |
|------------------|-------------|----------------|
| id | - | New ID |
| tenant_id | tenant_id | Lookup |
| release_id | release_id | Lookup new release ID |
| seq | line_number | Direct |
| date | scheduled_date | Direct (NEW FIELD) |
| planned_tons | qty_ordered | Direct |
| status | status | Map: PENDING→pending, SHIPPED→verified, CANCELLED→cancelled |
| shipped_at | shipped_at | Direct (NEW FIELD) |
| bol_id | - | Legacy, use BOL.release_line_id |
| created_at | created_at | PRESERVE ORIGINAL |

**Status Mapping:**
| PrimeTrade | Sacks | Notes |
|------------|-------|-------|
| PENDING | pending | Awaiting shipment |
| SHIPPED | verified | BOL created |
| CANCELLED | cancelled | Soft delete |

**New Fields Required in Sacks ReleaseLine:**
- `scheduled_date` (DateField, null=True)
- `shipped_at` (DateTimeField, null=True)

---

### 10. BOL (NEW MODEL IN SACKS)

**PrimeTrade:** `bol_system_bol` (28 rows)
**Sacks:** `inventory_bol` (NEW - must create)

| PrimeTrade Field | Sacks Field | Notes |
|------------------|-------------|-------|
| id | - | New ID |
| tenant_id | tenant_id | Lookup |
| bol_number | bol_number | Direct: "PRT-2025-0031" |
| bol_date | bol_date | Direct |
| date | - | Legacy string, use bol_date |
| is_void | is_void | Direct |
| voided_at | voided_at | Direct |
| voided_by | voided_by | Direct |
| void_reason | void_reason | Direct |
| issued_by | issued_by | Direct |
| release_line_id | release_line_id | Lookup new ReleaseLine ID |
| lot_id | sort_id | Lookup new Sort ID |
| product_id | item_id | Lookup new Item ID |
| customer_id | customer_id | Lookup new Customer ID |
| carrier_id | carrier_id | Lookup new Carrier ID |
| truck_id | truck_id | Lookup new Truck ID |
| release_display | release_display | Direct: "60271-1" |
| product_name | product_name | Direct (snapshot) |
| buyer_name | buyer_name | Direct (snapshot) |
| carrier_name | carrier_name | Direct (snapshot) |
| truck_number | truck_number | Direct (snapshot) |
| trailer_number | trailer_number | Direct (snapshot) |
| chemistry_display | chemistry_display | Direct (snapshot) |
| ship_to | ship_to | Direct (snapshot, TEXT) |
| customer_po | customer_po | Direct (snapshot) |
| special_instructions | special_instructions | Direct |
| care_of_co | care_of_co | Direct |
| net_tons | net_tons | Direct |
| official_weight_tons | official_weight_tons | Direct |
| official_weight_entered_by | official_weight_entered_by | Direct |
| official_weight_entered_at | official_weight_entered_at | Direct |
| weight_variance_tons | weight_variance_tons | Direct |
| weight_variance_percent | weight_variance_percent | Direct |
| pdf_url | pdf_url | Direct (S3 URL) |
| pdf_key | pdf_key | Direct (S3 key) |
| stamped_pdf_url | stamped_pdf_url | Direct |
| notes | notes | Direct |
| created_by_email | created_by_email | Direct |
| release_number | release_number | Direct (legacy ref) |
| created_at | created_at | PRESERVE ORIGINAL |
| updated_at | updated_at | PRESERVE ORIGINAL |

---

### 11. BOLCounter → BOLSequence

**PrimeTrade:** `bol_system_bolcounter` (2 rows)
**Sacks:** `inventory_bolsequence`

| PrimeTrade Field | Sacks Field | Transformation |
|------------------|-------------|----------------|
| id | - | New ID |
| tenant_id | tenant_id | Set to Liberty tenant (currently NULL!) |
| year | year | Direct |
| sequence | sequence | Direct |

**Current Values:**
- 2025: sequence=31
- 2026: sequence=18

**Fix:** Assign tenant_id during migration (was NULL in PrimeTrade).

---

### 12. AuditLog → django-simple-history

**PrimeTrade:** `bol_system_auditlog` (141 rows)
**Sacks:** Uses django-simple-history (automatic)

**Strategy:** Import as historical records or archive table.

| PrimeTrade Field | Sacks Approach |
|------------------|----------------|
| action | Map to history_type |
| object_type | history_table name |
| object_id | history_id |
| message | - (reconstruct from diff) |
| user_email | history_user |
| created_at | history_date |
| extra | - (JSON archived) |

**Option A:** Create `audit_archive` table for legacy logs
**Option B:** Skip migration, keep for reference only

**Recommendation:** Option A - preserve compliance trail

---

## ID Mapping Tables

During migration, maintain lookup tables:

```sql
-- primetrade_migration_map
CREATE TABLE migration_map (
    entity_type VARCHAR(50),
    old_id BIGINT,
    new_id BIGINT,
    PRIMARY KEY (entity_type, old_id)
);

-- Example entries:
-- ('tenant', 1, 42)
-- ('customer', 18, 100)
-- ('carrier', 11, 200)
-- ('release', 41, 500)
```

---

## Migration Script Order

```python
# migration_primetrade.py

def migrate():
    # Phase 1: Foundation
    tenant_map = migrate_tenant()          # 1 record
    item_map = migrate_products(tenant_map)  # 1 record
    customer_map = migrate_customers()       # 7 records (universal)
    carrier_map = migrate_carriers(tenant_map)  # 4 records (dedupe)

    # Phase 2: Dependent
    tenant_customer_map = migrate_ship_tos(tenant_map, customer_map)  # 12 records
    truck_map = migrate_trucks(carrier_map)  # 11 records
    sort_map = migrate_lots(tenant_map, item_map)  # 2 records

    # Phase 3: Transactional
    release_map = migrate_releases(
        tenant_map, customer_map, carrier_map,
        tenant_customer_map, sort_map
    )  # 16 records

    release_line_map = migrate_release_loads(
        tenant_map, release_map
    )  # 50 records

    bol_map = migrate_bols(
        tenant_map, release_line_map, sort_map,
        item_map, customer_map, carrier_map, truck_map
    )  # 28 records

    # Phase 4: System
    migrate_bol_counters(tenant_map)  # 2 records
    archive_audit_logs()  # 141 records

    return {
        'tenant': tenant_map,
        'item': item_map,
        'customer': customer_map,
        'carrier': carrier_map,
        'tenant_customer': tenant_customer_map,
        'truck': truck_map,
        'sort': sort_map,
        'release': release_map,
        'release_line': release_line_map,
        'bol': bol_map
    }
```

---

## Pre-Migration Checklist

### Sacks Model Changes Required

- [ ] Create `inventory_bol` model (30+ fields)
- [ ] Add `scheduled_date` to ReleaseLine
- [ ] Add `shipped_at` to ReleaseLine
- [ ] Add `chemistry` to Sort.attributes schema
- [ ] Add `care_of_co` to Release model
- [ ] Create PDF generator for pigiron BOLs
- [ ] Create weight variance calculation logic

### Data Quality Fixes

- [ ] Fix ST. MARYS address (street in city field)
- [ ] Merge duplicate carriers (R & J → R&J)
- [ ] Assign tenant_id to BOLCounters
- [ ] Normalize lot codes (optional)

### Template Changes

- [ ] Create pigiron dashboard template
- [ ] Create pigiron release list template
- [ ] Create pigiron BOL list template
- [ ] Create pigiron BOL create form
- [ ] Create pigiron weight entry form
- [ ] Create pigiron inventory report

---

## Rollback Plan

### Before Migration
1. Full database backup of Sacks production
2. Full database backup of PrimeTrade production
3. Document current BOL sequence numbers
4. Export all PDF URLs for verification

### Rollback Triggers
- Data integrity errors (FK violations)
- BOL number collisions
- PDF access failures
- >5% weight variance discrepancies

### Rollback Steps
1. Stop Sacks application
2. Restore Sacks database from backup
3. Verify PrimeTrade still operational
4. Document failure reason
5. Fix issues before retry

### Point of No Return
After 7 days of parallel operation with no issues, PrimeTrade can be decommissioned.

---

## Testing Plan

### Unit Tests
- [ ] Tenant creation with pigiron config
- [ ] Customer/Carrier/Truck CRUD
- [ ] Release creation and status transitions
- [ ] BOL creation with PDF generation
- [ ] Weight variance calculation
- [ ] Chemistry validation

### Integration Tests
- [ ] Full release → load → BOL workflow
- [ ] PDF generation and S3 upload
- [ ] BOL number sequence (no gaps, no collisions)
- [ ] Official weight entry + stamped PDF

### Data Validation
- [ ] Record counts match source
- [ ] All FKs resolve correctly
- [ ] Chemistry values preserved
- [ ] Timestamps preserved
- [ ] PDF URLs accessible

### UAT Checklist
- [ ] Create new release (AI parser)
- [ ] Create BOL from release load
- [ ] Enter official weight
- [ ] View inventory report
- [ ] Client portal access (if enabled)

---

## Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | Foundation | Tenant, Item, Customer, Carrier models + migration |
| 2 | Dependent | TenantCustomer, Truck, Sort models + migration |
| 3 | Transactional | Release, ReleaseLine, BOL models + migration |
| 4 | Polish | Templates, testing, parallel operation |
| 5 | Cutover | Go-live, monitoring, PrimeTrade sunset |

---

## Success Criteria

Phase 0 Complete When:
- [x] All 6 discovery documents exist
- [x] Every table mapped to Sacks equivalent
- [x] Field mappings documented
- [x] Status values have explicit mapping
- [x] Migration order defined
- [x] Rollback plan documented

Migration Complete When:
- [ ] All records migrated with preserved timestamps
- [ ] Zero BOL number collisions
- [ ] All PDFs accessible via new URLs
- [ ] Weight calculations match source
- [ ] 7 days parallel operation successful
- [ ] PrimeTrade decommissioned

---

*Document 6 of 6 - Phase 0 Discovery COMPLETE*
