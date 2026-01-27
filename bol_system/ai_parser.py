"""
AI-powered release order parsing using Anthropic Claude.

Extracts structured data from release order text and filters
critical delivery instructions from warehouse requirements.
"""
import json
import logging
import os
import re
from typing import Any, Dict, Optional

import anthropic

logger = logging.getLogger(__name__)

# Claude model configuration
CLAUDE_MODEL = "claude-sonnet-4-20250514"

AI_SCHEMA = (
    '{ "releaseNumber": str|null, "releaseDate": "MM/DD/YYYY"|null, '
    '"customerId": str|null, "customerPO": str|null, "shipVia": str|null, "fob": str|null, '
    '"shipTo": {"name": str|null, "address": str|null}, '
    '"material": {"lot": str|null, "description": str|null, "extraBOLAnalysis": str|null}, '
    '"quantityNetTons": number|null, '
    '"schedule": [{"date": "MM/DD/YYYY", "load": number}], '
    '"allWarehouseRequirements": str|null }'
)


def _strip_code_fence(s: str) -> str:
    """Remove markdown code fences from JSON response."""
    s = s.strip()
    s = re.sub(r"^```json\s*", "", s, flags=re.I)
    s = re.sub(r"^```\s*", "", s)
    s = re.sub(r"```\s*$", "", s)
    return s.strip()


def claude_parse_release_text(
    text: str,
    api_key: Optional[str] = None,
    timeout: float = 30.0,
) -> Optional[Dict[str, Any]]:
    """
    Use Claude API to extract structured data from release order text.
    Returns dict or None on failure.
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, AI extraction disabled")
        return None

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
        client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            temperature=0,  # Deterministic output
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        content = response.content[0].text
        clean_text = _strip_code_fence(content.strip())

        result = json.loads(clean_text)
        logger.info(f"Claude extraction successful: {list(result.keys())}")
        logger.info(f"Claude releaseNumber={result.get('releaseNumber')!r}, customerId={result.get('customerId')!r}")
        return result

    except anthropic.APITimeoutError:
        logger.error("Claude API timeout")
        return None
    except anthropic.RateLimitError as e:
        logger.error(f"Claude rate limit exceeded: {e}")
        return None
    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude JSON response: {e}")
        return None
    except Exception as e:
        logger.error(f"Claude API Stage 1 failed: {e}", exc_info=True)
        return None


def claude_filter_critical_instructions(
    warehouse_text: str,
    api_key: Optional[str] = None,
    timeout: float = 30.0,
) -> Optional[str]:
    """
    Stage 2: Filter warehouse requirements to extract ONLY critical delivery directives.
    Returns critical instructions string or None.
    """
    if not warehouse_text or not warehouse_text.strip():
        return None

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, Stage 2 filter disabled")
        return None

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
        client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            temperature=0,  # Deterministic output
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        result = response.content[0].text.strip()

        # Handle "null" response
        if result.lower() in ("null", "none", ""):
            return None

        return result

    except anthropic.APITimeoutError:
        logger.error("Claude API timeout (Stage 2)")
        return None
    except anthropic.RateLimitError as e:
        logger.error(f"Claude rate limit exceeded (Stage 2): {e}")
        return None
    except anthropic.APIError as e:
        logger.error(f"Claude API error (Stage 2): {e}")
        return None
    except Exception as e:
        logger.error(f"Claude API Stage 2 filter failed: {e}", exc_info=True)
        return None


# Backward compatibility aliases (used by release_parser.py)
ai_parse_release_text = claude_parse_release_text
remote_ai_parse_release_text = claude_parse_release_text
openai_parse_release_text = claude_parse_release_text
gemini_filter_critical_instructions = claude_filter_critical_instructions
openai_filter_critical_instructions = claude_filter_critical_instructions
