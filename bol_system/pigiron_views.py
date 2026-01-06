"""
Pig Iron workflow views.

URL pattern: /tenant/{tenant_code}/pigiron/...

These views implement the PrimeTrade pig iron workflow using the
Composable Architecture patterns from the spec.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import logging

from .models import (
    Tenant, Release, ReleaseLoad, BOL, Carrier, Truck,
    Product, Lot, Customer
)
from .services import BOLCreationService, parse_release_pdf
from .serializers import ReleaseSerializer, ReleaseLoadSerializer

logger = logging.getLogger(__name__)


def get_tenant_or_404(tenant_code):
    """Get tenant by code or return 404."""
    return get_object_or_404(Tenant, code=tenant_code.upper(), is_active=True)


# =============================================================================
# Release Views
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def release_list(request, tenant_code):
    """
    List all releases for a tenant.

    GET /tenant/{tenant_code}/pigiron/releases/
    Query params:
        - status: OPEN|COMPLETE|CANCELLED|ALL (default: OPEN)
    """
    tenant = get_tenant_or_404(tenant_code)

    status_filter = request.query_params.get('status', 'OPEN').upper()

    releases = Release.objects.filter(tenant=tenant)

    if status_filter != 'ALL':
        releases = releases.filter(status=status_filter)

    releases = releases.order_by('-created_at')

    data = []
    for release in releases:
        data.append({
            'id': release.id,
            'release_number': release.release_number,
            'release_date': release.release_date,
            'customer_id_text': release.customer_id_text,
            'customer_po': release.customer_po,
            'status': release.status,
            'total_loads': release.total_loads,
            'loads_shipped': release.loads_shipped,
            'loads_remaining': release.loads_remaining,
            'quantity_net_tons': release.quantity_net_tons,
            'material_description': release.material_description,
            'lot': release.lot,
            'special_instructions': release.special_instructions,
            'care_of_co': release.care_of_co,
            'created_at': release.created_at,
        })

    return Response({
        'tenant': tenant.code,
        'status_filter': status_filter,
        'count': len(data),
        'releases': data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def release_detail(request, tenant_code, release_id):
    """
    Get release details with all loads.

    GET /tenant/{tenant_code}/pigiron/releases/{release_id}/
    """
    tenant = get_tenant_or_404(tenant_code)
    release = get_object_or_404(Release, id=release_id, tenant=tenant)

    loads = []
    for load in release.loads.all():
        bol_info = None
        # Check new release_line FK first, then legacy bol FK
        active_bol = load.bols.filter(is_void=False).first()
        if not active_bol and load.bol:
            active_bol = load.bol if not load.bol.is_void else None

        if active_bol:
            bol_info = {
                'id': active_bol.id,
                'bol_number': active_bol.bol_number,
                'bol_date': active_bol.bol_date or active_bol.date,
                'net_tons': active_bol.net_tons,
                'carrier_name': active_bol.carrier_name,
            }

        loads.append({
            'id': load.id,
            'seq': load.seq,
            'line_number': load.line_number,
            'date': load.date,
            'planned_tons': load.planned_tons,
            'status': load.status,
            'shipped_at': load.shipped_at,
            'bol': bol_info,
        })

    # Get lot chemistry if available
    lot_info = None
    if release.lot_ref:
        lot_info = {
            'id': release.lot_ref.id,
            'code': release.lot_ref.code,
            'chemistry': release.lot_ref.format_chemistry(),
        }

    return Response({
        'id': release.id,
        'release_number': release.release_number,
        'release_date': release.release_date,
        'customer_id_text': release.customer_id_text,
        'customer_ref': {
            'id': release.customer_ref.id,
            'name': release.customer_ref.customer
        } if release.customer_ref else None,
        'customer_po': release.customer_po,
        'ship_via': release.ship_via,
        'fob': release.fob,
        'ship_to': {
            'name': release.ship_to_name,
            'street': release.ship_to_street,
            'street2': release.ship_to_street2,
            'city': release.ship_to_city,
            'state': release.ship_to_state,
            'zip': release.ship_to_zip,
        },
        'lot': lot_info,
        'material_description': release.material_description,
        'quantity_net_tons': release.quantity_net_tons,
        'status': release.status,
        'special_instructions': release.special_instructions,
        'care_of_co': release.care_of_co,
        'loads': loads,
        'total_loads': release.total_loads,
        'loads_shipped': release.loads_shipped,
        'loads_remaining': release.loads_remaining,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_release(request, tenant_code):
    """
    Upload release PDF for parsing.

    POST /tenant/{tenant_code}/pigiron/releases/upload/
    Body: multipart/form-data with 'file' field
    """
    tenant = get_tenant_or_404(tenant_code)

    if 'file' not in request.FILES:
        return Response(
            {'error': 'No file provided'},
            status=status.HTTP_400_BAD_REQUEST
        )

    pdf_file = request.FILES['file']

    try:
        parsed_data = parse_release_pdf(pdf_file)

        logger.info(
            f"Parsed release {parsed_data.get('releaseNumber', 'UNKNOWN')} "
            f"for tenant {tenant.code}"
        )

        return Response({
            'status': 'parsed',
            'data': parsed_data
        })

    except ImportError as e:
        logger.error(f"Release parsing dependency error: {e}")
        return Response(
            {'error': 'Release parsing service unavailable'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except Exception as e:
        logger.error(f"Release parsing error: {e}")
        return Response(
            {'error': f'Failed to parse release: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_release(request, tenant_code):
    """
    Create release from parsed data.

    POST /tenant/{tenant_code}/pigiron/releases/approve/
    Body: JSON with parsed release data
    """
    tenant = get_tenant_or_404(tenant_code)
    data = request.data

    try:
        with transaction.atomic():
            # Create or get lot
            lot = None
            material = data.get('material', {})
            lot_code = material.get('lot', '').strip()

            if lot_code:
                analysis = material.get('analysis', {})
                lot, created = Lot.objects.get_or_create(
                    tenant=tenant,
                    code=lot_code,
                    defaults={
                        'c': analysis.get('C'),
                        'si': analysis.get('Si'),
                        's': analysis.get('S'),
                        'p': analysis.get('P'),
                        'mn': analysis.get('Mn'),
                    }
                )
                if not created and any(analysis.values()):
                    # Update chemistry if provided
                    if analysis.get('C') is not None:
                        lot.c = analysis['C']
                    if analysis.get('Si') is not None:
                        lot.si = analysis['Si']
                    if analysis.get('S') is not None:
                        lot.s = analysis['S']
                    if analysis.get('P') is not None:
                        lot.p = analysis['P']
                    if analysis.get('Mn') is not None:
                        lot.mn = analysis['Mn']
                    lot.save()

            # Create release
            ship_to = data.get('shipTo', {})
            release = Release.objects.create(
                tenant=tenant,
                release_number=data.get('releaseNumber', ''),
                release_date=data.get('releaseDate'),
                customer_id_text=data.get('customerId', ''),
                customer_po=data.get('customerPO', ''),
                ship_via=data.get('shipVia', ''),
                fob=data.get('fob', ''),
                ship_to_name=ship_to.get('name', ''),
                ship_to_street=ship_to.get('street', ''),
                ship_to_city=ship_to.get('city', ''),
                ship_to_state=ship_to.get('state', ''),
                ship_to_zip=ship_to.get('zip', ''),
                lot=lot_code,
                lot_ref=lot,
                material_description=material.get('description', ''),
                quantity_net_tons=data.get('quantityNetTons'),
                special_instructions=data.get('specialInstructions', ''),
                status='OPEN',
            )

            # Create release loads from schedule
            schedule = data.get('schedule', [])
            for item in schedule:
                ReleaseLoad.objects.create(
                    tenant=tenant,
                    release=release,
                    seq=item.get('load', 1),
                    date=item.get('date'),
                    planned_tons=data.get('quantityNetTons'),  # Default to total
                    status='PENDING',
                )

            logger.info(
                f"Created release {release.release_number} with {len(schedule)} loads "
                f"for tenant {tenant.code}"
            )

            return Response({
                'status': 'created',
                'release_id': release.id,
                'release_number': release.release_number,
                'loads_created': len(schedule),
            }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Release approval error: {e}")
        return Response(
            {'error': f'Failed to create release: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )


# =============================================================================
# Pending Loads View
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_loads(request, tenant_code):
    """
    List all PENDING loads across all releases.

    GET /tenant/{tenant_code}/pigiron/pending-loads/
    """
    tenant = get_tenant_or_404(tenant_code)

    loads = ReleaseLoad.objects.filter(
        tenant=tenant,
        status='PENDING'
    ).select_related('release', 'release__lot_ref').order_by('date', 'release__release_number', 'seq')

    data = []
    for load in loads:
        release = load.release
        data.append({
            'id': load.id,
            'release_id': release.id,
            'release_number': release.release_number,
            'seq': load.seq,
            'line_number': load.line_number,
            'release_display': f"{release.release_number}-{load.seq}",
            'date': load.date,
            'planned_tons': load.planned_tons,
            'customer_id_text': release.customer_id_text,
            'customer_po': release.customer_po,
            'ship_to_name': release.ship_to_name,
            'ship_to_city': release.ship_to_city,
            'ship_to_state': release.ship_to_state,
            'material_description': release.material_description,
            'lot_code': release.lot_ref.code if release.lot_ref else release.lot,
            'chemistry': release.lot_ref.format_chemistry() if release.lot_ref else '',
            'special_instructions': release.special_instructions,
            'care_of_co': release.care_of_co,
        })

    return Response({
        'tenant': tenant.code,
        'count': len(data),
        'loads': data
    })


# =============================================================================
# BOL Views
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_bol(request, tenant_code):
    """
    Create BOL for a release load using BOLCreationService.

    POST /tenant/{tenant_code}/pigiron/bol/create/
    Body: {
        release_load_id: int,
        carrier_id: int,
        truck_id: int (optional),
        net_tons: decimal
    }
    """
    tenant = get_tenant_or_404(tenant_code)
    data = request.data

    # Validate required fields
    required = ['release_load_id', 'carrier_id', 'net_tons']
    missing = [f for f in required if f not in data]
    if missing:
        return Response(
            {'error': f'Missing required fields: {", ".join(missing)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Get related objects
        release_load = get_object_or_404(
            ReleaseLoad,
            id=data['release_load_id'],
            tenant=tenant
        )
        carrier = get_object_or_404(Carrier, id=data['carrier_id'])
        truck = None
        if data.get('truck_id'):
            truck = get_object_or_404(Truck, id=data['truck_id'])

        try:
            net_tons = Decimal(str(data['net_tons']))
            if net_tons <= 0:
                raise ValueError("Weight must be positive")
        except (InvalidOperation, ValueError) as e:
            return Response(
                {'error': f'Invalid net_tons: {e}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get user email for audit
        issued_by = getattr(request.user, 'email', '') or getattr(request.user, 'username', '')

        # Create BOL using service
        bol = BOLCreationService.create_bol(
            release_line=release_load,
            carrier=carrier,
            truck=truck,
            net_tons=net_tons,
            issued_by=issued_by,
        )

        logger.info(f"Created BOL {bol.bol_number} for tenant {tenant.code} by {issued_by}")

        return Response({
            'status': 'created',
            'bol': {
                'id': bol.id,
                'bol_number': bol.bol_number,
                'bol_date': bol.bol_date,
                'release_display': bol.release_display,
                'product_name': bol.product_name,
                'buyer_name': bol.buyer_name,
                'carrier_name': bol.carrier_name,
                'net_tons': bol.net_tons,
                'chemistry_display': bol.chemistry_display,
            }
        }, status=status.HTTP_201_CREATED)

    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"BOL creation error: {e}")
        return Response(
            {'error': f'Failed to create BOL: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bol_detail(request, tenant_code, bol_id):
    """
    Get BOL details.

    GET /tenant/{tenant_code}/pigiron/bol/{bol_id}/
    """
    tenant = get_tenant_or_404(tenant_code)
    bol = get_object_or_404(BOL, id=bol_id, tenant=tenant)

    return Response({
        'id': bol.id,
        'bol_number': bol.bol_number,
        'bol_date': bol.bol_date or bol.date,
        'is_void': bol.is_void,
        'voided_at': bol.voided_at,
        'voided_by': bol.voided_by,
        'void_reason': bol.void_reason,

        # Snapshot display fields
        'release_display': bol.release_display or bol.release_number,
        'product_name': bol.product_name,
        'buyer_name': bol.buyer_name,
        'carrier_name': bol.carrier_name,
        'truck_number': bol.truck_number,
        'trailer_number': bol.trailer_number,
        'chemistry_display': bol.chemistry_display,

        # Address
        'ship_to': bol.ship_to,
        'customer_po': bol.customer_po,
        'special_instructions': bol.special_instructions,
        'care_of_co': bol.care_of_co,

        # Weight
        'net_tons': bol.net_tons,
        'net_lbs': bol.total_weight_lbs,
        'official_weight_tons': bol.official_weight_tons,
        'official_weight_entered_by': bol.official_weight_entered_by,
        'official_weight_entered_at': bol.official_weight_entered_at,
        'weight_variance_tons': bol.weight_variance_tons,
        'effective_weight_tons': bol.effective_weight_tons,

        # PDF
        'pdf_url': bol.get_pdf_url(),
        'stamped_pdf_url': bol.stamped_pdf_url,

        # Audit
        'issued_by': bol.issued_by or bol.created_by_email,
        'created_at': bol.created_at,

        # Related IDs
        'release_line_id': bol.release_line_id,
        'lot_id': bol.lot_id,
        'product_id': bol.product_id,
        'customer_id': bol.customer_id,
        'carrier_id': bol.carrier_id,
        'truck_id': bol.truck_id,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def void_bol(request, tenant_code, bol_id):
    """
    Void a BOL.

    POST /tenant/{tenant_code}/pigiron/bol/{bol_id}/void/
    Body: { reason: string }
    """
    tenant = get_tenant_or_404(tenant_code)
    bol = get_object_or_404(BOL, id=bol_id, tenant=tenant)

    reason = request.data.get('reason', '').strip()
    if not reason:
        return Response(
            {'error': 'Void reason is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    voided_by = getattr(request.user, 'email', '') or getattr(request.user, 'username', '')

    try:
        bol = BOLCreationService.void_bol(bol, voided_by, reason)

        logger.info(f"Voided BOL {bol.bol_number} for tenant {tenant.code} by {voided_by}")

        return Response({
            'status': 'voided',
            'bol_number': bol.bol_number,
            'voided_at': bol.voided_at,
            'voided_by': bol.voided_by,
        })

    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_official_weight(request, tenant_code, bol_id):
    """
    Set official (certified) weight on BOL.

    POST /tenant/{tenant_code}/pigiron/bol/{bol_id}/official-weight/
    Body: { weight_tons: decimal }
    """
    tenant = get_tenant_or_404(tenant_code)
    bol = get_object_or_404(BOL, id=bol_id, tenant=tenant)

    if bol.is_void:
        return Response(
            {'error': 'Cannot set weight on voided BOL'},
            status=status.HTTP_400_BAD_REQUEST
        )

    weight_tons = request.data.get('weight_tons')
    if weight_tons is None:
        return Response(
            {'error': 'weight_tons is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        weight_tons = Decimal(str(weight_tons))
        if weight_tons <= 0:
            raise ValueError("Weight must be positive")
    except (InvalidOperation, ValueError) as e:
        return Response(
            {'error': f'Invalid weight_tons: {e}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    entered_by = getattr(request.user, 'email', '') or getattr(request.user, 'username', '')

    try:
        BOLCreationService.update_official_weight(bol, weight_tons, entered_by)

        logger.info(
            f"Set official weight {weight_tons} tons on BOL {bol.bol_number} "
            f"for tenant {tenant.code} by {entered_by}"
        )

        return Response({
            'status': 'updated',
            'bol_number': bol.bol_number,
            'official_weight_tons': bol.official_weight_tons,
            'weight_variance_tons': bol.weight_variance_tons,
            'weight_variance_percent': bol.weight_variance_percent,
        })

    except Exception as e:
        logger.error(f"Official weight error: {e}")
        return Response(
            {'error': f'Failed to set official weight: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bol_pdf(request, tenant_code, bol_id):
    """
    Generate/download BOL PDF.

    GET /tenant/{tenant_code}/pigiron/bol/{bol_id}/pdf/
    """
    tenant = get_tenant_or_404(tenant_code)
    bol = get_object_or_404(BOL, id=bol_id, tenant=tenant)

    # Import PDF generator
    from .services.pigiron_bol_pdf import generate_pigiron_bol_pdf

    try:
        pdf_bytes = generate_pigiron_bol_pdf(bol)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{bol.bol_number}.pdf"'
        return response

    except Exception as e:
        logger.error(f"PDF generation error for BOL {bol.bol_number}: {e}")
        return Response(
            {'error': f'Failed to generate PDF: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# Inventory Views
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def inventory_report(request, tenant_code):
    """
    Get inventory report (products + remaining tons).

    GET /tenant/{tenant_code}/pigiron/inventory/
    """
    tenant = get_tenant_or_404(tenant_code)

    products = Product.objects.filter(tenant=tenant, is_active=True)

    data = []
    for product in products:
        data.append({
            'id': product.id,
            'name': product.name,
            'start_tons': product.start_tons,
            'shipped_tons': product.shipped_tons,
            'remaining_tons': product.remaining_tons,
            'last_lot_code': product.last_lot_code,
        })

    return Response({
        'tenant': tenant.code,
        'products': data,
        'total_start_tons': sum(p['start_tons'] for p in data),
        'total_shipped_tons': sum(p['shipped_tons'] for p in data),
        'total_remaining_tons': sum(p['remaining_tons'] for p in data),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def product_list(request, tenant_code):
    """
    List products for tenant.

    GET /tenant/{tenant_code}/pigiron/products/
    """
    tenant = get_tenant_or_404(tenant_code)

    products = Product.objects.filter(tenant=tenant).order_by('name')

    data = []
    for product in products:
        data.append({
            'id': product.id,
            'name': product.name,
            'start_tons': product.start_tons,
            'shipped_tons': product.shipped_tons,
            'remaining_tons': product.remaining_tons,
            'is_active': product.is_active,
            'last_lot_code': product.last_lot_code,
            'c': product.c,
            'si': product.si,
            's': product.s,
            'p': product.p,
            'mn': product.mn,
        })

    return Response({
        'tenant': tenant.code,
        'count': len(data),
        'products': data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def lot_list(request, tenant_code):
    """
    List lots for tenant with chemistry.

    GET /tenant/{tenant_code}/pigiron/lots/
    """
    tenant = get_tenant_or_404(tenant_code)

    lots = Lot.objects.filter(tenant=tenant).select_related('product').order_by('-created_at')

    data = []
    for lot in lots:
        data.append({
            'id': lot.id,
            'code': lot.code,
            'product_id': lot.product_id,
            'product_name': lot.product.name if lot.product else None,
            'chemistry': lot.format_chemistry(),
            'c': lot.c,
            'si': lot.si,
            's': lot.s,
            'p': lot.p,
            'mn': lot.mn,
            'created_at': lot.created_at,
        })

    return Response({
        'tenant': tenant.code,
        'count': len(data),
        'lots': data
    })
