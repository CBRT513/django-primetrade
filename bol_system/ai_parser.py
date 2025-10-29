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

GROQ_DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_ENDPOINT = os.environ.get("GROQ_API_BASE", "https://api.groq.com/openai/v1/chat/completions")


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


def remote_ai_parse_release_text(
    text: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    endpoint: Optional[str] = None,
    timeout: float = 20.0,
) -> Optional[Dict[str, Any]]:
    """Use a managed API (Groq OpenAI-compatible) to return strict JSON."""
    api_key = api_key or os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    model = model or GROQ_DEFAULT_MODEL
    endpoint = endpoint or GROQ_ENDPOINT

    system = (
        "You are a precise information extractor. Return ONLY valid JSON for the schema: "
        f"{AI_SCHEMA}. Use null/[] when unknown. No markdown, no comments."
    )
    user = f"Extract fields from this release order text between <<< and >>>.\n<<<\n{text}\n>>>"
    try:
        resp = requests.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        return json.loads(content)
    except Exception:
        return None
