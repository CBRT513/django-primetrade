"""
PrimeTrade integration hooks for the Driver Kiosk module.
"""
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone

from .models import BOL, CompanyBranding
from .pdf_generator import generate_bol_pdf


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


def attach_signature(bol_id: int, signature_data: str, signed_by: str) -> dict:
    """Attach driver signature to BOL."""
    try:
        bol = BOL.objects.get(id=bol_id)

        if bol.signature:
            return {'success': False, 'error': 'BOL already signed'}

        bol.signature = signature_data
        bol.signed_by = signed_by
        bol.signed_at = timezone.now()
        bol.bol_status = 'signed'
        bol.save()

        return {
            'success': True,
            'bol_id': bol.id,
            'bol_number': bol.bol_number,
            'signed_at': bol.signed_at.isoformat(),
            'pdf_url': f'/bol/{bol.id}/pdf/',
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
