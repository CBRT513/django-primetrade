# PrimeTrade Data Samples

**Generated:** 2026-01-13 (refreshed)
**Source:** prt.barge2rail.com (production database)
**Purpose:** Phase 0 Discovery - Document 5 of 6

---

## Overview

| Entity | Total Records | Sample Size |
|--------|---------------|-------------|
| Tenants | 1 | 1 |
| Products | 1 | 1 |
| Lots | 2 | 2 |
| Customers | 8 | 5 |
| Customer Ship-Tos | 9 | 5 |
| Carriers | 9 | 5 |
| Trucks | 16 | 10 |
| Releases | 18 | 3 |
| Release Loads | 56 | 5 |
| BOLs | 36 | 3 |
| Audit Logs | 168 | 5 |

---

## Tenant

```json
{
  "id": 1,
  "name": "Liberty Steel",
  "code": "LIBERTY",
  "is_active": true,
  "created_at": "2025-12-05T15:02:11Z"
}
```

**Note:** Single tenant system. All entities reference this tenant.

---

## Products

```json
{
  "id": 9,
  "name": "NODULAR PIG IRON",
  "start_tons": 3129.72,
  "is_active": true,
  "last_lot_code": "CRT 050N711A",
  "c": 4.286,
  "si": 0.025,
  "s": 0.011,
  "p": 0.038,
  "mn": 0.027
}
```

**Note:** Single product. Chemistry mirrored from latest lot.

---

## Lots

```json
[
  {
    "id": 9,
    "code": "CRT 050N711A",
    "c": 4.286,
    "si": 0.025,
    "s": 0.011,
    "p": 0.038,
    "mn": 0.027,
    "product_id": 9
  },
  {
    "id": 10,
    "code": "050N711A",
    "c": 4.286,
    "si": 0.025,
    "s": 0.011,
    "p": 0.038,
    "mn": 0.027,
    "product_id": 9
  }
]
```

**Note:** Same chemistry, different lot code formats (with/without "CRT" prefix).

---

## Customers

```json
[
  {
    "id": 18,
    "customer": "INTAT",
    "address": "2148 North SR 3",
    "city": "Rushville",
    "state": "IN",
    "zip": "46173",
    "is_active": true
  },
  {
    "id": 19,
    "customer": "MINSTER",
    "address": "240 West 5th Street",
    "city": "Minster",
    "state": "OH",
    "zip": "45865",
    "is_active": true
  },
  {
    "id": 20,
    "customer": "LIBERTY TECH",
    "address": "630 Liberty Road",
    "city": "Delaware",
    "state": "OH",
    "zip": "43015",
    "is_active": true
  },
  {
    "id": 21,
    "customer": "LIBERTY",
    "address": "550 Liberty Rd",
    "city": "Delaware",
    "state": "OH",
    "zip": "43015",
    "is_active": true
  },
  {
    "id": 22,
    "customer": "ST. MARYS",
    "address": "",
    "city": "405-409 E. South St. Saint Marys",
    "state": "OH",
    "zip": "45885",
    "is_active": true
  }
]
```

**Data Quality Issue:** ST. MARYS has malformed address (street in city field).

---

## Customer Ship-Tos

```json
[
  {
    "id": 14,
    "customer": "INTAT",
    "name": "INTAT",
    "street": "2148 North SR 3",
    "city": "Rushville",
    "state": "IN",
    "zip": "46173"
  },
  {
    "id": 15,
    "customer": "MINSTER",
    "name": "The C.A, Lawton Co.",
    "street": "240 West 5th Street",
    "city": "Minster",
    "state": "OH",
    "zip": "45865"
  },
  {
    "id": 16,
    "customer": "LIBERTY TECH",
    "name": "Liberty Technology Co.",
    "street": "630 Liberty Road",
    "city": "Delaware",
    "state": "OH",
    "zip": "43015"
  },
  {
    "id": 17,
    "customer": "LIBERTY",
    "name": "Liberty Casting Co.",
    "street": "550 Liberty Rd",
    "city": "Delaware",
    "state": "OH",
    "zip": "43015"
  },
  {
    "id": 18,
    "customer": "ST. MARYS",
    "name": "ST. MARYS",
    "street": "405-409 E. South St. ",
    "city": "Saint Marys",
    "state": "OH",
    "zip": "45885"
  }
]
```

**Note:** Ship-to names differ from customer names (e.g., "MINSTER" → "The C.A, Lawton Co.").

---

## Carriers

```json
[
  {"id": 11, "carrier_name": "Brown Transport", "is_active": true, "truck_count": 5},
  {"id": 12, "carrier_name": "Piper Trucking", "is_active": true, "truck_count": 4},
  {"id": 13, "carrier_name": "R & J Trucking", "is_active": false, "truck_count": 0},
  {"id": 14, "carrier_name": "R&J Trucking", "is_active": true, "truck_count": 2},
  {"id": 15, "carrier_name": "CUSTOMER PU", "is_active": true, "truck_count": 0}
]
```

**Data Quality Issue:** Duplicate carrier - "R & J Trucking" (inactive) vs "R&J Trucking" (active).

---

## Trucks

```json
[
  {"id": 30, "carrier_name": "Brown Transport", "truck_number": "003", "trailer_number": "657"},
  {"id": 31, "carrier_name": "Brown Transport", "truck_number": "188", "trailer_number": "316"},
  {"id": 32, "carrier_name": "Brown Transport", "truck_number": "409", "trailer_number": "654"},
  {"id": 34, "carrier_name": "Brown Transport", "truck_number": "411", "trailer_number": "647"},
  {"id": 33, "carrier_name": "Brown Transport", "truck_number": "J08", "trailer_number": "660"},
  {"id": 35, "carrier_name": "Piper Trucking", "truck_number": "550", "trailer_number": "10"},
  {"id": 36, "carrier_name": "Piper Trucking", "truck_number": "587", "trailer_number": "T4"},
  {"id": 37, "carrier_name": "Piper Trucking", "truck_number": "9", "trailer_number": "20"},
  {"id": 38, "carrier_name": "Piper Trucking", "truck_number": "94", "trailer_number": "33"},
  {"id": 26, "carrier_name": "R&J Trucking", "truck_number": "148108", "trailer_number": "T797"}
]
```

**Note:** Truck numbers vary in format (numeric, alphanumeric, different lengths).

---

## Releases

```json
[
  {
    "id": 41,
    "release_number": "60298",
    "release_date": "2025-12-23",
    "customer_id_text": "LIBERTY TECH",
    "customer_po": "911660",
    "quantity_net_tons": 23.00,
    "status": "OPEN",
    "ship_to_name": "Liberty Technology Co.",
    "ship_to_city": "Delaware",
    "ship_to_state": "OH",
    "lot": "CRT 050N711A",
    "material_description": "NODULAR PIG IRON"
  },
  {
    "id": 40,
    "release_number": "60297",
    "release_date": "2025-12-23",
    "customer_id_text": "LIBERTY",
    "customer_po": "445023",
    "quantity_net_tons": 69.00,
    "status": "OPEN",
    "ship_to_name": "Liberty Casting Co.",
    "ship_to_city": "Delaware",
    "ship_to_state": "OH",
    "lot": "CRT 050N711A",
    "material_description": "NODULAR PIG IRON"
  },
  {
    "id": 39,
    "release_number": "60271",
    "release_date": "2025-12-15",
    "customer_id_text": "ST. MARYS",
    "customer_po": "156222",
    "quantity_net_tons": 138.00,
    "status": "OPEN",
    "ship_to_name": "St. Marys Foundry",
    "ship_to_city": "Saint Marys",
    "ship_to_state": "OH",
    "lot": "CRT 050N711A",
    "material_description": "NODULAR PIG IRON"
  }
]
```

**Pattern:** Release numbers are 5-digit (60xxx series). All use same lot currently.

---

## Release Loads

```json
[
  {
    "id": 117,
    "release_number": "60298",
    "seq": 1,
    "date": "2026-01-19",
    "planned_tons": 23.000,
    "status": "PENDING",
    "bol_number": null
  },
  {
    "id": 116,
    "release_number": "60297",
    "seq": 3,
    "date": "2026-01-28",
    "planned_tons": 23.000,
    "status": "PENDING",
    "bol_number": null
  },
  {
    "id": 115,
    "release_number": "60297",
    "seq": 2,
    "date": "2026-01-21",
    "planned_tons": 23.000,
    "status": "PENDING",
    "bol_number": null
  },
  {
    "id": 114,
    "release_number": "60297",
    "seq": 1,
    "date": "2026-01-07",
    "planned_tons": 23.000,
    "status": "PENDING",
    "bol_number": null
  },
  {
    "id": 113,
    "release_number": "60271",
    "seq": 6,
    "date": "2026-01-28",
    "planned_tons": 23.000,
    "status": "PENDING",
    "bol_number": null
  }
]
```

**Pattern:** Planned tons = total ÷ load count. Each load gets a scheduled date.

---

## BOLs

```json
[
  {
    "id": 73,
    "bol_number": "PRT-2026-0018",
    "date": "2026-01-06",
    "buyer_name": "HW-ST. MARYS",
    "carrier_name": "R&J Trucking",
    "truck_number": "15111",
    "net_tons": 23.93,
    "official_weight_tons": null,
    "product_name": "NODULAR PIG IRON",
    "release_number": "60276-1",
    "is_void": false,
    "ship_to": "St. Marys Foundry, Inc.\n405-409 E. South St.\nSt. Marys, OH 45885",
    "customer_po": "P/O999925120338"
  },
  {
    "id": 55,
    "bol_number": "PRT-2025-0031",
    "date": "2025-12-22",
    "buyer_name": "INTAT",
    "carrier_name": "Brown Transport",
    "truck_number": "409",
    "net_tons": 22.80,
    "official_weight_tons": null,
    "product_name": "NODULAR PIG IRON",
    "release_number": "60181-4",
    "is_void": false,
    "ship_to": "INTAT\n2148 North SR 3\nRushville, IN 46173",
    "customer_po": "676224"
  },
  {
    "id": 54,
    "bol_number": "PRT-2025-0030",
    "date": "2025-12-17",
    "buyer_name": "LIBERTY",
    "carrier_name": "Piper Trucking",
    "truck_number": "550",
    "net_tons": 22.82,
    "official_weight_tons": 22.70,
    "product_name": "NODULAR PIG IRON",
    "release_number": "60132-2",
    "is_void": false,
    "ship_to": "Liberty Casting Co.\n550 Liberty Rd\nDelaware, OH 43015",
    "customer_po": "444868"
  }
]
```

**Patterns:**
- BOL numbers: `PRT-{YEAR}-{SEQ:04d}`
- Release reference: `{release_number}-{load_seq}`
- Ship-to is newline-delimited address block
- Most BOLs missing official weight (entered later)

---

## BOL Counters

```json
[
  {"id": 5, "year": 2025, "sequence": 31, "tenant_id": null},
  {"id": 6, "year": 2026, "sequence": 18, "tenant_id": null}
]
```

**Issue:** `tenant_id` is NULL - not tenant-scoped. Would cause BOL number collisions if multi-tenant.

---

## Audit Logs

```json
[
  {
    "id": 141,
    "action": "BOL_CREATED",
    "object_type": "BOL",
    "object_id": "73",
    "message": "BOL created PRT-2026-0018",
    "user_email": "clif@barge2rail.com",
    "created_at": "2026-01-06T14:06:40Z"
  },
  {
    "id": 140,
    "action": "UPDATE",
    "object_type": "ReleaseLoad",
    "object_id": "117",
    "message": "Updated load date to 2026-01-19",
    "user_email": "clif@barge2rail.com",
    "created_at": "2026-01-05T19:38:47Z"
  },
  {
    "id": 139,
    "action": "RELEASE_APPROVE_CREATED",
    "object_type": "Release",
    "object_id": "41",
    "message": "Approved release 60298",
    "user_email": "clif@barge2rail.com",
    "created_at": "2025-12-23T16:57:27Z"
  },
  {
    "id": 138,
    "action": "RELEASE_APPROVE_CREATED",
    "object_type": "Release",
    "object_id": "40",
    "message": "Approved release 60297",
    "user_email": "clif@barge2rail.com",
    "created_at": "2025-12-23T16:55:53Z"
  },
  {
    "id": 137,
    "action": "BOL_CREATED",
    "object_type": "BOL",
    "object_id": "55",
    "message": "BOL created PRT-2025-0031",
    "user_email": "rwhite@barge2rail.com",
    "created_at": "2025-12-22T18:25:51Z"
  }
]
```

**Action Types:**
- `BOL_CREATED` - New BOL
- `RELEASE_APPROVE_CREATED` - Release approved from parsed PDF
- `UPDATE` - Record modified

---

## Voided BOLs

**None currently.** System supports void but hasn't been used.

---

## User Customer Access

**None configured.** Client portal access control not in use.

---

## Data Quality Issues Summary

| Issue | Entity | Description | Migration Action |
|-------|--------|-------------|------------------|
| Malformed address | Customer #22 (ST. MARYS) | Street in city field | Clean during migration |
| Duplicate carrier | Carriers #13, #14 | "R & J" vs "R&J" | Merge to single record |
| NULL tenant_id | BOL Counters | Not tenant-scoped | Assign tenant during migration |
| Inconsistent lot codes | Lots | "CRT 050N711A" vs "050N711A" | Normalize format |

---

## Migration Test Data Requirements

For Sacks migration testing, we need to handle:

1. **Products** - 1 record with chemistry
2. **Lots** - 2 records linked to product
3. **Customers** - 7 records with addresses
4. **Ship-Tos** - 12 records (multiple per customer)
5. **Carriers** - 5 records (dedupe needed)
6. **Trucks** - 11 records linked to carriers
7. **Releases** - 16 records with varying statuses
8. **Release Loads** - 50 records (27 shipped, 19 pending, 4 cancelled)
9. **BOLs** - 28 records with PDF URLs
10. **Audit Logs** - 141+ records (preserve for compliance)

---

*Document 5 of 6 - Phase 0 Discovery*
