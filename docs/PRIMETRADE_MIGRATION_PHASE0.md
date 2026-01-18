# PrimeTrade Migration - Phase 0 Discovery Plan

**Purpose:** Complete documentation of PrimeTrade before writing any migration code.  
**Lesson Learned:** Yifan migration required 10+ hours of patching because we skipped discovery.  
**Goal:** Zero surprises during PrimeTrade migration.

---

## Step 1: Database Schema Discovery (1 hour)

### 1.1 Connect to PrimeTrade Database
```bash
# Get connection string from Render dashboard for prt.barge2rail.com
psql "postgresql://[connection_string]"
```

### 1.2 Map Every Table
```sql
-- List all tables
\dt

-- For EACH table, document:
\d table_name

-- Get row counts
SELECT 
    schemaname,
    relname as table_name,
    n_live_tup as row_count
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC;
```

### 1.3 Create Schema Document
For each table, document:
- Table name
- Row count
- Column names and types
- Foreign key relationships
- Any JSONB fields and their structure
- Status/enum values used

**Output:** `PRIMETRADE_SCHEMA.md` with complete table mapping

---

## Step 2: UI Screen Documentation (2 hours)

### 2.1 Screenshot Every Screen
Login to prt.barge2rail.com and capture:

| Screen | URL Pattern | Screenshot |
|--------|-------------|------------|
| Dashboard | /dashboard | |
| BOL List | /bols | |
| BOL Detail | /bols/{id} | |
| BOL Create | /bols/new | |
| Customer List | /customers | |
| Customer Detail | /customers/{id} | |
| Carrier List | /carriers | |
| Truck List | /trucks | |
| Reports (if any) | /reports | |
| Admin | /admin | |

### 2.2 Document Each Screen
For every screen, record:
- **Columns displayed** (exact order, names)
- **Status badges** (exact text, colors)
- **Action buttons** (labels, positions)
- **Filters/dropdowns** (options available)
- **Summary cards** (metrics shown)
- **Sort order** (default sorting)

**Output:** `PRIMETRADE_SCREENS.md` with annotated screenshots

---

## Step 3: Status/Enum Mapping (30 min)

### 3.1 Document All Status Values
```sql
-- Find all status columns and their values
SELECT DISTINCT status FROM bols;
SELECT DISTINCT status FROM shipments;
-- etc for each table with status
```

### 3.2 Create Status Mapping Table

| Entity | PrimeTrade Status | Meaning | Sacks Equivalent |
|--------|-------------------|---------|------------------|
| BOL | draft | Not finalized | ? |
| BOL | complete | Finalized | ? |
| ... | ... | ... | ... |

**Output:** Status mapping section in schema doc

---

## Step 4: Business Logic Documentation (1 hour)

### 4.1 Workflow Documentation
Document the PrimeTrade workflow step-by-step:
1. How is a BOL created?
2. What triggers status changes?
3. How are coils/items assigned?
4. What calculations are performed (weights, counts)?
5. What generates BOL numbers?

### 4.2 Field Calculation Logic
Document any calculated fields:
- Total weight calculation
- Coil count logic
- Pricing calculations (if any)
- Date handling

### 4.3 Validation Rules
- Required fields
- Field constraints
- Business rules enforced

**Output:** `PRIMETRADE_WORKFLOWS.md`

---

## Step 5: Data Sample Extraction (30 min)

### 5.1 Export Sample Records
```sql
-- Sample BOLs with all fields
SELECT * FROM bols ORDER BY created_at DESC LIMIT 10;

-- Sample customers
SELECT * FROM customers LIMIT 10;

-- Sample line items
SELECT * FROM bol_line_items LIMIT 20;
```

### 5.2 Document Edge Cases
- BOLs with unusual data
- Null values in important fields
- Any data quality issues

**Output:** `PRIMETRADE_DATA_SAMPLES.md`

---

## Step 6: Sacks Gap Analysis (1 hour)

### 6.1 Compare to Sacks Models
For each PrimeTrade table, identify:
- Does equivalent sacks model exist?
- Field name differences
- Missing fields in sacks
- Extra fields in sacks

### 6.2 Template Requirements
Based on screenshots, document:
- Which sacks templates need modification
- New templates needed
- Column additions required
- Status badge changes

### 6.3 View Logic Changes
- Sorting differences
- Filter differences
- Calculation differences

**Output:** `PRIMETRADE_SACKS_GAP.md`

---

## Step 7: Migration Plan Creation (1 hour)

### 7.1 Table Migration Order
Based on foreign keys, determine order:
```
1. Customers (no dependencies)
2. Carriers (no dependencies)
3. Trucks (depends on Carriers)
4. BOLs (depends on Customers, Carriers)
5. BOL Line Items (depends on BOLs)
6. etc.
```

### 7.2 Field Mapping Document
For each table:
```
PrimeTrade.bols -> Sacks.inventory_bol
  - bol_number -> bol_number
  - customer_id -> tenant_customer_id (lookup required)
  - status -> status (mapped: 'complete' -> 'complete')
  - created_at -> created_at (PRESERVE ORIGINAL)
```

### 7.3 Template Modification List
Ordered list of template changes needed BEFORE migration:
1. Add X column to BOL list
2. Change status badge colors
3. etc.

**Output:** `PRIMETRADE_MIGRATION_PLAN.md`

---

## Deliverables Checklist

Before writing ANY migration code, these files must exist:

- [ ] `PRIMETRADE_SCHEMA.md` - Complete database schema
- [ ] `PRIMETRADE_SCREENS.md` - Annotated screenshots
- [ ] `PRIMETRADE_WORKFLOWS.md` - Business logic documentation
- [ ] `PRIMETRADE_DATA_SAMPLES.md` - Sample data with edge cases
- [ ] `PRIMETRADE_SACKS_GAP.md` - Gap analysis
- [ ] `PRIMETRADE_MIGRATION_PLAN.md` - Ordered migration plan

---

## Time Estimate

| Phase | Time |
|-------|------|
| Database schema | 1 hour |
| UI screenshots | 2 hours |
| Status mapping | 30 min |
| Business logic | 1 hour |
| Data samples | 30 min |
| Gap analysis | 1 hour |
| Migration plan | 1 hour |
| **Total** | **7 hours** |

---

## Success Criteria

Phase 0 is complete when:
1. All 6 deliverable documents exist
2. Every PrimeTrade table is mapped to sacks equivalent
3. Every screen has a screenshot with field annotations
4. Status values have explicit mapping
5. Template changes are listed BEFORE migration starts
6. Migration script order is defined

**Only then proceed to Phase 1 (building sacks templates/views to match).**

---

*Created from Yifan migration lessons learned. Following this prevents the patch-and-fix cycle.*
