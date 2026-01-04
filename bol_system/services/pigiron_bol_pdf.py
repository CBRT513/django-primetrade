"""
Pig Iron BOL PDF Generator using WeasyPrint.

Generates BOL PDFs using HTML/CSS templates for consistency
and maintainability.
"""
from django.template.loader import render_to_string
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


def generate_pigiron_bol_pdf(bol):
    """
    Generate pig iron BOL PDF using WeasyPrint.

    Args:
        bol: BOL model instance

    Returns:
        bytes: PDF content
    """
    try:
        from weasyprint import HTML
    except ImportError:
        logger.warning("WeasyPrint not installed, falling back to ReportLab")
        return _generate_pdf_reportlab(bol)

    context = {
        'bol': bol,
    }

    html_string = render_to_string('bol/pigiron_bol.html', context)
    html = HTML(string=html_string)
    pdf_bytes = html.write_pdf()

    return pdf_bytes


def _generate_pdf_reportlab(bol):
    """Fallback PDF generation using existing ReportLab generator."""
    from ..pdf_generator import generate_bol_pdf
    import tempfile
    import os

    # Generate to temp file and read bytes
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        generate_bol_pdf(bol, output_path=tmp_path)
        with open(tmp_path, 'rb') as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
