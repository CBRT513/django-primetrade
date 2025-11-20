# Workflow Changes - November 20, 2025

## Summary
Enhanced the Release Upload and BOL Creation workflows with intelligent combobox inputs, automatic data population, and improved BOL preview accuracy.

---

## 1. Customer ID and Carrier Combobox with "Add New" Functionality

### Context
Previously, Customer ID and Carrier fields in the Release Upload page were plain text inputs. Users had to manually type values, with no visibility into existing records or ability to quickly add new entries.

### Changes Made

#### Frontend (static/releases.html)
- **Replaced text inputs with combobox pattern** (HTML5 text input + datalist)
  - Customer ID: Input with autocomplete suggestions from existing customers
  - Carrier: Input with autocomplete suggestions from existing carriers
  - Added "Add" buttons next to each field

- **Added Modal Dialogs**
  - "Add Customer" modal with full address form (name, address, city, state, zip)
  - "Add Carrier" modal with contact information (name, contact, phone, email)

- **JavaScript Functionality**
  - `loadCustomers()` - Fetches all customers from `/api/customers/` on page load
  - `loadCarriers()` - Fetches all carriers from `/api/carriers/` on page load
  - `showAllSuggestions()` - Displays datalist dropdown when input is clicked/focused
  - Auto-population: When customer is selected, Ship-To address fields auto-fill
  - Modal save handlers: POST new customer/carrier to API, reload suggestions, update input

#### Backend (bol_system/views.py)
- **Added GET endpoint**: `/api/customers/<int:customer_id>/` (lines 265-277)
  - Returns single customer details by ID
  - Used for future customer detail lookups

#### Backend (bol_system/urls.py)
- **Added route**: `path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail')`

### Technical Details

**Combobox Pattern**:
```html
<input id="customerId" type="text" list="customerSuggestions" style="flex: 1;">
<datalist id="customerSuggestions">
  <!-- Populated via JavaScript with customer names -->
</datalist>
<button id="addCustomerBtn" class="btn btn-sm">Add</button>
```

**Auto-Population Logic** (static/releases.html:298-313):
```javascript
customerIdInput.addEventListener('change', async function() {
  const customerName = this.value.trim();
  const customer = customersCache.find(c => c.customer === customerName);
  if (customer) {
    // Populate Ship-To fields with customer's primary address
    document.getElementById('shipToName').value = customer.customer;
    document.getElementById('shipToStreet').value = customer.address || '';
    // ... etc
  }
});
```

### User Benefits
- ✅ **See AI-parsed values** even when they don't match existing entries (critical requirement)
- ✅ **Autocomplete suggestions** reduce typing and prevent duplicates
- ✅ **Quick "Add New"** without leaving the page
- ✅ **Auto-populate Ship-To** saves time and reduces errors
- ✅ **Seamless integration** with existing approval workflow

### Files Modified
- `bol_system/views.py` - Added customer_detail endpoint
- `bol_system/urls.py` - Added customer detail route
- `static/releases.html` - Combobox UI, modals, JavaScript functionality

---

## 2. Fixed: Cancelled Release Re-Creation

### Context
When a user cancelled a release to correct an error, they could not re-upload the same release number due to a database unique constraint violation.

### Problem
```
django.db.utils.IntegrityError: duplicate key value violates unique constraint
"bol_system_release_release_number_key"
DETAIL:  Key (release_number)=(60137) already exists.
```

The `release_number` field has a unique constraint in the database. Even though application logic checked for duplicates excluding CANCELLED status, the database prevented the INSERT.

### Solution (bol_system/views.py:847-866)

**Before**:
```python
if Release.objects.filter(release_number=release_number).exists():
    # Blocked ALL duplicates, including cancelled
    return Response({'error': 'Duplicate release_number'}, status=409)
```

**After**:
```python
# Check for active (non-cancelled) duplicates
existing_active = Release.objects.filter(release_number=release_number).exclude(status='CANCELLED').first()
if existing_active:
    return Response({'error': 'Duplicate release_number'}, status=409)

# If there's a cancelled release, delete it to allow re-creation
cancelled_release = Release.objects.filter(release_number=release_number, status='CANCELLED').first()
if cancelled_release:
    logger.info(f"Deleting cancelled release {release_number} (ID: {cancelled_release.id})")
    cancelled_release.delete()  # Cascade deletes associated loads
```

### Behavior
1. **Active releases**: Still blocks duplicates for OPEN/COMPLETE releases
2. **Cancelled releases**: Automatically deleted (with cascade delete of loads) before creating new release
3. **Audit trail**: Deletion logged for compliance

### User Impact
- ✅ Can now re-upload a release after cancelling it
- ✅ No manual database cleanup required
- ✅ Old cancelled data is cleaned up automatically

---

## 3. Fixed: BOL Preview Missing Release Data

### Context
When creating a BOL from a pending release load, the preview was missing critical fields:
- c/o Company (showed "PrimeTrade, LLC" instead of custom value like "Hickman, Williams & Company")
- Release # (blank instead of "60137-1")
- Lot Number (showed "N/A" instead of actual lot code)
- Chemistry (showed "Analysis: N/A" instead of actual C, Si, S, P, Mn values)

### Root Cause
The `preview_bol` endpoint (bol_system/views.py:486) only used form data from the Create BOL page. The form doesn't include fields for lot, chemistry, or c/o company because those are stored in the release, not entered per-BOL.

### Solution (bol_system/views.py:515-563)

**Added loadId detection**:
```python
# Check if creating from a release load to pull additional data
load_id = data.get('loadId') or data.get('load_id')
if load_id:
    release_load = ReleaseLoad.objects.select_related(
        'release',
        'release__lot_ref'
    ).get(id=load_id)
    release_obj = release_load.release
```

**Updated preview_data to use release values**:
```python
preview_data = {
    # ... other fields ...
    'releaseNumber': f'{release_obj.release_number}-{release_load.seq}' if release_load else data.get('releaseNumber', ''),
    'care_of_co': release_obj.care_of_co if release_obj else data.get('careOfCo', 'PrimeTrade, LLC'),
    'lot_ref': release_obj.lot_ref if release_obj else None,  # Contains lot code + chemistry
}
```

### Data Flow
1. User clicks "Create BOL" for a pending load
2. Form submits with `loadId` parameter
3. Backend checks for `loadId` in preview request
4. If present, loads Release and Lot from database
5. Preview PDF uses release data instead of form data

### User Impact
- ✅ **Preview now matches actual BOL** exactly
- ✅ Shows correct c/o company for blind shipping
- ✅ Displays full lot chemistry (C, Si, S, P, Mn)
- ✅ Shows formatted release number (e.g., "60137-1")
- ✅ No more surprises between preview and final BOL

---

## Technical Debt & Future Considerations

### Release Detail Page
Currently, the combobox functionality is **only** on the Release Upload page. The Release Detail/Edit page (templates/release_detail.html) still uses plain text inputs for Customer ID and Carrier.

**Decision**: Leave as-is for now to focus on one workflow at a time. Can add later if needed.

### Database Constraints
The unique constraint on `release_number` is maintained. Deletion approach (vs update-in-place) chosen because:
- Cancelled releases are essentially abandoned data
- Associated loads need cleanup too
- Fresh start is clearer for audit purposes
- Simpler than trying to update all fields of existing cancelled release

### Preview Performance
The preview now makes an additional database query when `loadId` is present. This is acceptable because:
- Query uses `select_related` for efficient joins
- Preview is user-initiated (not a background job)
- Only happens when creating BOL from release (not standalone BOLs)

---

## Deployment Notes

### Database Migrations
No new migrations required - all changes use existing model fields.

### Environment Variables
No new environment variables.

### Dependencies
No new Python or npm packages.

### Testing Checklist
- [ ] Upload release PDF with new customer/carrier names
- [ ] Use combobox autocomplete to select existing entries
- [ ] Click "Add" button to create new customer via modal
- [ ] Verify Ship-To address auto-populates when customer selected
- [ ] Cancel a release and re-upload with same release number
- [ ] Create BOL from pending load and verify preview shows:
  - Correct c/o company (if using blind shipping)
  - Formatted release number (e.g., "60137-1")
  - Lot code (e.g., "CRT 050N711A")
  - Chemistry values (C, Si, S, P, Mn)

---

## Git Commits

1. **7a5782e** - Fix combobox dropdown to show all suggestions on click/focus
2. **90794d1** - Add care_of_co and lot_ref fields to BOL preview
3. **10429cb** - Allow re-creating cancelled releases with same release number
4. **0267b74** - Fix: Delete cancelled releases before re-creation to avoid unique constraint violation
5. **f2594d5** - Fix BOL preview to show release data (c/o company, lot, chemistry, release #)

---

## Related Documentation

- **Blind Shipping**: See `BLIND_SHIPPING_CONTEXT.md`, `BLIND_SHIPPING_QUICK_START.md`, `BLIND_SHIPPING_SUMMARY.md`
- **BOL System**: See `bol_system/models.py` for data model
- **Release Workflow**: See `static/releases.html` and `templates/release_detail.html`

---

## Author
Claude Code session with Clif
Date: November 20, 2025
