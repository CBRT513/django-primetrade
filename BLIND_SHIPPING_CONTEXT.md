# BLIND SHIPPING IMPLEMENTATION CONTEXT

## Executive Summary
This document provides complete context for implementing the blind shipping feature for the PrimeTrade customer. The feature will hide the actual shipper name on BOLs when a release number contains a delimiter (e.g., "12345-BLIND"), replacing it with the customer's name.

---

## 1. RELEASE MODEL (Release Intake System)

**File:** `bol_system/models.py` (lines 284-341)

### Release Model Fields:
```python
class Release(TimestampedModel):
    # Core identification
    release_number = models.CharField(max_length=20, unique=True, db_index=True)
    release_date = models.DateField(null=True, blank=True)
    
    # Customer information (text field - not validated FK)
    customer_id_text = models.CharField(max_length=200)  # e.g., "ST. MARYS"
    customer_po = models.CharField(max_length=100, blank=True)
    
    # Shipping information
    ship_via = models.CharField(max_length=200, blank=True)
    fob = models.CharField(max_length=200, blank=True)
    
    # Ship-To Address (stored as text fields)
    ship_to_name = models.CharField(max_length=200, blank=True)
    ship_to_street = models.CharField(max_length=200, blank=True)
    ship_to_street2 = models.CharField(max_length=200, blank=True)
    ship_to_city = models.CharField(max_length=100, blank=True)
    ship_to_state = models.CharField(max_length=2, blank=True)
    ship_to_zip = models.CharField(max_length=10, blank=True)
    
    # Material/Product information
    lot = models.CharField(max_length=100, blank=True)
    material_description = models.CharField(max_length=200, blank=True)
    
    # Normalized foreign key references (for database integrity)
    customer_ref = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    ship_to_ref = models.ForeignKey('CustomerShipTo', on_delete=models.SET_NULL, null=True, blank=True)
    carrier_ref = models.ForeignKey(Carrier, on_delete=models.SET_NULL, null=True, blank=True)
    lot_ref = models.ForeignKey('Lot', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Quantity and status
    quantity_net_tons = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="OPEN")
    
    # Critical delivery instructions (appears on BOL)
    special_instructions = models.TextField(blank=True)
```

### Key Insight: Release Number Format
- Release numbers are stored as-is in `release_number` field
- Examples: `"12345"`, `"12345-BLIND"`, `"67890-XYZ"`
- **NO current parsing logic exists** - release numbers are treated as opaque strings
- When BOL is created from a load, format is: `{release.release_number}-{load.seq}` (line 704 in views.py)

---

## 2. BOL MODEL (Bill of Lading)

**File:** `bol_system/models.py` (lines 136-195)

### BOL Model Fields Related to Shipping:
```python
class BOL(TimestampedModel):
    bol_number = models.CharField(max_length=20, unique=True, db_index=True)
    
    # Product information
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=200)  # Denormalized for PDF
    
    # Customer/Consignee (text copies for immutability)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    buyer_name = models.CharField(max_length=200)  # CONSIGNEE NAME
    ship_to = models.TextField()  # CONSIGNEE ADDRESS (multiline)
    customer_po = models.CharField(max_length=100, blank=True)
    
    # Carrier information (text copies for immutability)
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE)
    carrier_name = models.CharField(max_length=200)
    truck = models.ForeignKey(Truck, on_delete=models.CASCADE, null=True, blank=True)
    truck_number = models.CharField(max_length=50)
    trailer_number = models.CharField(max_length=50)
    
    # Weight and date
    date = models.CharField(max_length=20)
    net_tons = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Release linkage (critical for blind shipping logic)
    release_number = models.CharField(max_length=20, blank=True, help_text='Release number for reference')
    lot_ref = models.ForeignKey('Lot', on_delete=models.SET_NULL, null=True, blank=True)
    special_instructions = models.TextField(blank=True)
    
    # Official weight tracking
    official_weight_tons = models.DecimalField(...)
    # ... (weight variance fields)
```

### Current Data Flow (Release → BOL):
**File:** `bol_system/views.py` (lines 670-706)

```python
# When creating BOL from ReleaseLoad:
if release_load:
    buyer_name = getattr(customer, 'customer', None) or release_obj.customer_id_text
    # Build ship-to address
    addr_parts = [release_obj.ship_to_name, release_obj.ship_to_street]
    if release_obj.ship_to_street2:
        addr_parts.append(release_obj.ship_to_street2)
    city_line = ", ".join([p for p in [release_obj.ship_to_city, release_obj.ship_to_state] if p])
    zip_part = f" {release_obj.ship_to_zip}" if release_obj.ship_to_zip else ''
    addr_parts.append(f"{city_line}{zip_part}".strip())
    ship_to_text = "\n".join([p for p in addr_parts if p]).strip()
    customer_po = release_obj.customer_po or ''

# BOL is created with:
bol = BOL.objects.create(
    # ... product fields ...
    buyer_name=buyer_name,           # Customer name (consignee)
    ship_to=ship_to_text,           # Customer address (consignee)
    # ... carrier/truck fields ...
    release_number=f'{release_obj.release_number}-{release_load.seq}',  # e.g. "12345-BLIND-1"
    special_instructions=release_obj.special_instructions
)
```

---

## 3. CUSTOMER MODEL (Shipper/Consignee Data)

**File:** `bol_system/models.py` (lines 47-75)

### Customer Model:
```python
class Customer(TimestampedModel):
    customer = models.CharField(max_length=200, unique=True)  # Company name
    address = models.CharField(max_length=200)
    address2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    zip = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)
    
    # Dashboard branding (not relevant to BOL generation)
    logo_url = models.URLField(...)
    primary_color = models.CharField(...)
    secondary_color = models.CharField(...)
    
    @property
    def full_address(self):
        address_lines = [self.address]
        if self.address2:
            address_lines.append(self.address2)
        address_lines.append(f"{self.city}, {self.state} {self.zip}")
        return "\n".join(address_lines)
```

### CustomerShipTo Model:
```python
class CustomerShipTo(TimestampedModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='ship_tos')
    name = models.CharField(max_length=200, blank=True)
    street = models.CharField(max_length=200)
    street2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    zip = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)
```

---

## 4. BOL PDF GENERATION (ReportLab)

**File:** `bol_system/pdf_generator.py`

### Current "SHIP FROM" Section (lines 182-188):
```python
# LEFT COLUMN - HARDCODED SHIPPER
left_col_data = [
    [Paragraph('<b>SHIP FROM:</b>', header_style)],
    [Paragraph(
        '<b>Cincinnati Barge & Rail Terminal, LLC</b><br/>'
        'c/o PrimeTrade, LLC<br/>'
        '1707 Riverside Drive<br/>'
        'Cincinnati, Ohio 45202<br/>'
        'Phone: (513) 721-1707',
        normal_style
    )],
    [Spacer(1, 0.05*inch)],
    [Paragraph('<b>CONSIGNEE (SHIP TO):</b>', header_style)],
    [Paragraph(
        f'<b>{data.buyer_name}</b><br/>'
        f'<font size="7">{data.ship_to.replace(chr(10), "<br/>")}</font>',
        normal_style
    )]
]
```

### Current "SHIP TO" (Consignee) Section:
- Uses `data.buyer_name` for bold consignee name
- Uses `data.ship_to` for multiline address
- Both come from BOL model fields populated during creation

### PDF Generation Entry Point:
**Function:** `generate_bol_pdf(bol_data, output_path=None)`
- Accepts either BOL model object OR dictionary
- Uses `DictWrapper` class to normalize field access
- Returns S3 URL or local file path

---

## 5. PROPOSED IMPLEMENTATION STRATEGY

### A. Release Number Pattern Detection

**Location to add:** New utility function in `bol_system/models.py` or new `bol_system/utils.py`

```python
def parse_release_for_blind_shipping(release_number: str) -> dict:
    """
    Parse release number to determine if blind shipping is required.
    
    Examples:
        "12345" -> {"base": "12345", "blind": False}
        "12345-BLIND" -> {"base": "12345", "blind": True, "suffix": "BLIND"}
        "12345-XYZ" -> {"base": "12345", "blind": True, "suffix": "XYZ"}
    
    Rule: If release contains hyphen, enable blind shipping
    """
    if '-' in release_number:
        parts = release_number.split('-', 1)  # Split on first hyphen only
        return {
            'base': parts[0],
            'blind': True,
            'suffix': parts[1] if len(parts) > 1 else '',
            'full': release_number
        }
    return {
        'base': release_number,
        'blind': False,
        'suffix': '',
        'full': release_number
    }
```

### B. BOL Model Enhancement (OPTIONAL)

Add computed property to BOL model:
```python
@property
def is_blind_shipping(self) -> bool:
    """Determine if this BOL requires blind shipping based on release number."""
    if not self.release_number:
        return False
    parsed = parse_release_for_blind_shipping(self.release_number)
    return parsed['blind']

@property
def shipper_name_for_bol(self) -> str:
    """Return appropriate shipper name based on blind shipping status."""
    if self.is_blind_shipping and self.customer:
        # Use customer/consignee name as shipper for blind shipping
        return self.customer.customer
    return "Cincinnati Barge & Rail Terminal, LLC"

@property
def shipper_address_for_bol(self) -> str:
    """Return appropriate shipper address based on blind shipping status."""
    if self.is_blind_shipping and self.customer:
        # Use customer address as shipper for blind shipping
        return self.customer.full_address
    return "c/o PrimeTrade, LLC\n1707 Riverside Drive\nCincinnati, Ohio 45202\nPhone: (513) 721-1707"
```

### C. PDF Generator Modification

**File:** `bol_system/pdf_generator.py` (lines 182-188)

**BEFORE:**
```python
left_col_data = [
    [Paragraph('<b>SHIP FROM:</b>', header_style)],
    [Paragraph(
        '<b>Cincinnati Barge & Rail Terminal, LLC</b><br/>'
        'c/o PrimeTrade, LLC<br/>'
        '1707 Riverside Drive<br/>'
        'Cincinnati, Ohio 45202<br/>'
        'Phone: (513) 721-1707',
        normal_style
    )],
```

**AFTER:**
```python
# Determine shipper based on blind shipping flag
shipper_name = "Cincinnati Barge & Rail Terminal, LLC"
shipper_address = "c/o PrimeTrade, LLC<br/>1707 Riverside Drive<br/>Cincinnati, Ohio 45202<br/>Phone: (513) 721-1707"

# Check for blind shipping via release number
if hasattr(data, 'release_number') and data.release_number:
    from .utils import parse_release_for_blind_shipping  # or inline the logic
    parsed = parse_release_for_blind_shipping(data.release_number)
    
    if parsed['blind']:
        # Blind shipping: Use consignee (customer) as shipper
        if hasattr(data, 'buyer_name') and data.buyer_name:
            shipper_name = data.buyer_name
        
        if hasattr(data, 'ship_to') and data.ship_to:
            # ship_to is already newline-separated text, convert to <br/>
            shipper_address = data.ship_to.replace('\n', '<br/>')

left_col_data = [
    [Paragraph('<b>SHIP FROM:</b>', header_style)],
    [Paragraph(
        f'<b>{shipper_name}</b><br/>{shipper_address}',
        normal_style
    )],
```

---

## 6. CRITICAL CONSIDERATIONS

### A. Data Availability Check
- BOL must have `customer` FK populated for blind shipping to work
- BOL must have `buyer_name` and `ship_to` fields (these are always populated from release)
- **Current BOL creation flow DOES populate these** (see views.py lines 670-706)

### B. Release Number Format Assumptions
**QUESTION FOR CUSTOMER:**
1. What delimiter indicates blind shipping? (Currently assuming: any hyphen)
2. Examples of non-blind releases: `"12345"`, `"ABC123"`
3. Examples of blind releases: `"12345-BLIND"`, `"12345-XYZ"`
4. Should suffix matter? Or is presence of hyphen enough?

**Recommended Rule:** ANY hyphen in release number triggers blind shipping

### C. Existing Release Numbers
**ACTION REQUIRED:** Query database to see current release number patterns
```bash
python manage.py shell
>>> from bol_system.models import Release
>>> Release.objects.values_list('release_number', flat=True).distinct()
```

### D. BOL Regeneration
- Existing BOLs can be regenerated with `regenerate_bol_pdf` endpoint (views.py line 1684)
- **IMPORTANT:** This will apply new blind shipping logic to old BOLs if release_number contains hyphen
- May need migration strategy for historical BOLs

### E. Preview Functionality
- BOL preview endpoint exists (views.py line 472)
- Preview uses dictionary data, not saved BOL
- **Must ensure preview flow also respects blind shipping logic**

---

## 7. TESTING CHECKLIST

### Unit Tests Needed:
1. `test_parse_release_for_blind_shipping()`
   - No hyphen: `"12345"` → blind=False
   - With hyphen: `"12345-BLIND"` → blind=True
   - Multiple hyphens: `"12345-ABC-XYZ"` → blind=True, suffix="ABC-XYZ"

2. `test_bol_blind_shipping_properties()`
   - BOL with release "12345" → is_blind_shipping=False
   - BOL with release "12345-BLIND" → is_blind_shipping=True
   - BOL without release_number → is_blind_shipping=False

3. `test_pdf_generation_blind_shipping()`
   - Generate PDF with blind release → verify shipper = consignee
   - Generate PDF with normal release → verify shipper = CBRT
   - Generate preview with blind release → verify same behavior

### Integration Tests:
1. Create release with "12345-BLIND"
2. Create BOL from that release
3. Generate PDF
4. Verify "SHIP FROM" section contains customer name/address

### Manual Testing:
1. Upload release PDF with delimiter in release number
2. Create BOL from pending load
3. Download PDF and verify shipper name

---

## 8. FILES TO MODIFY

### Primary Changes:
1. **`bol_system/utils.py`** (NEW FILE)
   - Add `parse_release_for_blind_shipping()` function

2. **`bol_system/pdf_generator.py`** (lines 182-188)
   - Modify "SHIP FROM" section to use conditional logic

### Optional Enhancements:
3. **`bol_system/models.py`** (BOL model)
   - Add `is_blind_shipping` property
   - Add `shipper_name_for_bol` property
   - Add `shipper_address_for_bol` property

4. **`bol_system/tests/test_blind_shipping.py`** (NEW FILE)
   - Comprehensive unit and integration tests

---

## 9. ROLLOUT PLAN

### Phase 1: Detection Logic (Low Risk)
- Add utility function for release parsing
- Add BOL model properties
- Deploy and verify detection works correctly
- **No visual changes yet**

### Phase 2: PDF Generation (Medium Risk)
- Modify PDF generator to use conditional shipper
- Test thoroughly with preview endpoint
- Deploy to staging
- Generate test BOLs for both blind and non-blind releases

### Phase 3: Validation & Documentation
- Update user documentation
- Train staff on new feature
- Monitor BOL generation logs for any issues
- Add audit log entry when blind shipping is used

---

## 10. EXAMPLE SCENARIOS

### Scenario 1: Normal Release (No Delimiter)
```
Release Number: "12345"
Customer: "ACME Steel Corp"

BOL Generated:
  SHIP FROM: Cincinnati Barge & Rail Terminal, LLC
             c/o PrimeTrade, LLC
             1707 Riverside Drive
             Cincinnati, Ohio 45202
  
  CONSIGNEE: ACME Steel Corp
             123 Steel Way
             Pittsburgh, PA 15201
```

### Scenario 2: Blind Shipping Release (With Delimiter)
```
Release Number: "12345-BLIND"
Customer: "ACME Steel Corp"

BOL Generated:
  SHIP FROM: ACME Steel Corp          ← CUSTOMER NAME
             123 Steel Way             ← CUSTOMER ADDRESS
             Pittsburgh, PA 15201
  
  CONSIGNEE: ACME Steel Corp
             123 Steel Way
             Pittsburgh, PA 15201
```

**Result:** Carrier sees ACME Steel Corp as shipper AND consignee, hiding CBRT entirely.

---

## 11. SECURITY & COMPLIANCE NOTES

### Audit Trail
- Log when blind shipping is triggered
- Track which release numbers use blind shipping
- Ensure audit log captures BOL regeneration events

### Data Integrity
- Release number is immutable once created
- BOL stores `release_number` for historical reference
- PDF can be regenerated at any time using current logic

### Customer Privacy
- This feature ENHANCES privacy for PrimeTrade's customer
- No additional PII is exposed
- Carrier only sees what customer wants them to see

---

## READY TO IMPLEMENT

**Confidence Level:** HIGH
- All data structures are well understood
- PDF generation is clean and modular
- Release number field is available on BOL
- Customer name/address already populated from release

**Estimated Effort:** 2-4 hours
- 1 hour: Write utility function and BOL properties
- 1 hour: Modify PDF generator
- 1-2 hours: Write tests and validate

**Risk Level:** LOW
- Changes isolated to PDF generation
- Backward compatible (no DB schema changes)
- Easy to test with preview endpoint
- Can be rolled back instantly if needed
