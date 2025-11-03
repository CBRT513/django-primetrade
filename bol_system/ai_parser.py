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

GROQ_DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_ENDPOINT = os.environ.get("GROQ_API_BASE", "https://api.groq.com/openai/v1/chat/completions")
OPENROUTER_DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")
OPENROUTER_ENDPOINT = os.environ.get("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1/chat/completions")
TOGETHER_DEFAULT_MODEL = os.environ.get("TOGETHER_MODEL", "meta-llama/llama-3.1-8b-instruct")
TOGETHER_ENDPOINT = os.environ.get("TOGETHER_API_BASE", "https://api.together.xyz/v1/chat/completions")


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
        "For specialInstructions: extract the full text from 'Warehouse:', 'Warehouse requirements:', or similar sections.\n"
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
    """Use a managed API (Groq/OpenRouter/Together) to return strict JSON."""
    # Provider autodetect order: GROQ > OPENROUTER > TOGETHER
    provider = None
    if os.environ.get("GROQ_API_KEY"):
        provider = "groq"
        api_key = api_key or os.environ.get("GROQ_API_KEY")
        model = model or GROQ_DEFAULT_MODEL
        endpoint = endpoint or GROQ_ENDPOINT
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    elif os.environ.get("OPENROUTER_API_KEY"):
        provider = "openrouter"
        api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        model = model or OPENROUTER_DEFAULT_MODEL
        endpoint = endpoint or OPENROUTER_ENDPOINT
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Optional but recommended; safe defaults
            "HTTP-Referer": os.environ.get("OPENROUTER_REFERER", "https://primetrade.local"),
            "X-Title": os.environ.get("OPENROUTER_TITLE", "PrimeTrade Release Parser"),
        }
    elif os.environ.get("TOGETHER_API_KEY"):
        provider = "together"
        api_key = api_key or os.environ.get("TOGETHER_API_KEY")
        model = model or TOGETHER_DEFAULT_MODEL
        endpoint = endpoint or TOGETHER_ENDPOINT
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    else:
        return None

    system = (
        "You are a precise information extractor for release orders. Return ONLY valid JSON for the schema: "
        f"{AI_SCHEMA}. "
        "For specialInstructions: extract the full text from 'Warehouse:', 'Warehouse requirements:', or similar sections. "
        "Use null/[] when unknown. No markdown, no comments."
    )
    user = f"Extract fields from this release order text between <<< and >>>.\n<<<\n{text}\n>>>"
    try:
        payload = {
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        return json.loads(content)
    except Exception:
        return None
