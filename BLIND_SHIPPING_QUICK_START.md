# Blind Shipping - Quick Implementation Guide

## What is Blind Shipping?
When a release number contains a delimiter (hyphen), the BOL PDF will show the **customer's name and address** as the shipper instead of "Cincinnati Barge & Rail Terminal, LLC". This hides CBRT from the carrier.

## Detection Logic
```python
# Add to: bol_system/utils.py (NEW FILE)

def parse_release_for_blind_shipping(release_number: str) -> dict:
    """
    Parse release number to determine if blind shipping is required.
    Rule: Any hyphen in release number triggers blind shipping.
    """
    if not release_number:
        return {'base': '', 'blind': False, 'suffix': '', 'full': ''}
    
    if '-' in release_number:
        parts = release_number.split('-', 1)
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

## PDF Generator Changes
```python
# Edit: bol_system/pdf_generator.py (around line 180)
# Replace the hardcoded shipper section with:

# Determine shipper based on blind shipping flag
shipper_name = "Cincinnati Barge & Rail Terminal, LLC"
shipper_address = "c/o PrimeTrade, LLC<br/>1707 Riverside Drive<br/>Cincinnati, Ohio 45202<br/>Phone: (513) 721-1707"

# Check for blind shipping via release number
if hasattr(data, 'release_number') and data.release_number:
    from .utils import parse_release_for_blind_shipping
    parsed = parse_release_for_blind_shipping(data.release_number)
    
    if parsed['blind']:
        # Blind shipping: Use consignee (customer) as shipper
        if hasattr(data, 'buyer_name') and data.buyer_name:
            shipper_name = data.buyer_name
        
        if hasattr(data, 'ship_to') and data.ship_to:
            shipper_address = data.ship_to.replace('\n', '<br/>')

# Then use in the table:
left_col_data = [
    [Paragraph('<b>SHIP FROM:</b>', header_style)],
    [Paragraph(f'<b>{shipper_name}</b><br/>{shipper_address}', normal_style)],
    [Spacer(1, 0.05*inch)],
    [Paragraph('<b>CONSIGNEE (SHIP TO):</b>', header_style)],
    [Paragraph(f'<b>{data.buyer_name}</b><br/><font size="7">{data.ship_to.replace(chr(10), "<br/>")}</font>', normal_style)]
]
```

## Test Cases
```bash
# 1. Create test release with delimiter
python manage.py shell
>>> from bol_system.models import Release, Customer
>>> customer = Customer.objects.first()
>>> release = Release.objects.create(
...     release_number="TEST-BLIND-001",
...     customer_id_text="Test Customer",
...     customer_ref=customer,
...     ship_to_street="123 Test St",
...     ship_to_city="Cincinnati",
...     ship_to_state="OH",
...     ship_to_zip="45202"
... )

# 2. Create BOL and verify
>>> from bol_system.pdf_generator import generate_bol_pdf
>>> # Create BOL via normal flow (will auto-populate release_number)
>>> # Then check PDF shows customer as shipper

# 3. Test utility function
>>> from bol_system.utils import parse_release_for_blind_shipping
>>> parse_release_for_blind_shipping("12345")
{'base': '12345', 'blind': False, 'suffix': '', 'full': '12345'}
>>> parse_release_for_blind_shipping("12345-BLIND")
{'base': '12345', 'blind': True, 'suffix': 'BLIND', 'full': '12345-BLIND'}
```

## Files to Create/Modify
1. **CREATE:** `bol_system/utils.py`
2. **EDIT:** `bol_system/pdf_generator.py` (lines ~180-188)
3. **CREATE (optional):** `bol_system/tests/test_blind_shipping.py`

## Rollback Plan
If issues arise, simply revert `pdf_generator.py` to hardcoded shipper. No database changes required.

## Key Data Points
- **BOL.release_number** stores the release number (e.g., "12345-BLIND-1")
- **BOL.buyer_name** stores customer/consignee name
- **BOL.ship_to** stores customer/consignee address (newline-separated)
- Both fields are **always populated** from Release when BOL is created

## Example Output

### Before (Normal Release "12345"):
```
SHIP FROM:
  Cincinnati Barge & Rail Terminal, LLC
  c/o PrimeTrade, LLC
  1707 Riverside Drive
  Cincinnati, Ohio 45202

CONSIGNEE:
  ACME Steel Corp
  123 Steel Way
  Pittsburgh, PA 15201
```

### After (Blind Release "12345-BLIND"):
```
SHIP FROM:
  ACME Steel Corp        ← Changed to customer
  123 Steel Way          ← Changed to customer address
  Pittsburgh, PA 15201

CONSIGNEE:
  ACME Steel Corp
  123 Steel Way
  Pittsburgh, PA 15201
```

## Ready to Code!
See `BLIND_SHIPPING_CONTEXT.md` for complete technical details.
