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
    release_no = _find(r"Release\s*#:\s*(\d+)", t)
    release_date = _find(r"Release\s*Date\s+(%s)" % DATE_SLASH, t)
    customer_id = _find(r"Customer\s*ID\s*:\s*([A-Z0-9 .,&'-]+)", t)

    ship_via = _find(r"Ship\s*Via\s+([^\n]+?)\s+FOB", t)
    fob = _find(r"FOB\s+([^\n]+?)\s+Customer PO #", t) or _find(r"FOB\s+([^\n]+)", t)
    customer_po = _find(r"Customer PO\s*#\s*(\S+)", t)

    # Ship To block: take the first block after 'Ship To:'
    ship_to_block = _find(r"Ship To:\s*([\s\S]*?)\n\s*Release Date", t)
    ship_to = {}
    if ship_to_block:
        # First line is name; subsequent lines compose address
        lines = [ln.strip() for ln in ship_to_block.splitlines() if ln.strip()]
        if lines:
            ship_to["name"] = lines[0]
        if len(lines) > 1:
            ship_to["address"] = ", ".join(lines[1:])

    # Material row
    lot = _find(r"\b([A-Z]{3}\s*\S+)\s+NODULAR PIG IRON", t) or _find(r"Lot\s*Number\s*\n([\S ]+)", t)
    desc = "NODULAR PIG IRON" if re.search(r"NODULAR\s+PIG\s+IRON", t, re.I) else None
    qty = _find(r"Approx\.?\s*Quantity[\s\S]*?(\d+\.\d+)\s*NT", t)

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

    # Schedule lines
    sched: List[Dict[str, str]] = []
    for m in re.finditer(r"\b1\s*TL\s*Deliver\s*(%s)\s*(?:LOAD|Load|Load)\s*#?\s*(\d+)" % DATE_DASH, t):
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