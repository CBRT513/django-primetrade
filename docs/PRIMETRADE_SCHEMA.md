# PrimeTrade Database Schema

**Generated:** 2026-01-13 (refreshed)
**Source:** prt.barge2rail.com (Neon PostgreSQL)
**Purpose:** Phase 0 Discovery - Document 1 of 6

---

## Database Overview

| Category | Tables | Description |
|----------|--------|-------------|
| Core Business | 7 | BOL, Release, ReleaseLoad, Customer, Carrier, Truck, Lot |
| Supporting | 4 | Tenant, Product, CustomerShipTo, BOLCounter |
| System | 4 | AuditLog, UserCustomerAccess, CompanyBranding, RoleRedirectConfig |
| Django/Auth | 11 | Standard Django tables |
| **Total** | **26** | |

---

## Table Row Counts

| Table | Row Count | Notes |
|-------|-----------|-------|
| bol_system_bol | 36 | Main BOL records |
| bol_system_release | 18 | Release orders |
| bol_system_releaseload | 56 | Release line items |
| bol_system_customer | 8 | Customer records |
| bol_system_carrier | 9 | Carrier records (duplicates + bad data) |
| bol_system_truck | 16 | Truck/trailer combinations |
| bol_system_customershipto | 9 | Ship-to addresses |
| bol_system_lot | 2 | Chemistry lots |
| bol_system_product | 1 | Single product (Nodular Pig Iron) |
| bol_system_tenant | 1 | Single tenant (Liberty Steel) |
| bol_system_bolcounter | 2 | Year-based sequence (2025, 2026) |
| bol_system_auditlog | 168 | Audit trail |
| bol_system_usercustomeraccess | 0 | Empty |
| bol_system_companybranding | 0 | Empty |
| bol_system_roleredirectconfig | 4 | Role routing |

---

## Core Business Tables

### bol_system_bol (36 rows) - Main BOL Table

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | bigint | NOT NULL | PK, auto-generated |
| created_at | timestamp | NOT NULL | |
| updated_at | timestamp | NOT NULL | |
| updated_by | varchar(200) | NOT NULL | |
| **bol_number** | varchar(20) | NOT NULL | Format: PRT-YYYY-NNNN |
| product_name | varchar(200) | NOT NULL | Always "NODULAR PIG IRON" |
| buyer_name | varchar(200) | NOT NULL | Customer short name |
| ship_to | text | NOT NULL | Full address text |
| customer_po | varchar(100) | NOT NULL | |
| carrier_name | varchar(200) | NOT NULL | Denormalized |
| truck_number | varchar(50) | NOT NULL | |
| trailer_number | varchar(50) | NOT NULL | |
| date | varchar(20) | NOT NULL | Legacy string date |
| bol_date | date | NULL | Proper date field |
| **net_tons** | numeric(10,2) | NOT NULL | Estimated weight |
| notes | text | NOT NULL | |
| special_instructions | text | NOT NULL | |
| pdf_url | varchar(1000) | NOT NULL | Generated PDF |
| stamped_pdf_url | varchar(1000) | NOT NULL | Official stamped PDF |
| pdf_key | varchar(500) | NULL | S3 key |
| created_by_email | varchar(200) | NOT NULL | |
| **is_void** | boolean | NOT NULL | Soft delete flag |
| void_reason | text | NOT NULL | |
| voided_at | timestamp | NULL | |
| voided_by | varchar(200) | NOT NULL | |
| **official_weight_tons** | numeric(10,2) | NULL | Actual weight |
| official_weight_entered_at | timestamp | NULL | |
| official_weight_entered_by | varchar(200) | NOT NULL | |
| weight_variance_tons | numeric(10,2) | NULL | Calculated |
| weight_variance_percent | numeric(6,2) | NULL | Calculated |
| release_number | varchar(20) | NOT NULL | Denormalized |
| release_display | varchar(30) | NOT NULL | Display text |
| chemistry_display | varchar(200) | NOT NULL | Formatted chemistry |
| care_of_co | varchar(200) | NOT NULL | C/O line |
| issued_by | varchar(200) | NOT NULL | |
| carrier_id | bigint | NOT NULL | FK → Carrier |
| customer_id | bigint | NULL | FK → Customer |
| product_id | bigint | NOT NULL | FK → Product |
| truck_id | bigint | NULL | FK → Truck |
| lot_id | bigint | NULL | FK → Lot |
| lot_ref_id | bigint | NULL | FK → Lot (legacy) |
| release_line_id | bigint | NULL | FK → ReleaseLoad |
| tenant_id | bigint | NULL | FK → Tenant |

**Unique Constraints:**
- `(tenant_id, bol_number)` - BOL number unique per tenant
- `release_line_id WHERE NOT is_void` - Only one active BOL per release line

**Sample Data (Latest):**
```
PRT-2026-0026 | NODULAR PIG IRON | ST. MARYS | 22.48 tons (Jan 13)
PRT-2026-0025 | NODULAR PIG IRON | LIBERTY   | 23.xx tons
PRT-2026-0024 | NODULAR PIG IRON | ST. MARYS | 23.xx tons
```

---

### bol_system_release (18 rows) - Release Orders

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | bigint | NOT NULL | PK |
| created_at | timestamp | NOT NULL | |
| updated_at | timestamp | NOT NULL | |
| updated_by | varchar(200) | NOT NULL | |
| **release_number** | varchar(20) | NOT NULL | e.g., "60298" |
| release_date | date | NULL | |
| customer_id_text | varchar(200) | NOT NULL | Customer name text |
| customer_po | varchar(100) | NOT NULL | |
| ship_via | varchar(200) | NOT NULL | |
| fob | varchar(200) | NOT NULL | |
| ship_to_name | varchar(200) | NOT NULL | |
| ship_to_street | varchar(200) | NOT NULL | |
| ship_to_street2 | varchar(200) | NOT NULL | |
| ship_to_city | varchar(100) | NOT NULL | |
| ship_to_state | varchar(2) | NOT NULL | |
| ship_to_zip | varchar(10) | NOT NULL | |
| lot | varchar(100) | NOT NULL | Lot code text |
| material_description | varchar(200) | NOT NULL | |
| **quantity_net_tons** | numeric(10,2) | NULL | Total ordered |
| **status** | varchar(12) | NOT NULL | OPEN/COMPLETE/CANCELLED |
| special_instructions | text | NOT NULL | |
| care_of_co | varchar(200) | NOT NULL | |
| carrier_ref_id | bigint | NULL | FK → Carrier |
| customer_ref_id | bigint | NULL | FK → Customer |
| lot_ref_id | bigint | NULL | FK → Lot |
| ship_to_ref_id | bigint | NULL | FK → CustomerShipTo |
| tenant_id | bigint | NULL | FK → Tenant |

**Status Values:**
| Status | Count | Meaning |
|--------|-------|---------|
| OPEN | 6 | In progress, loads remaining |
| COMPLETE | 10 | All loads shipped |
| CANCELLED | 2 | Order cancelled |

**Latest Release:** #60381 (ELYRIA, 115 tons)

---

### bol_system_releaseload (56 rows) - Release Line Items

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | bigint | NOT NULL | PK |
| created_at | timestamp | NOT NULL | |
| updated_at | timestamp | NOT NULL | |
| updated_by | varchar(200) | NOT NULL | |
| **seq** | integer | NOT NULL | Line sequence (1, 2, 3...) |
| date | date | NULL | Planned ship date |
| **planned_tons** | numeric(10,3) | NULL | Per-load planned weight |
| **status** | varchar(12) | NOT NULL | PENDING/SHIPPED/CANCELLED |
| shipped_at | timestamp | NULL | When shipped |
| bol_id | bigint | NULL | FK → BOL (when shipped) |
| release_id | bigint | NOT NULL | FK → Release |
| tenant_id | bigint | NULL | FK → Tenant |

**Status Values:**
| Status | Count | Meaning |
|--------|-------|---------|
| PENDING | 16 | Not yet shipped |
| SHIPPED | 36 | BOL created |
| CANCELLED | 4 | Line cancelled |

**Unique Constraint:** `(release_id, seq)` - Sequence unique per release

---

## Supporting Tables

### bol_system_customer (8 rows)

| Column | Type | Notes |
|--------|------|-------|
| id | bigint | PK |
| customer | varchar(200) | **UNIQUE** - Customer name |
| address, address2, city, state, zip | varchar | Address fields |
| is_active | boolean | |
| logo_url | varchar(500) | Customer logo |
| primary_color, secondary_color | varchar(7) | Branding colors |
| tenant_id | bigint | FK → Tenant |

**Current Customers (8):**
- ELYRIA (new)
- HW-ST. MARYS (St. Marys, OH)
- INTAT (Rushville, IN)
- LIBERTY (Delaware, OH)
- LIBERTY TECH (Delaware, OH)
- MINSTER (Minster, OH)
- ST. MARYS (Saint Marys, OH)
- Xenia Foundry & Machine Co (Xenia, OH)

---

### bol_system_carrier (9 rows)

| Column | Type | Notes |
|--------|------|-------|
| id | bigint | PK |
| carrier_name | varchar(200) | **UNIQUE** |
| contact_name, phone, email | varchar | Contact info |
| is_active | boolean | |
| tenant_id | bigint | FK → Tenant |

**Current Carriers (9 - includes bad data):**
- Brown Transport (active)
- Piper Trucking (active)
- R & J Trucking ⚠️ (inactive - duplicate)
- R&J Trucking (active)
- CUSTOMER PU (inactive)
- FOBRelease #... ⚠️ (parsing error - bad data)
- (+ others)

---

### bol_system_truck (16 rows)

| Column | Type | Notes |
|--------|------|-------|
| id | bigint | PK |
| truck_number | varchar(50) | |
| trailer_number | varchar(50) | |
| is_active | boolean | |
| carrier_id | bigint | FK → Carrier |

**Unique Constraint:** `(carrier_id, truck_number)`

---

### bol_system_lot (2 rows) - Chemistry Lots

| Column | Type | Notes |
|--------|------|-------|
| id | bigint | PK |
| code | varchar(100) | Lot identifier |
| c | numeric(6,3) | Carbon % |
| si | numeric(6,3) | Silicon % |
| s | numeric(6,3) | Sulfur % |
| p | numeric(6,3) | Phosphorus % |
| mn | numeric(6,3) | Manganese % |
| product_id | bigint | FK → Product |
| tenant_id | bigint | FK → Tenant |

**Current Lots:**
| Code | C | Si | S | P | Mn |
|------|---|---|---|---|---|
| 050N711A | 4.286 | 0.025 | 0.011 | 0.038 | 0.027 |
| CRT 050N711A | 4.286 | 0.025 | 0.011 | 0.038 | 0.027 |

---

### bol_system_product (1 row)

| Column | Type | Notes |
|--------|------|-------|
| id | bigint | PK |
| name | varchar(200) | **UNIQUE** - "NODULAR PIG IRON" |
| start_tons | numeric(10,2) | Starting inventory: 3129.72 |
| last_lot_code | varchar(100) | |
| c, si, s, p, mn | numeric(6,3) | Default chemistry |
| is_active | boolean | |
| tenant_id | bigint | FK → Tenant |

---

### bol_system_customershipto (9 rows)

| Column | Type | Notes |
|--------|------|-------|
| id | bigint | PK |
| name | varchar(200) | Ship-to name |
| street, street2, city, state, zip | varchar | Address |
| is_active | boolean | |
| customer_id | bigint | FK → Customer |
| tenant_id | bigint | FK → Tenant |

**Unique Constraint:** `(customer_id, street, city, state, zip)`

---

### bol_system_tenant (1 row)

| Column | Type | Notes |
|--------|------|-------|
| id | bigint | PK |
| name | varchar(100) | "Liberty Steel" |
| code | varchar(20) | **UNIQUE** - "LIBERTY" |
| is_active | boolean | |
| created_at | timestamp | |

---

### bol_system_bolcounter (2 rows) - BOL Number Sequence

| Column | Type | Notes |
|--------|------|-------|
| id | bigint | PK |
| year | integer | Calendar year |
| sequence | integer | Next BOL number |
| tenant_id | bigint | FK → Tenant (NULL!) |

**Current Values:**
| Year | Sequence | Notes |
|------|----------|-------|
| 2025 | 31 | 31 BOLs in 2025 |
| 2026 | 26 | 26 BOLs in 2026 so far |

⚠️ **Note:** tenant_id is NULL - counter is global, not per-tenant

---

## System Tables

### bol_system_auditlog (168 rows)

| Column | Type | Notes |
|--------|------|-------|
| id | bigint | PK |
| action | varchar(64) | Action type |
| object_type | varchar(64) | Entity type |
| object_id | varchar(64) | Entity ID |
| message | text | Description |
| user_email | varchar(200) | Who |
| ip | varchar(45) | Client IP |
| method | varchar(10) | HTTP method |
| path | varchar(300) | URL path |
| user_agent | varchar(300) | Browser |
| **extra** | jsonb | Additional data |
| tenant_id | bigint | FK → Tenant |

---

### bol_system_usercustomeraccess (0 rows)

Controls which users can access which customers.

| Column | Type | Notes |
|--------|------|-------|
| user_email | varchar(254) | |
| is_primary | boolean | |
| access_level | varchar(20) | |
| customer_id | bigint | FK → Customer |
| tenant_id | bigint | FK → Tenant |

---

### bol_system_roleredirectconfig (4 rows)

Role-based landing page routing.

| Column | Type | Notes |
|--------|------|-------|
| role_name | varchar(20) | **UNIQUE** |
| landing_page | varchar(200) | URL to redirect to |
| is_active | boolean | |

---

## Entity Relationship Diagram

```
Tenant
  │
  ├─→ Customer ──→ CustomerShipTo
  │      │
  │      └─→ UserCustomerAccess
  │
  ├─→ Carrier ──→ Truck
  │
  ├─→ Product ──→ Lot
  │
  ├─→ Release ──→ ReleaseLoad ──→ BOL
  │      │            │
  │      └────────────┴─→ (customer_ref, carrier_ref, lot_ref, ship_to_ref)
  │
  └─→ BOLCounter (sequence per year)
```

---

## Status/Enum Mapping

### Release Status
| Status | Count | Meaning | Transitions To |
|--------|-------|---------|----------------|
| OPEN | 6 | Active, loads remaining | COMPLETE, CANCELLED |
| COMPLETE | 10 | All loads shipped | - |
| CANCELLED | 2 | Order cancelled | - |

### ReleaseLoad Status
| Status | Count | Meaning | Transitions To |
|--------|-------|---------|----------------|
| PENDING | 16 | Scheduled, not yet shipped | SHIPPED, CANCELLED |
| SHIPPED | 36 | BOL created and linked | - |
| CANCELLED | 4 | Load cancelled | - |

### BOL Status (Implicit via is_void)
| is_void | Meaning |
|---------|---------|
| false | Active BOL |
| true | Voided (soft deleted) |

### Product/Customer/Carrier Status
| is_active | Meaning |
|-----------|---------|
| true | Available for selection in forms |
| false | Hidden from dropdowns, data preserved |

### Workflow State Machine

```
Release: OPEN ──────┬──→ COMPLETE (all loads shipped)
                    └──→ CANCELLED

ReleaseLoad: PENDING ──┬──→ SHIPPED (BOL created)
                       └──→ CANCELLED

BOL: (created) ──→ is_void=true (voided)
```

---

## Known Security Issues

**Audit Date:** 2026-01-05  
**Audit File:** `~/Desktop/prt-tenant-audit.md`

| Risk | Count | Summary |
|------|-------|---------|
| HIGH | 18 | Cross-tenant data exposure in queries |
| MEDIUM | 5 | Missing tenant filters |
| LOW | 2 | Minor isolation gaps |

**Critical Functions:**
- `approve_release` - Creates Release, ReleaseLoad, Lot, Product without tenant
- `pending_loads` - Returns ALL tenants' pending loads
- `create_bol` - Creates BOL without tenant
- `customer_branding` - Fetches any tenant's customer by ID/name

**Mitigation:** Single tenant (Liberty Steel) currently exists. No new tenants until migration complete.

**Resolution:** Migration to Sacks (properly architected multi-tenant).

---

## Key Observations

1. **Single Tenant System**: Only "Liberty Steel" tenant exists
2. **Single Product**: Only "NODULAR PIG IRON" product
3. **Chemistry Tracking**: Lots track C, Si, S, P, Mn percentages
4. **Denormalized Data**: BOL stores carrier_name, buyer_name, etc. as text
5. **Dual Weight Tracking**: net_tons (estimated) vs official_weight_tons (actual)
6. **Void Pattern**: is_void flag for soft delete with audit trail
7. **Release-Load-BOL Workflow**: Release → ReleaseLoad lines → BOL per line
8. **Data Quality Issue**: Duplicate carrier (R & J vs R&J)
9. **BOL Number Format**: PRT-YYYY-NNNN (e.g., PRT-2025-0031)
10. **Global BOL Counter**: Not tenant-scoped (potential issue for multi-tenant)

---

## Migration Considerations

1. **Tenant Model**: Map to Sacks tenant/supplier system
2. **Chemistry Fields**: Sacks needs equivalent Lot model with chemistry
3. **Release-Load Pattern**: Similar to Sacks staged load concept
4. **Weight Variance Tracking**: Unique to PrimeTrade
5. **PDF Generation**: Both draft and stamped versions
6. **Audit Log**: Has JSONB extra field for flexible data
7. **Sequence Generator**: Year-based counter needs mapping

---

*Document 1 of 6 - Phase 0 Discovery Complete*
