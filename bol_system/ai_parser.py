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
    '"schedule": [{"date": "MM/DD/YYYY", "load": number}] }'
)


def _strip_code_fence(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^```json\s*", "", s, flags=re.I)
    s = re.sub(r"^```\s*", "", s)
    s = re.sub(r"```\s*$", "", s)
    return s.strip()


def ai_parse_release_text(
    text: str,
    model: Optional[str] = None,
    ollama_url: Optional[str] = None,
    timeout: float = 15.0,
) -> Optional[Dict[str, Any]]:
    """
    Ask a local Ollama model to extract a strict JSON object.
    Returns dict or None on failure.
    """
    model = model or os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
    base = ollama_url or os.environ.get("OLLAMA_URL", "http://localhost:11434")

    prompt = (
        "Extract fields from the following RELEASE ORDER text. "
        "Return ONLY valid JSON matching this schema (no prose, no markdown):\n"
        f"{AI_SCHEMA}\n"
        "Fill unknown fields with null or empty list.\n"
        "Text between <<< and >>> follows.\n<<<\n"
        f"{text}\n>>>\n"
    )

    try:
        resp = requests.post(
            f"{base.rstrip('/')}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0, "num_ctx": 8192},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        raw = _strip_code_fence(str(body.get("response", "")).strip())
        return json.loads(raw)
    except Exception:
        return None