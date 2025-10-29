import re
from typing import Any, Dict, List

from pypdf import PdfReader


DATE_SLASH = r"\d{2}/\d{2}/\d{4}"
DATE_DASH = r"\d{2}-\d{2}-\d{2}"


def _find(pattern: str, text: str, flags: int = re.IGNORECASE) -> str | None:
    m = re.search(pattern, text, flags)
    if not m:
        return None
    # If the regex has a capturing group, return it; otherwise return the full match
    try:
        # m.re.groups is the number of capturing groups in the pattern
        if getattr(m, 're', None) and getattr(m.re, 'groups', 0) >= 1:
            return m.group(1).strip()
        # Fallback to full match when no capturing group present
        return m.group(0).strip()
    except Exception:
        # Absolute fallback – never raise for missing group
        return m.group(0).strip()


def parse_release_text(text: str) -> Dict[str, Any]:
    """Parse release order text extracted from a customer PDF.

    Returns a normalized dict with release header, material, schedule, and notes.
    The parser is rule/regex-based and tuned for the provided examples.
    """
    # Normalize spaces
    t = re.sub(r"\u00a0", " ", text)

    # Header fields
    release_no = _find(r"Release\s*#\s*[:\-]?\s*(\d+)", t)
    # Allow optional colon and flexible spacing
    release_date = (
        _find(r"Release\s*Date\s*[:\-]?\s*(%s)" % DATE_SLASH, t)
        or _find(r"Date\s*[:\-]?\s*(%s)" % DATE_SLASH, t)
    )
    # Customer name/ID variations
    customer_id = (
        _find(r"Customer\s*(?:ID|Name)?\s*[:\-]?\s*([A-Za-z0-9 .,&'\-/]+)", t)
        or _find(r"Customer\s*:\s*([A-Za-z0-9 .,&'\-/]+)", t)
    )

    # Ship Via and FOB - allow colon and line ends
    ship_via = (
        _find(r"Ship\s*Via\s*[:\-]?\s*([^\n]+?)(?:\s+FOB|\n)", t)
    )
    fob = (
        _find(r"FOB\s*[:\-]?\s*([^\n]+?)(?:\s+Customer\s*P\.?O\.?|\n)", t)
        or _find(r"FOB\s*[:\-]?\s*([^\n]+)", t)
    )
    # Customer PO variants: PO, P.O., with/without '#'
    customer_po = _find(r"Customer\s*P\.?O\.?\s*(?:#\s*)?[:\-]?\s*(\S+)", t)

    # Fallback: header row with values on next line
    hdr = re.search(r"^\s*Release\s*Date\s+Ship\s*Via\s+FOB\s+Customer\s*P\.?O\.?\s*#\s*$\n([^\n]+)", t, re.I | re.M)
    if hdr:
        row = hdr.group(1).strip()
        # 1) Date
        dm = re.search(DATE_SLASH, row)
        if dm:
            release_date = dm.group(0)
            rest = row[dm.end():].strip()
        else:
            rest = row
        # 2) FOB token and Ship Via (text between date and FOB)
        fob_m = re.search(r"\b(Origin|Destination)\b", rest, re.I)
        if fob_m:
            fob = fob_m.group(1).title()
            pre = rest[:fob_m.start()].strip()
            if pre:
                ship_via = pre
            rest_after_fob = rest[fob_m.end():].strip()
        else:
            rest_after_fob = rest
        # 3) Customer PO (digits, even when glued to next word)
        po_m = re.search(r"(\d{4,})(?=\D|$)", rest_after_fob)
        if po_m:
            customer_po = po_m.group(1)
            name_after = rest_after_fob[po_m.end():].lstrip(" -:#")
        else:
            name_after = rest_after_fob
        # 4) Ship-To name from the remainder (first words; stop at obvious noise)
        ship_to_name = re.sub(r"\s{2,}", " ", name_after).strip()
        ship_to_name = re.sub(r"\bRelease\s*#:?.*$", "", ship_to_name, flags=re.I)

    # Customer ID fallback near label
    if not customer_id:
        cid_inline = re.search(r"Customer\s*ID\s*:\s*([^\n\r]+)", t, re.I)
        if cid_inline and cid_inline.group(1).strip():
            customer_id = cid_inline.group(1).strip()
        else:
            # Look for an all-caps token appearing after a ZIP code in the Ship-To area
            ship_block_for_id = re.search(r"Ship To:[\s\S]{0,400}", t, re.I)
            if ship_block_for_id:
                seg = ship_block_for_id.group(0)
                caps = re.search(r"\b\d{5}\s*([A-Z][A-Z .,&'\-]{3,})\b", seg)
                if caps:
                    customer_id = caps.group(1).strip()

    # Ship To block: capture until the next major header
    ship_to_block = _find(r"Ship To:\s*([\s\S]*?)(?:\n\s*(?:Release\s*#|Release\s*Date|Approx\.|Please\s+deliver|Shipper:))", t)
    ship_to = {}
    if ship_to_block:
        # First line is name; subsequent lines compose address
        lines = [ln.strip() for ln in ship_to_block.splitlines() if ln.strip()]
        if lines:
            ship_to["name"] = lines[0]
        if len(lines) > 1:
            # Clean trailing CUSTOMER ID tokens accidentally glued to the city/ZIP line
            cleaned = []
            for i, ln in enumerate(lines[1:]):
                if i == 0:
                    ln = re.sub(r"(\b\d{5}\b)\s*[A-Z][A-Z .,&'\-]{3,}$", r"\1", ln)
                cleaned.append(ln)
            ship_to["address"] = ", ".join(cleaned)

    # Material row
    lot = (
        _find(r"\bCRT\s+([A-Za-z0-9-]+)\s+NT\b", t)
        or _find(r"\b([A-Z]{3}\s*\S+)\s+NODULAR PIG IRON", t)
        or _find(r"Lot\s*Number\s*\n([\S ]+)", t)
    )
    desc = "NODULAR PIG IRON" if re.search(r"NODULAR\s+PIG\s+IRON", t, re.I) else None
    qty = (
        _find(r"Approx\.?\s*Quantity[\s\S]{0,200}?(\d+\.\d{3})", t)
        or _find(r"(?mi)^\s*(\d+\.\d{3})\s+CRT\b", t)
        or _find(r"(\d+\.\d{3})[\s\S]{0,40}?\bNT\b", t)
    )

    # Analysis primary line
    c = _find(r"\bC\s*(\d+\.\d+)", t)
    si = _find(r"\bSi\s*(\d+\.\d+)", t)
    s = _find(r"\bS\s*(\d+\.\d+)", t)
    p = _find(r"\bP\s*(\d+\.\d+)", t)
    mn = _find(r"\bMn\s*(\d+\.\d+)", t)

    analysis: Dict[str, float] = {}
    for k, v in [("C", c), ("Si", si), ("S", s), ("P", p), ("Mn", mn)]:
        if v is not None:
            try:
                analysis[k] = float(v)
            except ValueError:
                pass

    # Optional microelements (appear in MINSTER)
    cr = _find(r"\bCR\s*(\d+\.\d+)", t)
    ti = _find(r"\bTI\s*(\d+\.\d+)", t)
    v = _find(r"\bV\s*(\d+\.\d+)", t)
    extras = {}
    for k, val in [("Cr", cr), ("Ti", ti), ("V", v)]:
        if val:
            try:
                extras[k] = float(val)
            except ValueError:
                pass

    # Warehouse/location and carrier from Ship Via (if it's a known carrier phrase)
    warehouse_name = _find(r"Warehouse\s*\n\s*([A-Z]{3})", t) or _find(r"\bWarehouse\b[\s\S]*?\b(CRT)\b", t)
    warehouse_loc = _find(r"\bCINCINNATI\b", t)

    # If we derived ship_to_name earlier from header row, prefer it
    try:
        if 'ship_to_name' in locals():
            if not ship_to.get('name') or 'Release Date' in ship_to.get('name', ''):
                ship_to['name'] = ship_to_name
    except Exception:
        pass

    # Schedule lines (e.g., "Deliver 11-05-25 Load #1")
    sched: List[Dict[str, str]] = []
    for m in re.finditer(r"(?:\d+\s*TL\s*)?Deliver\s*(%s)\s*(?:LOAD|Load)\s*#?\s*(\d+)" % DATE_DASH, t, re.I):
        ds, num = m.group(1), m.group(2)
        # Convert YY to YYYY (assume 20YY)
        mm, dd, yy = ds.split("-")
        date_iso = f"20{yy}-{mm}-{dd}"
        sched.append({"date": date_iso, "load": int(num)})

    # Carrier: often Ship Via contains '<Carrier> Trucking'
    carrier = None
    if ship_via:
        carrier = ship_via.strip()

    # Notes snippets to echo to BOL requirements
    bol_requirements: List[str] = []
    for phrase in [
        r"free of radioactive contamination",
        r"Analysis\s*&\s*PO must be on BOL",
        r"SEND TO THE FOUNDRY",
        r"Do\s*NOT\s*exceed\s*max(imum)?\s*legal",
        r"Trucks?\s+must\s+be\s+TARPED",
        r"Material\s*#\s*\S+",
        r"P\.O\.\s*#\s*\S+",
    ]:
        m = re.search(phrase, t, re.I)
        if m:
            bol_requirements.append(m.group(0))

    result: Dict[str, Any] = {
        "releaseNumber": release_no,
        "customerId": customer_id,
        "customerPO": customer_po,
        "releaseDate": release_date,
        "shipVia": ship_via,
        "fob": fob,
        "shipToRaw": ship_to,
        "material": {
            "lot": lot,
            "description": desc,
            "analysis": analysis,
            "extraBOLAnalysis": extras or None,
        },
        "warehouse": {"name": warehouse_name or "CRT", "location": "CINCINNATI" if warehouse_loc else None},
        "quantityNetTons": float(qty) if qty else None,
        "schedule": sched,
        "carrier": carrier,
        "bolRequirements": bol_requirements,
        "rawTextPreview": text[:1000],
    }

    return result


def parse_release_pdf(file_obj) -> Dict[str, Any]:
    """Extract text from a PDF file-like and parse it."""
    reader = PdfReader(file_obj)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return parse_release_text(text)