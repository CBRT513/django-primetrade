# PrimeTrade Business Workflows Documentation

**Generated:** 2026-01-06 (workflows unchanged, validated 2026-01-13)  
**Source:** prt.barge2rail.com  
**Purpose:** Phase 0 Discovery - Document 4 of 6

---

## Workflow Overview

PrimeTrade manages pig iron sales from Liberty Steel through a release-based fulfillment model:

```
Customer Release → Parse/Approve → Schedule Loads → Create BOLs → Enter Official Weights → Generate Reports
```

---

## Workflow 1: Release Upload & Approval

### Input Sources
1. **AI Parser (Gemini 1.5 Flash)** - Upload customer PDF release
2. **Manual Entry** - Enter release data directly

### AI Parser Flow (`release_parser.py`)

```
Customer PDF Upload
       ↓
pypdf extracts text
       ↓
Regex patterns extract:
  - Release Number
  - Release Date
  - Customer ID
  - Ship-To Address
  - Carrier/Ship Via
  - Quantity (Net Tons)
  - Lot Code
  - Chemistry (C/Si/S/P/Mn)
  - Schedule dates
       ↓
Gemini 1.5 Flash enhancement:
  - Parse complex addresses
  - Extract special instructions
  - Normalize data
       ↓
Return parsed JSON for approval
```

### Approval Process (`approve_release` view)

```
Parsed Data Received
       ↓
Validate release_number unique per tenant
       ↓
Transaction.atomic():
  │
  ├─→ Create Release record
  │
  ├─→ Upsert Customer (get_or_create by name)
  │
  ├─→ Upsert CustomerShipTo (by address components)
  │
  ├─→ Upsert Carrier (get_or_create by name)
  │
  ├─→ Validate/Create Lot:
  │     - If exists: validate chemistry within tolerance (0.01)
  │     - If not exists: create with parsed chemistry
  │
  ├─→ Create ReleaseLoad records (one per scheduled date)
  │     - Divide total tons by load count
  │     - Set status = 'PENDING'
  │
  └─→ Mirror chemistry to Product.last_lot fields
       ↓
Return release with normalized IDs
```

### Data Created
| Entity | When Created |
|--------|--------------|
| Release | Always |
| Customer | If new customer name |
| CustomerShipTo | If new address for customer |
| Carrier | If new carrier name |
| Lot | If lot code doesn't exist |
| Product | If material description is new |
| ReleaseLoad | One per scheduled date |

---

## Workflow 2: BOL Creation

### Entry Point
- Loading Schedule screen → "Create BOL" button
- Office page (`/office.html`) → Select release load

### BOL Creation Flow (`create_bol` view)

```
Select Release Load from dropdown
       ↓
Auto-populate from Release:
  - Customer
  - Ship-To Address
  - Product/Lot/Chemistry
  - Special Instructions
  - Care-of Company
       ↓
User enters:
  - Date
  - Carrier (can override)
  - Truck Number
  - Trailer Number (optional)
  - Net Weight (in POUNDS)
  - Notes (optional)
       ↓
Convert weight: pounds → tons (÷ 2000)
       ↓
Generate BOL Number:
  - Format: PRT-YYYY-NNNN
  - Atomic counter per year
       ↓
Create BOL record with:
  - Snapshot all display fields
  - Link to Release/Load/Lot/Product
  - Set net_tons
       ↓
Update ReleaseLoad:
  - status = 'SHIPPED'
  - link BOL
       ↓
Check if all loads shipped:
  - If yes: Release.status = 'COMPLETE'
       ↓
Generate PDF (async-safe):
  - Create PDF with ReportLab
  - Upload to S3
  - Store pdf_url and pdf_key
       ↓
Send email notification (optional)
       ↓
Return BOL number and PDF URL
```

### Weight Entry
- **Input:** Net weight in POUNDS (lbs)
- **Storage:** Converted to TONS (net_tons field)
- **Formula:** `net_tons = input_pounds / 2000`

### PDF Generation (`pdf_generator.py`)

```
BOL Data Loaded
       ↓
ReportLab creates PDF:
  - Header: CBRT logo + "Bill of Lading"
  - BOL Number + Date
  - Ship From: CBRT address with c/o line
  - Ship To: Customer address
  - Carrier info + truck/trailer
  - Product + chemistry
  - Net tons + special instructions
       ↓
Upload to S3: media/bol_pdfs/{bol_number}.pdf
       ↓
Store URL in bol.pdf_url
```

---

## Workflow 3: Weight Variance Management

### Purpose
Track difference between CBRT "bucket" weights and customer certified scale weights.

### Weight Fields on BOL
| Field | Description |
|-------|-------------|
| net_tons | CBRT scale weight (initial estimate) |
| official_weight_tons | Certified scale weight (entered later) |
| weight_variance_tons | Difference (official - CBRT) |
| weight_variance_percent | Percentage variance |
| official_weight_entered_by | Who entered it |
| official_weight_entered_at | When entered |

### Official Weight Entry Flow

```
BOL ships with net_tons (CBRT weight)
       ↓
Customer provides certified scale ticket
       ↓
Staff enters official weight via /bol-weights.html
       ↓
System calculates:
  - variance_tons = official - net_tons
  - variance_percent = (variance / net_tons) * 100
       ↓
Generate Stamped PDF:
  - Add "OFFICIAL WEIGHT" watermark
  - Show both weights
  - Show variance
       ↓
Upload to S3: media/bol_pdfs/{bol_number}_stamped.pdf
       ↓
Store in bol.stamped_pdf_url
```

### Variance Display
- **Green text:** Official (certified scale) weight
- **Amber text:** Planned (bucket estimate) weight
- Variance shown as both tons and percentage

---

## Workflow 4: Inventory Tracking

### Inventory Calculation

```
Starting Inventory (Product.start_tons)
       ↓
Subtract all shipped BOLs:
  - Use official_weight_tons if available
  - Fall back to net_tons (CBRT weight)
       ↓
= Remaining Inventory
```

### Inventory Sources
| Product | Source |
|---------|--------|
| Starting | Product.start_tons (manually set) |
| Shipped | Sum of BOL.official_weight_tons or net_tons |
| Remaining | Calculated: Starting - Shipped |

### Inventory Report (`/inventory-report.html`)

```
Select date range (From/To)
       ↓
Calculate for period:
  - Beginning Inventory (as of From date)
  - Shipped This Period
  - Ending Inventory (as of To date)
       ↓
Display in table
       ↓
Optional: Download PDF
```

---

## Workflow 5: Release Lifecycle

### Status Transitions

```
              ┌──────────────────────────────────────┐
              │                                      │
              ▼                                      │
OPEN ────────────────────────────────→ COMPLETE     │
  │                                        ▲        │
  │   (All loads shipped)                  │        │
  │                                        │        │
  │                                        │        │
  └─────────────────────────────────→ CANCELLED ────┘
              (Manual cancellation)
```

### ReleaseLoad Status Transitions

```
PENDING ──────────────────────────→ SHIPPED
    │       (BOL created)              ▲
    │                                  │
    │                                  │
    └──────────────────────────→ CANCELLED
             (Manual)

Note: When BOL deleted, load reverts to PENDING
```

### Automatic Status Updates
1. **ReleaseLoad → SHIPPED:** When BOL created and linked
2. **Release → COMPLETE:** When all loads are SHIPPED (no PENDING remaining)
3. **ReleaseLoad → PENDING:** When linked BOL is deleted (via BOL.delete() override)

---

## Workflow 6: Client Portal Access

### User Role: Client

```
Client logs in via Google OAuth
       ↓
JWT contains:
  - customer_access: [list of customer IDs]
  - role: "Client"
       ↓
UserCustomerAccess table maps:
  - user_email → customer IDs they can view
       ↓
Client Portal shows:
  - Inventory for their customers
  - Releases for their customers
  - BOLs/shipments for their customers
       ↓
Can download BOL PDFs
Cannot: create BOLs, edit releases, access admin
```

### Data Filtering
- Clients see only data for customers they're linked to
- Filtered via UserCustomerAccess table

---

## Workflow 7: BOL Void/Reissue

### Void Pattern (Soft Delete)

```
BOL exists (is_void = false)
       ↓
Admin voids BOL:
  - is_void = true
  - voided_at = now()
  - voided_by = user email
  - void_reason = text
       ↓
Linked ReleaseLoad:
  - status → PENDING
  - bol reference → NULL
       ↓
Original PDF preserved
       ↓
Can create new BOL for same load
```

### Constraint
- `uniq_active_bol_per_release_line`: Only one non-voided BOL per ReleaseLoad
- Allows reissue after void

---

## Workflow 8: Chemistry Tracking

### Lot-Based Chemistry

```
Release approved with lot code + chemistry
       ↓
System checks existing lot:
  - If exists: validate chemistry within tolerance (0.01)
  - If mismatch > tolerance: return 409 Conflict
  - If new: create Lot with chemistry
       ↓
Chemistry mirrored to Product for display
       ↓
BOL snapshots chemistry at creation:
  - bol.chemistry_display = "C: 4.286 / Si: 0.025..."
```

### Chemistry Fields
| Element | Field | Typical Range |
|---------|-------|---------------|
| Carbon | c | ~4.3 |
| Silicon | si | ~0.025 |
| Sulfur | s | ~0.011 |
| Phosphorus | p | ~0.038 |
| Manganese | mn | ~0.027 |

### Tolerance Validation
- Default tolerance: 0.01
- Blocks release if existing lot chemistry differs beyond tolerance

---

## Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PrimeTrade Data Flow                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Customer PDF ─→ AI Parser ─→ Parsed Data ─→ Release + Loads       │
│                                                    │                │
│                                                    ↓                │
│                              Loading Schedule (PENDING loads)       │
│                                                    │                │
│                                                    ↓                │
│                              Create BOL ─→ PDF Generated            │
│                                   │              │                  │
│                                   ↓              ↓                  │
│                              Update Load    Email Sent              │
│                              (SHIPPED)                              │
│                                   │                                 │
│                                   ↓                                 │
│                           Check All Loads                           │
│                                   │                                 │
│                          (if all shipped)                           │
│                                   ↓                                 │
│                          Release COMPLETE                           │
│                                                                     │
│  Later: Official Weight ─→ Variance Calc ─→ Stamped PDF            │
│                                                                     │
│  Reports: Inventory = Starting - Shipped                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/releases/` | GET | List releases |
| `/api/releases/<id>/view/` | GET | Release detail |
| `/api/releases/upload/` | POST | Upload release PDF |
| `/api/releases/approve/` | POST | Approve parsed release |
| `/api/releases/update/` | POST | Update release |
| `/api/bols/create/` | POST | Create BOL |
| `/api/bols/` | GET | List BOLs |
| `/api/pending-loads/` | GET | Get pending loads for schedule |
| `/api/balances/` | GET | Get inventory balances |
| `/api/products/` | GET/POST | Products CRUD |
| `/api/customers/` | GET/POST | Customers CRUD |
| `/api/carriers/` | GET/POST | Carriers CRUD |

---

## Key Business Rules

1. **BOL Numbers are sequential per year** - PRT-2025-0031 → PRT-2026-0001
2. **Weights entered in pounds, stored in tons** - Conversion at entry
3. **Chemistry validated within tolerance** - Prevents lot mismatches
4. **One active BOL per load** - Constraint enforced at DB level
5. **Void preserves history** - Soft delete with audit trail
6. **Official weight is truth** - Used for billing if available
7. **Client access by customer linkage** - Multi-customer visibility possible

---

*Document 4 of 6 - Phase 0 Discovery*
