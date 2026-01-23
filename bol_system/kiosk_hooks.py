"""
PrimeTrade integration hooks for the Driver Kiosk module.
"""
import base64
import logging
from io import BytesIO

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from PIL import Image

from .models import BOL, CompanyBranding
from .pdf_generator import generate_bol_pdf

logger = logging.getLogger(__name__)


def search_bols(query: str, filters: dict = None, request=None) -> list[dict]:
    """Search BOLs for office assignment."""
    # TODO: Add tenant filtering for multi-tenant
    qs = BOL.objects.filter(bol_status='ready')

    if query:
        qs = qs.filter(
            Q(bol_number__icontains=query) |
            Q(customer__customer__icontains=query) |
            Q(truck_number__icontains=query) |
            Q(buyer_name__icontains=query)
        )

    if filters:
        if filters.get('status'):
            qs = qs.filter(bol_status=filters['status'])
        if filters.get('date_from'):
            qs = qs.filter(created_at__date__gte=filters['date_from'])
        if filters.get('date_to'):
            qs = qs.filter(created_at__date__lte=filters['date_to'])

    results = []
    for bol in qs[:20]:
        results.append({
            'id': bol.id,
            'bol_number': bol.bol_number,
            'customer_name': bol.customer.customer if bol.customer else bol.buyer_name or '',
            'truck_number': bol.truck_number or '',
            'status': bol.bol_status,
            'created_at': bol.created_at.isoformat() if bol.created_at else '',
            'summary': f"{bol.product_name or 'Pig Iron'}, {bol.net_tons or 0:,.2f} tons",
        })

    return results


def get_bol_detail(bol_id: int) -> dict:
    """Get full BOL details for driver review."""
    bol = BOL.objects.select_related('customer', 'carrier').get(id=bol_id)

    # Get shipper from CompanyBranding
    branding = CompanyBranding.get_instance()

    return {
        'id': bol.id,
        'bol_number': bol.bol_number,
        'status': bol.bol_status,
        'created_at': bol.created_at.isoformat() if bol.created_at else '',
        'shipper': {
            'name': branding.company_name if branding else 'Cincinnati Barge & Rail Terminal',
            'address': f"{branding.address_line1}\n{branding.address_line2}" if branding else '',
        },
        'consignee': {
            'name': bol.customer.customer if bol.customer else bol.buyer_name or '',
            'address': bol.customer.full_address if bol.customer else '',
        },
        'carrier': {
            'name': bol.carrier.carrier_name if bol.carrier else '',
            'truck_number': bol.truck_number or '',
            'driver_name': bol.signed_by or '',
        },
        'line_items': [
            {
                'description': bol.product_name or 'Pig Iron',
                'quantity': float(bol.net_tons) if bol.net_tons else 0,
                'unit': 'tons',
                'weight_lbs': float(bol.net_tons * 2000) if bol.net_tons else 0,
                'notes': '',
            }
        ],
        'total_weight_lbs': float(bol.net_tons * 2000) if bol.net_tons else 0,
        'total_items': 1,
        'signature_captured': bool(bol.signature),
        'signed_at': bol.signed_at.isoformat() if bol.signed_at else None,
    }


def _overlay_signature_on_pdf(pdf_bytes: bytes, signature_base64: str, signed_by: str, signed_at) -> bytes:
    """
    Overlay signature image onto existing PDF at CARRIER SIGNATURE location.

    Args:
        pdf_bytes: Original PDF as bytes
        signature_base64: Base64 encoded signature image (data:image/png;base64,...)
        signed_by: Driver name for label
        signed_at: Timestamp for label

    Returns:
        Signed PDF as bytes
    """
    # Decode base64 signature to image
    if ',' in signature_base64:
        signature_base64 = signature_base64.split(',')[1]
    sig_data = base64.b64decode(signature_base64)
    sig_image = Image.open(BytesIO(sig_data))

    # Convert to RGB if needed (PNG may have alpha channel)
    if sig_image.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', sig_image.size, (255, 255, 255))
        if sig_image.mode == 'P':
            sig_image = sig_image.convert('RGBA')
        background.paste(sig_image, mask=sig_image.split()[-1] if sig_image.mode == 'RGBA' else None)
        sig_image = background

    # Save signature to temp buffer for ReportLab
    sig_buffer = BytesIO()
    sig_image.save(sig_buffer, format='PNG')
    sig_buffer.seek(0)

    # Wrap BytesIO in ImageReader for ReportLab compatibility
    sig_reader = ImageReader(sig_buffer)

    # Create overlay PDF with signature
    # PDF is landscape letter: 792 x 612 points (11 x 8.5 inches)
    overlay_buffer = BytesIO()
    c = canvas.Canvas(overlay_buffer, pagesize=landscape(letter))

    # Signature placement: right side of page, bottom area
    # Right column starts at ~5 inches, signature area ~1 inch from bottom
    sig_x = 5.5 * inch
    sig_y = 0.7 * inch
    sig_width = 2.5 * inch
    sig_height = 0.6 * inch

    # Draw signature image
    c.drawImage(
        sig_reader,
        sig_x,
        sig_y,
        width=sig_width,
        height=sig_height,
        preserveAspectRatio=True,
        anchor='sw'
    )

    # Add timestamp below signature
    timestamp_str = signed_at.strftime('%m/%d/%Y %I:%M %p') if signed_at else ''
    c.setFont('Helvetica', 7)
    c.drawString(sig_x, sig_y - 10, f"Signed: {timestamp_str}")
    c.drawString(sig_x, sig_y - 20, f"Driver: {signed_by}")

    c.save()
    overlay_buffer.seek(0)

    # Merge overlay onto original PDF
    original_pdf = PdfReader(BytesIO(pdf_bytes))
    overlay_pdf = PdfReader(overlay_buffer)

    writer = PdfWriter()

    # Merge first page with signature overlay
    page = original_pdf.pages[0]
    page.merge_page(overlay_pdf.pages[0])
    writer.add_page(page)

    # Copy any additional pages (unlikely for BOL)
    for i in range(1, len(original_pdf.pages)):
        writer.add_page(original_pdf.pages[i])

    # Output merged PDF
    output_buffer = BytesIO()
    writer.write(output_buffer)
    output_buffer.seek(0)

    return output_buffer.read()


def attach_signature(bol_id: int, signature_data: str, signed_by: str) -> dict:
    """
    Attach driver signature to BOL.

    Saves signature data, regenerates PDF with signature overlay,
    uploads signed PDF to S3, and sends email notification.
    """
    try:
        bol = BOL.objects.get(id=bol_id)

        if bol.signature:
            return {'success': False, 'error': 'BOL already signed'}

        # Save signature metadata
        bol.signature = signature_data
        bol.signed_by = signed_by
        bol.signed_at = timezone.now()
        bol.bol_status = 'signed'
        bol.save()

        # Regenerate PDF with signature overlay
        try:
            # Generate fresh PDF
            unsigned_pdf = generate_bol_pdf(bol, return_bytes=True)

            # Overlay signature
            signed_pdf = _overlay_signature_on_pdf(
                unsigned_pdf,
                signature_data,
                signed_by,
                bol.signed_at
            )

            # Upload signed PDF to S3 (replace existing)
            year = bol.date.year if hasattr(bol.date, 'year') else timezone.now().year
            filename = f"bols/{year}/{bol.bol_number}.pdf"

            # Delete existing if present
            if default_storage.exists(filename):
                default_storage.delete(filename)

            saved_path = default_storage.save(filename, ContentFile(signed_pdf))
            pdf_url = default_storage.url(saved_path)

            # Update BOL with new PDF URL
            bol.pdf_url = pdf_url
            bol.save(update_fields=['pdf_url', 'updated_at'])

            logger.info(f"Signed PDF uploaded for BOL {bol.bol_number}")

        except Exception as e:
            logger.error(f"Failed to generate signed PDF for BOL {bol.bol_number}: {str(e)}")
            pdf_url = bol.pdf_url  # Fall back to existing URL

        # Send email notification with signed PDF
        try:
            from .email_utils import send_bol_notification
            send_bol_notification(bol, pdf_url)
            logger.info(f"Email notification sent for signed BOL {bol.bol_number}")
        except Exception as e:
            logger.error(f"Failed to send email for BOL {bol.bol_number}: {str(e)}")
            # Don't fail signature if email fails

        return {
            'success': True,
            'bol_id': bol.id,
            'bol_number': bol.bol_number,
            'signed_at': bol.signed_at.isoformat(),
            'pdf_url': pdf_url if 'pdf_url' in locals() else f'/bol/{bol.id}/pdf/',
        }
    except BOL.DoesNotExist:
        return {'success': False, 'error': 'BOL not found'}


def generate_pdf(bol_id: int) -> HttpResponse:
    """Generate printable PDF of BOL."""
    bol = BOL.objects.get(id=bol_id)

    # Use existing PDF generation with return_bytes=True for inline display
    pdf_bytes = generate_bol_pdf(bol, return_bytes=True)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{bol.bol_number}.pdf"'
    return response
