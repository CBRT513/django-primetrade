import json
import logging
import os
import re
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

AI_SCHEMA = (
    '{ "releaseNumber": str|null, "releaseDate": "MM/DD/YYYY"|null, '
    '"customerId": str|null, "customerPO": str|null, "shipVia": str|null, "fob": str|null, '
    '"shipTo": {"name": str|null, "address": str|null}, '
    '"material": {"lot": str|null, "description": str|null, "extraBOLAnalysis": str|null}, '
    '"quantityNetTons": number|null, '
    '"schedule": [{"date": "MM/DD/YYYY", "load": number}], '
    '"allWarehouseRequirements": str|null }'
)

OPENAI_DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"


def _strip_code_fence(s: str) -> str:
    """Remove markdown code fences from JSON response."""
    s = s.strip()
    s = re.sub(r"^```json\s*", "", s, flags=re.I)
    s = re.sub(r"^```\s*", "", s)
    s = re.sub(r"```\s*$", "", s)
    return s.strip()


def openai_parse_release_text(
    text: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> Optional[Dict[str, Any]]:
    """
    Use OpenAI API to extract structured data from release order text.
    Returns dict or None on failure.
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set, AI extraction disabled")
        return None

    model = model or OPENAI_DEFAULT_MODEL

    prompt = (
        "Extract fields from the following RELEASE ORDER text. "
        "Return ONLY valid JSON matching this schema (no prose, no markdown):\n"
        f"{AI_SCHEMA}\n\n"
        "Instructions:\n"
        "- For material.description: include ONLY the base material name (e.g., 'NODULAR PIG IRON'). DO NOT include chemistry values.\n"
        "- For material.extraBOLAnalysis: extract ONLY supplemental chemistry specifications that are NOT standard chemistry (C, Si, S, P, Mn). "
        "Examples: 'CR .004 TI .001 V .004', 'CU 0.15 NI 0.08'. If found, preserve EXACTLY as written. Set to null if not present.\n"
        "- For allWarehouseRequirements: extract the COMPLETE text from the 'Warehouse requirements:' or 'Warehouse:' section EXACTLY as written, preserving all bullets and formatting.\n"
        "- If there is no warehouse section, set to null.\n"
        "- Fill unknown fields with null or empty list.\n\n"
        "Text between <<< and >>> follows.\n<<<\n"
        f"{text}\n>>>"
    )

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"}
        }

        resp = requests.post(OPENAI_ENDPOINT, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # Extract content from OpenAI response format
        choices = data.get("choices", [])
        if not choices:
            return None

        message = choices[0].get("message", {})
        content = message.get("content", "")
        
        if not content:
            return None

        clean_text = _strip_code_fence(content.strip())
        return json.loads(clean_text)
        
    except Exception as e:
        logger.error(f"OpenAI API Stage 1 failed: {e}", exc_info=True)
        return None


def openai_filter_critical_instructions(
    warehouse_text: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> Optional[str]:
    """
    Stage 2: Filter warehouse requirements to extract ONLY critical delivery directives.
    Returns critical instructions string or None.
    """
    if not warehouse_text or not warehouse_text.strip():
        return None

    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set, Stage 2 filter disabled")
        return None

    model = model or OPENAI_DEFAULT_MODEL

    prompt = (
        "You are analyzing warehouse requirements from a shipping release order. "
        "Your task is to identify ONLY the critical delivery directives that a truck driver MUST follow.\n\n"

        "CRITICAL INSTRUCTIONS include:\n"
        "- Specific plant/location requirements (e.g., 'DELIVER TO PLANT ONE', 'SEND TO THE FOUNDRY')\n"
        "- Time-sensitive directives (e.g., 'Pickup & Deliver Same Day', 'Call ahead before delivery')\n"
        "- Special handling requirements (e.g., 'Must deliver to Building 3', 'Use north entrance only')\n"
        "- Customer-specific delivery instructions that affect WHERE or WHEN delivery occurs\n\n"

        "ROUTINE REQUIREMENTS (DO NOT INCLUDE):\n"
        "- Equipment type specifications (e.g., 'bulk end dump trailer', 'flatbed required')\n"
        "- Weight limits (e.g., 'DO NOT EXCEED Maximum Legal Truck Weight')\n"
        "- Material cleanliness requirements (e.g., 'truck must be clean', 'no contamination')\n"
        "- Tarping requirements (e.g., 'Truck must be TARPED')\n"
        "- Standard BOL content requirements (e.g., 'Analysis & PO must be on BOL', 'Material # must be on BOL', 'PO # must be on BOL')\n"
        "- Chemistry/analysis specifications (e.g., 'CR .004 TI .001 V .004', 'Analysis', chemical element values)\n"
        "- Material numbers (e.g., 'Material # 5000052')\n"
        "- Shipper information (e.g., 'SHIPPER: Primetrade, LLC')\n"
        "- General delivery hours (e.g., 'Deliveries accepted 8am-4pm')\n"
        "- Standard operating procedures\n\n"

        "EXAMPLES:\n"
        "Input: '- DELIVER TO PLANT ONE\\n- Truck must be TARPED\\n- DO NOT EXCEED Maximum Legal Truck Weight'\n"
        "Output: 'DELIVER TO PLANT ONE'\n\n"

        "Input: '- Material # 5000052\\n- P.O. # 450002459\\n- \"SEND TO THE FOUNDRY\"\\n- CR .004 TI .001 V .004\\n- Analysis'\n"
        "Output: 'SEND TO THE FOUNDRY'\n\n"

        "Input: '- Pickup & Deliver Same Day\\n- Equipment type: bulk end dump trailer\\n- SHIPPER: Primetrade, LLC'\n"
        "Output: 'Pickup & Deliver Same Day'\n\n"

        "Input: '- Truck must be TARPED\\n- Analysis & PO must be on BOL\\n- Equipment type: Bulk end dump trailer'\n"
        "Output: null\n\n"

        "Now analyze the following warehouse requirements. Return ONLY the critical delivery directive text, "
        "or the word 'null' if there are no critical instructions. Do not include any explanation or markdown.\n\n"
        "Warehouse Requirements:\n<<<\n"
        f"{warehouse_text}\n>>>"
    )

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0
        }

        resp = requests.post(OPENAI_ENDPOINT, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            return None

        message = choices[0].get("message", {})
        result = message.get("content", "").strip()

        # Handle "null" response
        if result.lower() in ("null", "none", ""):
            return None

        return result
        
    except Exception as e:
        logger.error(f"OpenAI API Stage 2 filter failed: {e}", exc_info=True)
        return None


# Backward compatibility aliases (used by release_parser.py)
ai_parse_release_text = openai_parse_release_text
remote_ai_parse_release_text = openai_parse_release_text
gemini_filter_critical_instructions = openai_filter_critical_instructions
