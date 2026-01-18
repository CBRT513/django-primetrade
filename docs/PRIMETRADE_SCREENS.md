# PrimeTrade UI Screens Documentation

**Generated:** 2026-01-06 (UI unchanged, row counts refreshed 2026-01-13)  
**Source:** prt.barge2rail.com  
**Purpose:** Phase 0 Discovery - Document 2 of 6  
**Screenshots:** `/docs/primetrade_screenshots/`

---

## Navigation Structure

**Staff Portal Navigation:**
- Dashboard
- Releases
- Schedule
- Products
- Customers
- Carriers
- Admin (Django)
- Client Portal

**Quick Actions (from Dashboard):**
- Create BOL
- Upload Release
- BOL Weights
- Inventory Report

---

## Screen 1: Dashboard (`/`)

**Screenshot:** `01_dashboard.png`

### Summary Cards (Top Row)
| Card | Value | Description |
|------|-------|-------------|
| TOTAL BOLS | 28 | All time count |
| PENDING RELEASES | 5 | Open releases |
| THIS WEEK | 1 | BOLs created this week |
| CUSTOMERS | 7 | Active customers |

### Upcoming Schedule Table
| Column | Description |
|--------|-------------|
| DATE | Scheduled load date |
| RELEASE | Release # + Load # (e.g., "60271 #1") |
| CUSTOMER | Customer name |
| TONS | Planned tonnage |
| STATUS | Badge: PENDING (yellow) |

### Recent BOLs Table
| Column | Description |
|--------|-------------|
| BOL # | Format: PRT-YYYY-NNNN |
| DATE | ISO date (YYYY-MM-DD) |
| CUSTOMER | Customer name |
| TONS | Net tons shipped |

### Recent Releases Table
| Column | Description |
|--------|-------------|
| RELEASE # | 5-digit number |
| CUSTOMER | Customer name |
| TONS | Total tonnage |
| STATUS | Badge: OPEN (green) |

### Quick Actions Buttons
- Create BOL (green, primary)
- Upload Release (outline)
- BOL Weights (outline)
- Inventory Report (outline)

---

## Screen 2: Releases List (`/open-releases/`)

**Screenshot:** `02_releases_list.png`

### Header
- Title: "Releases"
- Subtitle: "View and manage customer releases"
- Action Button: "Upload Release" (green)

### Filter Tabs
- **Open** (default, selected)
- Complete
- Cancelled
- All

### Legend
- **Green** = Official (certified scale) weight
- **Amber** = Planned (estimate) weight

### Search & Controls
- Search box: "Search release #, customer..."
- Pagination: "10 per page" dropdown
- Refresh button

### Table Columns
| Column | Sortable | Description |
|--------|----------|-------------|
| RELEASE # | ✓ | 5-digit release number |
| CUSTOMER | ✓ | Customer name |
| STATUS | ✓ | Badge: OPEN/COMPLETE/CANCELLED |
| LOADS | ✓ | Progress bar showing shipped/total (e.g., "1/6") |
| TONS (SHIPPED/TOTAL) | ✓ | Green for shipped, amber for planned |
| NEXT LOAD | ✓ | Date + urgency badge (Tomorrow/Soon/In Xd) |
| LAST SHIPPED | ✓ | Date of most recent shipment |

### Urgency Badges
- **Tomorrow** (orange) - Load due tomorrow
- **Soon** (yellow) - Load due within 3 days
- **In Xd** (green) - X days until next load

---

## Screen 3: Release Detail (`/api/releases/{id}/view/`)

**Screenshot:** `03_release_detail.png`

### Header Actions
- Cancel Release (red button)
- Back (outline)
- Save Changes (green)

### Form Fields - Row 1
| Field | Type | Example |
|-------|------|---------|
| Release # | Text (readonly?) | 60271 |
| Release Date | Date picker | 12/15/2025 |
| Status | Dropdown | Open |
| Customer | Text | ST. MARYS |
| Customer PO | Text | 156222 |

### Form Fields - Row 2
| Field | Type | Example |
|-------|------|---------|
| Carrier | Text | Piper Trucking |
| Quantity (Net Tons) | Number | 138.00 |

### Ship To Section
| Field | Example |
|-------|---------|
| Name | St. Marys Foundry |
| Street | 405-409 E. South St. |
| City | Saint Marys |
| State | OH |
| Zip | 45885 |

### Product Section
| Field | Example |
|-------|---------|
| Lot | CRT 050N711A |
| Material Description | NODULAR PIG IRON |

### Chemistry Fields
| C | Si | S | P | Mn |
|---|---|---|---|---|
| 4.286 | 0.025 | 0.011 | 0.038 | 0.027 |

### Additional Fields
- **Critical Delivery Instructions** (textarea)
- **c/o Company (for Blind Shipping)** - Default: "PrimeTrade, LLC"

### Loads Table (below form - not visible in screenshot)
Lists individual loads with:
- Load #
- Planned Date
- Planned Tons
- Status
- BOL link (if shipped)

---

## Screen 4: Loading Schedule (`/loading-schedule/`)

**Screenshot:** `04_loading_schedule.png`

### Header
- Title: "Loading Schedule"
- Subtitle: "Pending shipments organized by urgency"
- Count badge: "18 pending loads"

### Filter Buttons
- All (default)
- Overdue Only
- This Week
- Refresh

### Grouped Sections
Loads are grouped by time period:
- **This Week** (3 loads)
- **Next Week** (5 loads)
- **Later** (10 loads)

### Table Columns
| Column | Description |
|--------|-------------|
| RELEASE # | Clickable link to release |
| LOAD # | Sequence number (1, 2, 3...) |
| DATE | Scheduled date |
| DAYS | Urgency badge (Tomorrow/In Xd) |
| CUSTOMER | Customer name |
| TONS | Planned tonnage |
| CARRIER | Carrier name |
| ACTION | "Create BOL" button (green) |

---

## Screen 5: Products (`/products.html`)

**Screenshot:** `05_products.png`

### Add Product Form (Left Side)
| Field | Type | Required |
|-------|------|----------|
| Product Name | Text | Yes |
| Starting Tons | Number | Yes |
| Active (Available for BOLs) | Checkbox | - |
| Buttons: Add Product, Cancel | | |

### All Products Table (Right Side)
| Column | Description |
|--------|-------------|
| STATUS | Badge: ACTIVE (green) |
| PRODUCT | Product name |
| LAST LOT | Most recent lot code |
| C/SI/S/P/MN | Chemistry percentages |
| STARTING | Initial inventory (tons) |
| SHIPPED | Total shipped (tons) |
| REMAINING | Calculated remaining |
| ACTIONS | Edit, Deactivate (red) |

### Current Data
- NODULAR PIG IRON: Starting 3129.72, Shipped 647.00, Remaining 2482.72

---

## Screen 6: Customers (`/customers.html`)

**Screenshot:** `06_customers.png`

### Add Customer Form (Left Side)
| Field | Type | Required |
|-------|------|----------|
| Customer Name | Text | Yes |
| Street Address | Text | Yes |
| Address Line 2 | Text | No |
| City | Text | Yes |
| State | Dropdown | Yes |
| ZIP Code | Text | Yes |
| Active (Available for BOLs) | Checkbox | - |
| Buttons: Add Customer, Cancel | | |

### All Customers Table (Right Side)
| Column | Description |
|--------|-------------|
| STATUS | Badge: ACTIVE (green) |
| CUSTOMER | Customer name |
| HEADQUARTERS ADDRESS | Full address |
| ACTIONS | Edit, Ship-Tos, Deactivate (red) |

### Ship-Tos Button
Opens modal/page to manage multiple ship-to addresses per customer.

---

## Screen 7: Carriers (`/carriers.html`)

**Screenshot:** `07_carriers.png`

### Add Carrier Form (Left Side)
| Field | Type | Required |
|-------|------|----------|
| Carrier Name | Text | Yes |
| Contact Person | Text | No |
| Phone | Text | No |
| Email | Text | No |
| Active (Available for BOLs) | Checkbox | - |
| Buttons: Add Carrier, Cancel | | |

### All Carriers Table (Right Side)
| Column | Description |
|--------|-------------|
| STATUS | Badge: ACTIVE (green) |
| CARRIER | Carrier name |
| CONTACT | Contact info or "No contact info" |
| TRUCKS | Count of trucks (e.g., "5 trucks") |
| ACTIONS | Edit, Deactivate (red) |

### Current Carriers
- Brown Transport (5 trucks)
- CUSTOMER PU (0 trucks)
- Piper Trucking (4 trucks)
- R&J Trucking (2 trucks)

---

## Screen 8: Admin (`/admin/`)

**Screenshot:** `08_admin.png`

### Django Administration
Standard Django admin interface with BOL_SYSTEM section:

| Model | Actions |
|-------|---------|
| Audit logs | View only |
| Bol counters | Add, Change |
| Bols | Add, Change |
| Carriers | Add, Change |
| Company Branding | Add, Change |
| Customer ship tos | Add, Change |
| Customers | Add, Change |
| Lots | Add, Change |
| Products | Add, Change |
| Releases | Add, Change |
| Role Redirect Configurations | Add, Change |
| Tenants | Add, Change |
| User Customer Access | Add, Change |

---

## Screen 9: Client Portal (`/client.html`)

**Screenshot:** `09_client_portal.png` (large file)

### Header
- Welcome message
- User email
- Loading Schedule link
- Logout

### Inventory Summary Card
| Field | Value |
|-------|-------|
| Product | NODULAR PIG IRON |
| Starting | 3129.72 |
| Shipped | 647.00 |
| Remaining | 2482.72 |

### Recent Shipments Table
| Column | Description |
|--------|-------------|
| Date | Ship date |
| BOL # | BOL number (clickable → PDF) |
| Product | Product name |
| Truck | Truck number |
| Net Tons | Weight |
| Status | "Shipped" badge |

- Pagination: 10/25/50/100 per page
- Total: 28 shipments

### Releases Section
| Column | Description |
|--------|-------------|
| Release # | Release number |
| Customer | Customer name |
| Status | OPEN badge |
| Shipped | Count + tons shipped |
| Remaining | Count + tons remaining |
| Total | Total loads |
| Next Load | Date of next scheduled load |

- Filter tabs: Open, Complete, Cancelled, All

---

## Screen 10: Create BOL (`/office.html`)

**Screenshot:** `10_create_bol.png`

### Form Fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| Release Load | Dropdown | Yes | Shows: "60297 - Load 1 — LIBERTY — 2026-01-07 — 23.000 NT" |
| Date | Date picker | Yes | |
| Product | Dropdown | Yes | Pre-filled: NODULAR PIG IRON |
| Customer | Dropdown | Yes | Auto-populated from release |
| Customer PO # | Text | No | |
| Ship-To Address | Dropdown | Yes | Based on customer |
| Carrier | Dropdown | Yes | |
| Truck Number | Dropdown | Yes | Filtered by carrier |
| Trailer Number | Text | No | |
| Net Weight (lbs) | Number | Yes | In pounds |
| Notes | Textarea | No | |

### Actions
- **Preview BOL** - Opens PDF preview
- After preview: Confirm to save and generate final BOL

### Workflow
1. Select Release Load → auto-populates Customer, Ship-To, Product
2. Select Carrier → populates Truck dropdown
3. Enter weight in pounds
4. Preview BOL → Review PDF
5. Confirm → Creates BOL, updates inventory

---

## Screen 11: Upload Release (`/releases.html`)

**Screenshot:** `11_upload_release.png`

### Options
1. **Use AI parser (Gemini 1.5 Flash)** - Checkbox
2. **Upload & Parse** - Button to upload PDF
3. **Manual Entry** - Button for manual form

### AI Parser Feature
- Uses Google Gemini 1.5 Flash
- Parses customer PDF release documents
- Extracts: Release #, Customer, Ship-To, Quantity, Dates, etc.

### Manual Entry
Opens form similar to Release Detail for manual data entry.

---

## Screen 12: BOL Weights (`/bol-weights.html`)

**Screenshot:** `12_bol_weights.png`

### Purpose
Enter official certified scale weights after BOLs are shipped.

### Controls
- Toggle: "Show all (including official)"
- Pagination: 10/25/50/100 per page

### Table Columns
| Column | Description |
|--------|-------------|
| BOL # | BOL number |
| DATE | Ship date |
| CUSTOMER | Customer name |
| PRODUCT | Product name |
| CBRT WEIGHT | Original bucket weight (tons) |
| OFFICIAL | Certified scale weight (tons) |
| VARIANCE | Difference (tons and %) |
| STATUS | PENDING or COMPLETE |
| ACTION | "Enter Weight" button |

### Workflow
1. BOL ships with estimated "bucket" weight
2. Customer provides certified scale weight
3. Staff enters official weight
4. System calculates variance
5. Generates stamped PDF with official weight

---

## Screen 13: Inventory Report (`/inventory-report.html`)

**Screenshot:** `13_inventory_report.png`

### Date Range Selection
- From: Date picker
- To: Date picker
- Generate Report button
- Download PDF button

### Report Table
| Column | Description |
|--------|-------------|
| PRODUCT | Product name |
| BEGINNING INVENTORY | Starting tons for period |
| SHIPPED THIS PERIOD | Total shipped in date range |
| ENDING INVENTORY | Calculated ending balance |

### Notes
- Weight Display: "All weights shown are Bucket weights (net tons)"
- Used for end-of-month inventory reconciliation

---

## Key UI Patterns

### Status Badges
| Status | Color | Context |
|--------|-------|---------|
| ACTIVE | Green | Products, Customers, Carriers |
| OPEN | Green | Releases |
| PENDING | Yellow | Schedule, BOL Weights |
| COMPLETE | Blue | Releases |
| CANCELLED | Red | Releases |
| SHIPPED | Green | BOLs |

### Urgency Badges
| Badge | Color | Meaning |
|-------|-------|---------|
| Tomorrow | Orange | Due tomorrow |
| Soon | Yellow | Due within 3 days |
| In Xd | Green | X days out |

### Form Patterns
- Left column: Add new form
- Right column: List existing items
- Actions: Edit, Deactivate (soft delete)

### Weight Display
- **Green** = Official (certified scale)
- **Amber** = Planned (bucket estimate)

---

## Missing Screens (Not Built)

1. **BOL Detail Page** - No dedicated page; BOLs open as PDF directly
2. **Truck Management** - Trucks managed through Carrier page
3. **Lot Management** - Lots managed through Django admin
4. **User Management** - Handled in Django admin

---

## Deprecated/Unused

1. **`/bol.html`** - Old BOL form, no longer used (marked for removal)

---

*Document 2 of 6 - Phase 0 Discovery Complete*
