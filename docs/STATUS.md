# django-primetrade — Project Status Report

Updated: 2025-11-03

## Executive summary
- Current: Live Django app with SSO. Stable flows for Release intake/approval, normalization/upserts (Customer, Ship-To, Carrier, Lot+chemistry), load‑driven BOL creation with professional landscape PDF (both CBRT + PrimeTrade logos, single page, B&W optimized), open releases reporting, product chemistry mirroring, carrier/truck management, audit logging (with optional external forward), health and balances/history endpoints. Recent BOLs created successfully with new PDF design.
- Hot issues: Product edit via POST /api/products/ returns Bad Request/"already exists" when updating start_tons; upsert‑on‑POST patch is implemented locally and needs deployment. Deploy logs show "models have changes not reflected in a migration" warning—verify migrations are fully applied. UI still requests /api/branding (endpoint was removed)—clean up that call.
- Immediate next steps: deploy product upsert fix; confirm migration 0006 indexes applied on Neon; remove stale /api/branding request; optionally enable Galactica forwarding via env vars.

## Where we are (functional scope)
- Release intake and approval
  - Upload/parse PDF (regex + optional AI); approve endpoint upserts Customer (by customer_id_text), Ship‑To (unique by address per customer), Carrier (by name), Lot (by code), and validates lot chemistry within tolerance (env LOT_CHEM_TOLERANCE, default ±0.01).
  - Duplicate release_number rejected with 409; response returns normalized IDs.
  - Release detail page + GET/PATCH API mirrors approve logic with validation and upserts.
- Scheduling and BOLs
  - ReleaseLoad rows represent planned loads; Office UI is load‑driven: pick a PENDING load, fields auto‑fill/lock (including street2 in ship-to address), edit net tons and carrier/truck; confirm creates BOL with lot_ref and release_number, marks load SHIPPED, and auto‑completes Release when no pending loads remain.
  - PDF generation: professional landscape (11"x8.5") single-page design with CBRT + PrimeTrade logos, B&W laser printer optimized. Includes dynamic chemistry (from lot), lot number, release number, customer PO, full ship-to address with street2. Preview and saved PDFs both use same generator. After creation, PDF opens automatically in new tab.
  - History and balances endpoints provide shipped/remaining by product.
- Master data and UI
  - Products page shows last lot and chemistry mirrored from Lot; balances displayed.
  - Customers page manages Ship‑To addresses via per‑customer modal.
  - Carriers page manages carriers and trucks.
  - Home portal with Admin/Office/Client tabs; Open Releases list with drill‑down.
- Audit and ops
  - AuditLog model + /api/audit/ endpoint; key actions instrumented (release approve/update, BOL create, ship‑to/carrier changes). Optional forwarding to GALACTICA_URL with GALACTICA_API_KEY. Health endpoint present.
- Performance
  - Migration 0006 adds indexes on Release(status, created_at), ReleaseLoad(status), ReleaseLoad(release,status), BOL(product), BOL(date), BOL(customer).

## Plans
- Immediate (today)
  - Deploy product upsert‑on‑POST (update by id) so editing start_tons doesn’t collide with unique name; return 409 on rename‑to‑duplicate.
  - Remove stray /api/branding fetch from UI to eliminate 404 noise.
  - Ensure migration 0006 applied on Neon (check django_migrations table or re‑run migrate).
  - Optionally set Galactica env vars and verify ingestion.
- Short term (1–2 weeks)
  - Office UX hardening: hide legacy free‑form controls behind “Advanced (admin)”; ensure only carrier/truck/trailer and net tons are editable.
  - Add simple Audit UI page with filters. Add role‑based permissions for Admin/Office/Client views.
  - Tests: unit tests for approve/patch flows, lot chemistry tolerance, load‑driven BOL. Smoke tests for endpoints.
  - Data integrity: admin actions to split/merge Ship‑To; product rename flow with safe migration of FKs; lock Lot→Product once shipping starts.
  - Ops: structured error telemetry; tighter logging redaction; periodic backup/restore docs; staging environment.
- Later
  - PWA enhancements (offline/manifest), richer reports (by customer/lot/date), reprint/regenerate BOL, CSV export/import for masters, bulk scheduling.

## Current schema (models, key fields, constraints)
- Product
  - name (unique), start_tons (Decimal 10,2), is_active; mirrors: last_lot_code, c/si/s/p/mn; ordering name.
  - Computed: shipped_tons (sum BOL.net_tons), remaining_tons.
- Customer
  - customer (unique), address, city, state(2), zip, is_active; ordering customer.
- CustomerShipTo
  - FK customer, name, street, street2 (optional), city, state(2), zip, is_active; unique_together (customer, street, city, state, zip); ordering customer,name.
- Carrier
  - carrier_name (unique), contact, phone, email, is_active; ordering carrier_name.
- Truck
  - FK carrier, truck_number, trailer_number, is_active; unique_together (carrier, truck_number); ordering truck_number.
- BOLCounter
  - year (unique), sequence; get_next_bol_number() issues “PRT-YYYY-####”.
- BOL
  - bol_number (unique, indexed), FK product, product_name (mirror), FK customer (nullable), buyer_name, ship_to (text), customer_po, FK carrier, carrier_name (mirror), FK truck (nullable), truck_number, trailer_number, date (string), net_tons (Decimal 10,2), notes, pdf_url, created_by_email, FK lot_ref (nullable, for chemistry), release_number (text); ordering -created_at.
  - save() auto‑assigns bol_number/product_name/carrier_name, logs.
  - PDF generation pulls chemistry from lot_ref, displays release_number, customer_po, and includes street2 in ship-to address.
- CompanyBranding
  - Singleton config (company_name, address lines, phone, website, email, logo fields); enforced single row.
- Lot
  - code (unique, indexed), FK product (nullable), c/si/s/p/mn; ordering code.
- Release
  - release_number (unique, indexed), release_date, customer_id_text, customer_po, ship_via, fob, ship_to_[name/street/street2/city/state/zip], lot (text), material_description, quantity_net_tons (Decimal 10,2), status {OPEN, COMPLETE, CANCELLED}; ordering -created_at.
  - FKs: customer_ref, ship_to_ref, carrier_ref, lot_ref (all nullable).
  - Properties: loads counts (total/shipped/remaining).
- ReleaseLoad
  - FK release (related_name=loads), seq (unique per release), date, planned_tons (Decimal 10,3), status {PENDING, SHIPPED, CANCELLED}, FK bol (nullable); unique_together (release, seq); ordering seq.
- AuditLog
  - action, object_type, object_id, message, user_email, ip, method, path, user_agent, extra (JSON); ordering -created_at.
- Indexes (migration 0006)
  - Release(status, created_at), ReleaseLoad(status), ReleaseLoad(release, status), BOL(product), BOL(date), BOL(customer).

## Current file list (project tree)
```
bol_system/
  __init__.py
  __pycache__/
    __init__.cpython-313.pyc
    admin.cpython-313.pyc
    apps.cpython-313.pyc
    models.cpython-313.pyc
    serializers.cpython-313.pyc
    urls.cpython-313.pyc
    views.cpython-313.pyc
  admin.py
  ai_parser.py
  apps.py
  auth_views.py
  migrations/
    0001_initial.py
    0002_releases.py
    0003_customer_shipto_lot_and_release_fk.py
    0004_product_chemistry_fields.py
    0005_auditlog.py
    0006_performance_indexes.py
    0007_remove_bol_bol_product_idx_remove_bol_bol_date_idx_and_more.py
    0008_releaseload_actual_tons.py
    0009_add_street2_fields.py
    0010_add_lot_and_release_to_bol.py
    __init__.py
    __pycache__/
      0001_initial.cpython-313.pyc
      __init__.cpython-313.pyc
  models.py
  pdf_generator.py
  release_parser.py
  serializers.py
  test_auth.py
  urls.py
  views.py
docs/
  legacy/
    firebase-config.js
media/
  bol_pdfs/
    PRT-2025-0002.pdf
    PRT-2025-0003.pdf
    PRT-2025-0004.pdf
    PRT-2025-0005.pdf
primetrade_project/
  __init__.py
  __pycache__/
    __init__.cpython-313.pyc
    settings.cpython-313.pyc
    urls.cpython-313.pyc
    wsgi.cpython-313.pyc
  asgi.py
  auth_views.py
  auth_views.py.backup
  settings.py
  urls.py
  wsgi.py
static/
  bol.html
  carriers.html
  cbrt-logo-optimized.svg
  cbrt-logo.jpg
  primetrade-logo.jpg
  client.html
  css/
    cbrt-brand.css
  customers.html
  index.html
  js/
    api.js
    auth.js
    firebase-config.js
    utils.js
  login.html
  office.html
  products.html
  releases.html
templates/
  404.html
  500.html
  emergency_login.html
  index.html
  login.html
  open_releases.html
  release_detail.html
```

## Notes and risks
- Product edits: server currently treats POST as create; upsert patch is ready—deploy to resolve “Bad Request/exists” on edits.
- Migrations: logs show “models have changes not reflected”; confirm no pending local model diffs and re‑run migrate on Neon (ensure 0006 applied).
- UI cleanup: remove /api/branding fetch to stop 404s.
- Security/roles: endpoints are session‑authenticated; add groups/permissions before multi‑tenant or external users.
- Testing: minimal automated tests—add unit/API tests to guard the load‑driven BOL flow and chemistry tolerance logic.
