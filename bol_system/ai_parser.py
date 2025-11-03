import json
import os
import re
from typing import Any, Dict, Optional

import requests

AI_SCHEMA = (
    '{ "releaseNumber": str|null, "releaseDate": "MM/DD/YYYY"|null, '
    '"customerId": str|null, "customerPO": str|null, "shipVia": str|null, "fob": str|null, '
    '"shipTo": {"name": str|null, "address": str|null}, '
    '"material": {"lot": str|null, "description": str|null}, '
    '"quantityNetTons": number|null, '
    '"schedule": [{"date": "MM/DD/YYYY", "load": number}], '
    '"specialInstructions": str|null }'
)

GEMINI_DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_ENDPOINT_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _strip_code_fence(s: str) -> str:
    """Remove markdown code fences from JSON response."""
    s = s.strip()
    s = re.sub(r"^```json\s*", "", s, flags=re.I)
    s = re.sub(r"^```\s*", "", s)
    s = re.sub(r"```\s*$", "", s)
    return s.strip()


def gemini_parse_release_text(
    text: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 20.0,
) -> Optional[Dict[str, Any]]:
    """
    Use Google Gemini API to extract structured data from release order text.
    Returns dict or None on failure.
    """
    api_key = api_key or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None

    model = model or GEMINI_DEFAULT_MODEL
    endpoint = f"{GEMINI_ENDPOINT_BASE}/{model}:generateContent?key={api_key}"

    prompt = (
        "Extract fields from the following RELEASE ORDER text. "
        "Return ONLY valid JSON matching this schema (no prose, no markdown):\n"
        f"{AI_SCHEMA}\n\n"
        "Instructions:\n"
        "- For specialInstructions: extract ONLY the bulleted requirements (-) from 'Warehouse requirements:' or 'Warehouse:' sections.\n"
        "- Include only the dash/bullet items. Stop before section headings like 'Trucking requirements:', 'SPECIAL INSTRUCTIONS:', or contact information.\n"
        "- Do NOT include document headers, addresses, release numbers, or other metadata in specialInstructions.\n"
        "- Fill unknown fields with null or empty list.\n\n"
        "Text between <<< and >>> follows.\n<<<\n"
        f"{text}\n>>>"
    )

    try:
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json"
            }
        }

        resp = requests.post(endpoint, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # Extract text from Gemini response format
        candidates = data.get("candidates", [])
        if not candidates:
            return None

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            return None

        text_response = parts[0].get("text", "")
        clean_text = _strip_code_fence(text_response.strip())

        return json.loads(clean_text)
    except Exception:
        return None


# Aliases for backward compatibility
ai_parse_release_text = gemini_parse_release_text
remote_ai_parse_release_text = gemini_parse_release_text
