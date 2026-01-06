"""
Release Parser Service (Anthropic Claude).

Extracts release data from PDF documents using Claude Vision.
"""
import base64
import json
import logging
from typing import TypedDict, Optional

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-20250514"


class ShipToAddress(TypedDict):
    name: str
    street: str
    city: str
    state: str
    zip: str


class ChemistryAnalysis(TypedDict):
    C: Optional[float]
    Si: Optional[float]
    S: Optional[float]
    P: Optional[float]
    Mn: Optional[float]


class MaterialInfo(TypedDict):
    lot: str
    description: str
    analysis: ChemistryAnalysis


class ScheduleItem(TypedDict):
    date: str  # YYYY-MM-DD
    load: int


class ParsedRelease(TypedDict):
    releaseNumber: str
    releaseDate: str  # YYYY-MM-DD
    customerId: str
    customerPO: str
    shipVia: str
    fob: str
    shipTo: ShipToAddress
    material: MaterialInfo
    quantityNetTons: float
    schedule: list[ScheduleItem]
    specialInstructions: str


def parse_release_pdf(pdf_file) -> ParsedRelease:
    """
    Extract release information from PDF using Claude Vision.

    Args:
        pdf_file: File-like object containing PDF data

    Returns:
        ParsedRelease dict with extracted data

    Raises:
        ImportError: If anthropic package not installed
        ValueError: If extraction fails or returns invalid JSON
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError(
            "anthropic package required for release parsing. "
            "Install with: pip install anthropic"
        )

    client = Anthropic()

    # Convert PDF to base64
    pdf_bytes = pdf_file.read()
    pdf_base64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    logger.info(f"Parsing release PDF ({len(pdf_bytes)} bytes)")

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_base64
                    }
                },
                {
                    "type": "text",
                    "text": """Extract release information from this document.
Return JSON with these fields:
{
    "releaseNumber": "string",
    "releaseDate": "YYYY-MM-DD",
    "customerId": "string",
    "customerPO": "string",
    "shipVia": "string",
    "fob": "string",
    "shipTo": {
        "name": "string",
        "street": "string",
        "city": "string",
        "state": "string",
        "zip": "string"
    },
    "material": {
        "lot": "string",
        "description": "string",
        "analysis": {
            "C": number or null,
            "Si": number or null,
            "S": number or null,
            "P": number or null,
            "Mn": number or null
        }
    },
    "quantityNetTons": number,
    "schedule": [
        {"date": "YYYY-MM-DD", "load": 1},
        ...
    ],
    "specialInstructions": "string"
}
Only return valid JSON, no explanation."""
                }
            ]
        }]
    )

    response_text = response.content[0].text.strip()

    # Handle potential markdown code blocks
    if response_text.startswith('```'):
        # Remove markdown code block markers
        lines = response_text.split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines[-1].strip() == '```':
            lines = lines[:-1]
        response_text = '\n'.join(lines)

    try:
        parsed = json.loads(response_text)
        logger.info(f"Parsed release {parsed.get('releaseNumber', 'UNKNOWN')}")
        return parsed
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response as JSON: {e}")
        logger.debug(f"Response was: {response_text[:500]}")
        raise ValueError(f"Failed to parse release: invalid JSON response")
