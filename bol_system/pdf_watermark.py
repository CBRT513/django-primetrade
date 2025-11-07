"""
PDF Watermarking for Official Weight Certification
Adds a visible stamp to BOL PDFs when official certified scale weight is entered
"""
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger(__name__)


def create_watermark_stamp(official_weight_tons, variance_tons, variance_percent):
    """
    Create a watermark stamp showing official weight and variance

    Args:
        official_weight_tons: Official certified scale weight in tons
        variance_tons: Difference from CBRT estimate (official - cbrt)
        variance_percent: Percentage difference

    Returns:
        BytesIO buffer containing the watermark PDF
    """
    buffer = BytesIO()

    # Create watermark on landscape letter (matching BOL orientation)
    page_width, page_height = landscape(letter)
    c = canvas.Canvas(buffer, pagesize=landscape(letter))

    # Position: Top-right corner with padding
    x_pos = page_width - 3.5 * inch
    y_pos = page_height - 1.2 * inch

    # Draw semi-transparent box background
    c.setFillColorRGB(0.02, 0.4, 0.41, alpha=0.95)  # Dark teal with transparency
    c.roundRect(x_pos - 0.2*inch, y_pos - 0.1*inch, 3.2*inch, 1.0*inch, 6, fill=1, stroke=0)

    # Title: "OFFICIAL WEIGHT"
    c.setFillColorRGB(1, 1, 1)  # White text
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x_pos, y_pos + 0.65*inch, "🟢 OFFICIAL CERTIFIED WEIGHT")

    # Official weight in large text
    c.setFont("Helvetica-Bold", 18)
    official_lbs = int(official_weight_tons * 2000)
    c.drawString(x_pos, y_pos + 0.30*inch, f"{official_lbs:,} lbs")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x_pos + 2.0*inch, y_pos + 0.30*inch, f"({official_weight_tons:.2f} t)")

    # Variance line with color coding
    c.setFont("Helvetica", 9)
    variance_sign = '+' if variance_tons >= 0 else ''
    variance_text = f"Variance: {variance_sign}{variance_tons:.2f} t ({variance_sign}{variance_percent:.1f}%)"

    # Color code variance: green for small, amber for medium, red for large
    abs_variance_pct = abs(variance_percent)
    if abs_variance_pct >= 5:
        c.setFillColorRGB(1, 0.2, 0.2)  # Red for >5%
    elif abs_variance_pct >= 2:
        c.setFillColorRGB(1, 0.8, 0)  # Amber for >2%
    else:
        c.setFillColorRGB(0.4, 1, 0.4)  # Light green for <2%

    c.drawString(x_pos, y_pos + 0.05*inch, variance_text)

    c.save()
    buffer.seek(0)
    return buffer


def watermark_bol_pdf(bol):
    """
    Add official weight watermark to existing BOL PDF

    Args:
        bol: BOL model instance with official_weight_tons set

    Returns:
        str: URL of the watermarked PDF, or None if watermarking failed
    """
    if not bol.official_weight_tons:
        logger.warning(f"Cannot watermark BOL {bol.bol_number}: no official weight set")
        return None

    if not bol.pdf_url:
        logger.warning(f"Cannot watermark BOL {bol.bol_number}: no original PDF exists")
        return None

    try:
        # Extract S3 key from URL
        # Format: https://bucket.s3.region.amazonaws.com/bols/YYYY/BOL-NUMBER.pdf?...
        # or: bols/YYYY/BOL-NUMBER.pdf (local path)
        original_path = bol.pdf_url.split('?')[0]  # Remove query params
        if 'amazonaws.com/' in original_path:
            # Extract key from S3 URL
            s3_key = original_path.split('amazonaws.com/')[-1]
        else:
            # Local file path
            s3_key = original_path.replace('/media/', '')

        logger.info(f"Watermarking BOL {bol.bol_number}, original path: {s3_key}")

        # Read original PDF from storage
        original_pdf_file = default_storage.open(s3_key, 'rb')
        original_pdf = PdfReader(original_pdf_file)

        # Calculate variance
        variance_tons = float(bol.weight_variance_tons or 0)
        variance_percent = float(bol.weight_variance_percent or 0)

        # Create watermark stamp
        watermark_buffer = create_watermark_stamp(
            float(bol.official_weight_tons),
            variance_tons,
            variance_percent
        )
        watermark_pdf = PdfReader(watermark_buffer)

        # Create output PDF with watermark
        writer = PdfWriter()

        # Overlay watermark on first page (BOL is single page)
        page = original_pdf.pages[0]
        watermark_page = watermark_pdf.pages[0]
        page.merge_page(watermark_page)
        writer.add_page(page)

        # Add any additional pages (shouldn't be any, but handle gracefully)
        for i in range(1, len(original_pdf.pages)):
            writer.add_page(original_pdf.pages[i])

        # Save watermarked PDF to buffer
        output_buffer = BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)

        # Generate stamped filename: bols/YYYY/BOL-NUMBER-stamped.pdf
        stamped_path = s3_key.replace('.pdf', '-stamped.pdf')

        # Save to storage
        saved_path = default_storage.save(stamped_path, ContentFile(output_buffer.read()))
        stamped_url = default_storage.url(saved_path)

        logger.info(f"Successfully watermarked BOL {bol.bol_number}, saved to: {saved_path}")

        # Close files
        original_pdf_file.close()

        return stamped_url

    except Exception as e:
        logger.error(f"Error watermarking BOL {bol.bol_number}: {str(e)}", exc_info=True)
        return None
