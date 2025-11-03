import re
from typing import Any, Dict, List

from pypdf import PdfReader
from .ai_parser import (
    ai_parse_release_text,
    remote_ai_parse_release_text,
    gemini_filter_critical_instructions,
)


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
            # Remove customer token appended after ZIP (e.g., '45885ST. MARYS')
            cleaned = []
            for ln in lines[1:]:
                ln = re.sub(r"(\b\d{5})(?:\s*[A-Z][A-Z .,&'\-]{1,})?$", r"\1", ln)
                cleaned.append(ln)
            ship_to["address"] = ", ".join(cleaned)

    # Material row
    lot = (
        _find(r"\b(CRT\s+[A-Za-z0-9-]+)\s+NT\b", t)
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
            # Derive a clean address from the lines following the name
            if ship_to.get('name') and (not ship_to.get('address') or re.search(r"Release\s*Date|^\s*\d{2}/\d{2}/\d{4}|Release\s*#", ship_to.get('address',''), re.I)):
                name_idx = t.lower().find(ship_to['name'].lower())
                if name_idx != -1:
                    tail = t[name_idx: name_idx + 600]
                    # Split into lines, skip first (the name)
                    lines = [ln.strip() for ln in tail.splitlines()[1:] if ln.strip()]
                    cleaned = []
                    for ln in lines:
                        if re.search(r"^(Release\s*#|Shipper:|Please\s+deliver|Charlotte,\s*NC|^\d{2}/\d{2}/\d{4})", ln, re.I):
                            break
                        # Trim trailing uppercase customer token after ZIP (allow spaces)
                        ln_cleaned = re.sub(r"(\b\d{5})(?:\s*[A-Z][A-Z .,&'\-]{1,})?$", r"\1", ln)
                        cleaned.append(ln_cleaned)
                        # Stop after we've captured City, State ZIP (complete address)
                        if re.search(r"[A-Za-z]+,\s*[A-Z]{2}\s+\d{5}", ln_cleaned):
                            break
                    if cleaned:
                        ship_to['address'] = ", ".join(cleaned)
            # Customer ID: look after ZIP in the Ship-To block
            def _is_placeholder(val: str | None) -> bool:
                return isinstance(val, str) and val.strip().upper() in {"SHIP TO", "CUSTOMER ID", "N/A"}
            if (not customer_id or _is_placeholder(customer_id)) and ship_to.get('name'):
                window = t[name_idx: name_idx + 300] if name_idx != -1 else t
                m = re.search(r"\b\d{5}\s*([A-Z][A-Z .,&'\-]{2,})", window)
                if m:
                    customer_id = m.group(1).strip()
    except Exception:
        pass

    # Schedule lines (e.g., "Deliver 11-05-25 Load #1" or "1 TL 11/04/25 LOAD #1")
    sched: List[Dict[str, str]] = []
    # Pattern handles both dash (11-05-25) and slash (11/04/25) formats
    DATE_SHORT = r"\d{2}[-/]\d{2}[-/]\d{2}"
    # Make "Deliver" optional to handle formats like "1 TL 11/04/25 LOAD #1"
    for m in re.finditer(r"(?:\d+\s*TL\s*)?(?:Deliver\s*)?(%s)\s*(?:LOAD|Load)\s*#?\s*(\d+)" % DATE_SHORT, t, re.I):
        ds, num = m.group(1), m.group(2)
        # Convert YY to YYYY (assume 20YY), handle both - and / separators
        parts = re.split(r'[-/]', ds)
        if len(parts) == 3:
            mm, dd, yy = parts
            date_iso = f"20{yy}-{mm}-{dd}"
            sched.append({"date": date_iso, "load": int(num)})

    # Carrier: often Ship Via contains '<Carrier> Trucking'
    carrier = None
    if ship_via:
        carrier = ship_via.strip()

    # Warehouse section - extract full text for special_instructions
    warehouse_section = None
    try:
        # Match entire Warehouse:/Warehouse requirements: section until next major section or end
        sec = re.search(
            r"Warehouse\s*(?:requirements)?\s*:\s*([\s\S]*?)(?=\n\s*(?:Trucking\s*(?:requirements)?\s*:|SPECIAL\s+INSTRUCTIONS\s*:|Ship\s+From\s*:)|$)",
            t,
            re.I
        )
        if sec:
            warehouse_section = sec.group(1).strip()
    except Exception:
        pass

    # Warehouse requirements bullets (prefer exact section parsing)
    bol_requirements: List[str] = []
    try:
        sec = re.search(r"Warehouse\s+requirements\s*:\s*([\s\S]*?)(?:\n\s*(Trucking\s+requirements|Please\s+deliver|$))", t, re.I)
        if sec:
            block = sec.group(1)
            lines = [ln.rstrip() for ln in block.splitlines()]
            current = None
            for ln in lines:
                if not ln.strip():
                    continue
                if ln.strip().startswith('-'):
                    if current:
                        bol_requirements.append(current.strip(' -'))
                    current = ln.strip()[1:].strip()
                else:
                    # continuation of previous bullet (wrapped line)
                    if current:
                        current += ' ' + ln.strip()
            if current:
                bol_requirements.append(current.strip(' -'))
        # Normalize common variants
        normed = []
        for s in bol_requirements:
            s = re.sub(r"\s+", " ", s).strip()
            # Fix split sentence for certification line
            m = re.search(r"Put this statement on BOL:.*free of radioactive contamination", s, re.I)
            if m:
                s = m.group(0)
            normed.append(s)
        bol_requirements = normed
    except Exception:
        pass

    # Fallback: look for phrases if section parsing failed
    if not bol_requirements:
        for phrase in [
            r"Put this statement on BOL:.*free of radioactive contamination",
            r"free of radioactive contamination",
            r"Analysis\s*&\s*PO must be on BOL",
            r"SEND TO THE FOUNDRY",
            r"Do\s*NOT\s*exceed\s*max(imum)?\s*legal",
            r"Trucks?\s+must\s+be\s+TARPED",
            r"Material\s*#\s*\S+",
            r"P\.O\.\s*#\s*\S+",
            r"SHIPPER:\s*Primetrade,?\s*LLC",
        ]:
            m = re.search(phrase, t, re.I | re.S)
            if m:
                bol_requirements.append(re.sub(r"\s+", " ", m.group(0)).strip())

    # Parse ship-to address into components for easier frontend handling
    def _parse_shipto_address(addr: str | None) -> Dict[str, str]:
        """Split combined address into street, street2, city, state, zip"""
        if not addr:
            return {}

        # Split by comma
        parts = [p.strip() for p in addr.split(',')]
        parsed = {}

        # Last part should be "City, ST ZIP" or just "ST ZIP"
        if parts:
            last = parts[-1].strip()
            # Try to extract State ZIP from last part
            m = re.match(r'^([A-Za-z ]+)?\s*([A-Z]{2})\s+(\d{5})$', last)
            if m:
                city_from_last, state, zip_code = m.groups()
                parsed['state'] = state
                parsed['zip'] = zip_code
                if city_from_last:
                    parsed['city'] = city_from_last.strip()
                parts = parts[:-1]  # Remove last part

        # If we didn't get city from last part, try second-to-last
        if 'city' not in parsed and parts:
            parsed['city'] = parts[-1].strip()
            parts = parts[:-1]

        # Remaining parts are street address lines
        if parts:
            parsed['street'] = parts[0].strip()
        if len(parts) > 1:
            parsed['street2'] = ', '.join(parts[1:]).strip()

        return parsed

    # Enhance ship_to with parsed components
    if ship_to and ship_to.get('address'):
        parsed_addr = _parse_shipto_address(ship_to['address'])
        ship_to.update(parsed_addr)

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
        "specialInstructions": warehouse_section,
        "rawTextPreview": text[:1000],
    }

    return result


def parse_release_pdf(file_obj, ai_mode: str | None = None) -> Dict[str, Any]:
    """Extract text from a PDF file-like and parse it.

    ai_mode: 'local' for Ollama on localhost, 'cloud' for managed API (Groq), or None.
    """
    reader = PdfReader(file_obj)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    parsed = parse_release_text(text)

    if ai_mode in ("local", "cloud"):
        def _is_bad_value(s: Any) -> bool:
            if s is None:
                return True
            if isinstance(s, str):
                lab = s.strip().upper()
                return lab in {"", "SHIP TO", "CUSTOMER ID", "N/A"}
            return False

        def _addr_contaminated(addr: str) -> bool:
            if not isinstance(addr, str):
                return True
            return bool(re.search(r"Release\s*Date|Ship\s*Via|Customer\s*PO|^\s*\d{2}/\d{2}/\d{4}|Release\s*#", addr, re.I))

        need = any(
            _is_bad_value(parsed.get(k))
            for k in ["customerId", "customerPO", "releaseDate", "shipToRaw"]
        ) or _addr_contaminated((parsed.get("shipToRaw") or {}).get("address", ""))

        if need:
            ai = ai_parse_release_text(text) if ai_mode == "local" else remote_ai_parse_release_text(text)
            if isinstance(ai, dict):
                if _is_bad_value(parsed.get("releaseDate")) and ai.get("releaseDate"):
                    parsed["releaseDate"] = ai.get("releaseDate")
                if _is_bad_value(parsed.get("customerId")) and ai.get("customerId"):
                    parsed["customerId"] = ai.get("customerId")
                if _is_bad_value(parsed.get("customerPO")) and ai.get("customerPO"):
                    parsed["customerPO"] = ai.get("customerPO")
                if _is_bad_value(parsed.get("shipVia")) and ai.get("shipVia"):
                    parsed["shipVia"] = ai.get("shipVia")
                if _is_bad_value(parsed.get("fob")) and ai.get("fob"):
                    parsed["fob"] = ai.get("fob")
                # Ship To
                ai_ship = ai.get("shipTo") if isinstance(ai.get("shipTo"), dict) else None
                if ai_ship and (_is_bad_value(parsed.get("shipToRaw")) or _addr_contaminated((parsed.get("shipToRaw") or {}).get("address", ""))):
                    parsed["shipToRaw"] = ai_ship
                # Material
                if not parsed.get("material", {}).get("lot") and isinstance(ai.get("material"), dict):
                    parsed.setdefault("material", {})
                    parsed["material"].setdefault("description", ai.get("material", {}).get("description"))
                    parsed["material"]["lot"] = ai.get("material", {}).get("lot")
                # Quantity
                parsed["quantityNetTons"] = parsed.get("quantityNetTons") or ai.get("quantityNetTons")
                # Schedule
                if not parsed.get("schedule") and isinstance(ai.get("schedule"), list):
                    iso_sched = []
                    for row in ai.get("schedule"):
                        try:
                            d = row.get("date")
                            if d and "/" in d:
                                mm, dd, yyyy = d.split("/")
                                d = f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"
                            iso_sched.append({"date": d, "load": int(row.get("load"))})
                        except Exception:
                            pass
                    if iso_sched:
                        parsed["schedule"] = iso_sched
                # Critical Delivery Instructions - Two-stage extraction
                # Stage 1: AI extracted all warehouse requirements
                # Stage 2: Filter to only critical delivery directives
                warehouse_text = ai.get("allWarehouseRequirements")
                if warehouse_text:
                    critical = gemini_filter_critical_instructions(warehouse_text.strip())
                    if critical:
                        parsed["specialInstructions"] = critical
    return parsed
