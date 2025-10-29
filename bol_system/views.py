from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from django.db import models, connection
from .models import Product, Customer, Carrier, Truck, BOL, Release, ReleaseLoad
from .serializers import ProductSerializer, CustomerSerializer, CarrierSerializer, TruckSerializer, ReleaseSerializer
from .pdf_generator import generate_bol_pdf
from .release_parser import parse_release_pdf
import logging
import os
import base64
import tempfile

logger = logging.getLogger(__name__)

# Health check endpoint (no auth required for monitoring)
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint for monitoring and deployment verification"""
    try:
        # Check database connectivity
        connection.ensure_connection()
        return Response({
            'status': 'healthy',
            'database': 'connected',
            'service': 'primetrade'
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return Response({
            'status': 'unhealthy',
            'error': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

# Product endpoints
class ProductListView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Product.objects.filter(is_active=True).order_by('name')

# Customer endpoints
class CustomerListView(generics.ListCreateAPIView):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Customer.objects.filter(is_active=True).order_by('customer')

# Carrier endpoints with trucks
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def carrier_list(request):
    try:
        if request.method == 'POST':
            # Create or update carrier
            data = request.data
            carrier_id = data.get('id')

            if carrier_id:
                # Update existing carrier
                try:
                    carrier = Carrier.objects.get(id=carrier_id)
                    carrier.carrier_name = data.get('carrier_name', carrier.carrier_name)
                    carrier.contact_name = data.get('contact_name', '')
                    carrier.phone = data.get('phone', '')
                    carrier.email = data.get('email', '')
                    carrier.is_active = data.get('is_active', True)
                    carrier.save()

                    # Handle trucks if provided
                    if 'trucks' in data:
                        # Delete existing trucks and recreate
                        carrier.trucks.all().delete()
                        for truck_data in data['trucks']:
                            Truck.objects.create(
                                carrier=carrier,
                                truck_number=truck_data.get('truck_number', ''),
                                trailer_number=truck_data.get('trailer_number', ''),
                                is_active=truck_data.get('is_active', True)
                            )

                    logger.info(f"Carrier {carrier.id} updated by {request.user.username}")
                    return Response({'ok': True, 'id': carrier.id})
                except Carrier.DoesNotExist:
                    logger.error(f"Carrier {carrier_id} not found")
                    return Response({'error': 'Carrier not found'}, status=status.HTTP_404_NOT_FOUND)
            else:
                # Create new carrier
                if not data.get('carrier_name'):
                    return Response(
                        {'error': 'carrier_name is required'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                carrier = Carrier.objects.create(
                    carrier_name=data.get('carrier_name'),
                    contact_name=data.get('contact_name', ''),
                    phone=data.get('phone', ''),
                    email=data.get('email', ''),
                    is_active=data.get('is_active', True)
                )
                logger.info(f"Carrier {carrier.id} created by {request.user.username}")
                return Response({'ok': True, 'id': carrier.id})

        # GET request - list carriers
        carriers = Carrier.objects.filter(is_active=True).order_by('carrier_name')
        result = []
        for carrier in carriers:
            trucks = carrier.trucks.filter(is_active=True)
            carrier_data = CarrierSerializer(carrier).data
            carrier_data['trucks'] = TruckSerializer(trucks, many=True).data
            result.append(carrier_data)
        return Response(result)
    except ValueError as e:
        logger.error(f"Validation error in carrier_list: {str(e)}")
        return Response(
            {'error': 'Invalid input data', 'detail': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Unexpected error in carrier_list: {str(e)}")
        return Response(
            {'error': 'An unexpected error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# BOL preview (no database save)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def preview_bol(request):
    """
    Generate a preview PDF without saving to database
    Returns base64-encoded PDF for display in modal
    """
    try:
        data = request.data

        # Validation
        required_fields = ['date', 'productId', 'buyerName', 'shipTo', 'netTons']
        for field in required_fields:
            if not data.get(field):
                return Response({'error': f'Missing field: {field}'},
                              status=status.HTTP_400_BAD_REQUEST)

        # Validate net_tons is positive number
        try:
            net_tons = float(data['netTons'])
            if net_tons <= 0:
                return Response(
                    {'error': 'net_tons must be positive'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'error': 'net_tons must be a valid number'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get related objects for display names
        try:
            product = Product.objects.get(id=data['productId'])
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            carrier = Carrier.objects.get(id=data.get('carrierId', ''))
        except Carrier.DoesNotExist:
            return Response({'error': 'Carrier not found'}, status=status.HTTP_404_NOT_FOUND)

        truck = None
        if data.get('truckId'):
            try:
                truck = Truck.objects.get(id=data.get('truckId'))
            except Truck.DoesNotExist:
                return Response({'error': 'Truck not found'}, status=status.HTTP_404_NOT_FOUND)

        # Build preview data dictionary
        preview_data = {
            'bolNumber': 'PREVIEW',
            'productName': product.name,
            'date': data['date'],
            'buyerName': data['buyerName'],
            'shipTo': data['shipTo'],
            'carrierName': carrier.carrier_name,
            'truckNumber': truck.truck_number if truck else data.get('truckNo', ''),
            'trailerNumber': truck.trailer_number if truck else data.get('trailerNo', ''),
            'netTons': net_tons,
            'customerPO': data.get('customerPO', ''),
        }

        # Generate temporary PDF
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_path = temp_file.name
        temp_file.close()

        try:
            generate_bol_pdf(preview_data, output_path=temp_path)

            # Read PDF and encode as base64
            with open(temp_path, 'rb') as pdf_file:
                pdf_bytes = pdf_file.read()
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

            logger.info(f"BOL preview generated by {request.user.username}")

            return Response({
                'ok': True,
                'pdfBase64': pdf_base64
            })

        finally:
            # Cleanup temp file
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass  # Ignore cleanup errors

    except ValueError as e:
        logger.error(f"Validation error in preview_bol: {str(e)}")
        return Response(
            {'error': 'Invalid input data', 'detail': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Unexpected error in preview_bol: {str(e)}")
        return Response({'ok': False, 'error': 'An unexpected error occurred'},
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# BOL creation (confirm and save to database)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_bol(request):
    try:
        data = request.data

        # Validation
        required_fields = ['date', 'productId', 'buyerName', 'shipTo', 'netTons']
        for field in required_fields:
            if not data.get(field):
                return Response({'error': f'Missing field: {field}'},
                              status=status.HTTP_400_BAD_REQUEST)

        # Validate net_tons is positive number
        try:
            net_tons = float(data['netTons'])
            if net_tons <= 0:
                return Response(
                    {'error': 'net_tons must be positive'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'error': 'net_tons must be a valid number'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get related objects
        try:
            product = Product.objects.get(id=data['productId'])
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            carrier = Carrier.objects.get(id=data.get('carrierId', ''))
        except Carrier.DoesNotExist:
            return Response({'error': 'Carrier not found'}, status=status.HTTP_404_NOT_FOUND)

        customer = None
        if data.get('customerId'):
            try:
                customer = Customer.objects.get(id=data.get('customerId'))
            except Customer.DoesNotExist:
                return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)

        truck = None
        if data.get('truckId'):
            try:
                truck = Truck.objects.get(id=data.get('truckId'))
            except Truck.DoesNotExist:
                return Response({'error': 'Truck not found'}, status=status.HTTP_404_NOT_FOUND)

        # Create BOL
        bol = BOL.objects.create(
            product=product,
            product_name=product.name,
            date=data['date'],
            buyer_name=data['buyerName'],
            ship_to=data['shipTo'],
            carrier=carrier,
            carrier_name=carrier.carrier_name,
            truck=truck,
            truck_number=truck.truck_number if truck else data.get('truckNo', ''),
            trailer_number=truck.trailer_number if truck else data.get('trailerNo', ''),
            net_tons=net_tons,
            notes=data.get('notes', ''),
            customer=customer,
            customer_po=data.get('customerPO', ''),
            created_by_email=f'{request.user.username}@primetrade.com'
        )

        logger.info(f"BOL {bol.bol_number} created by {request.user.username} with {net_tons} tons")

        # Generate PDF
        try:
            pdf_url = generate_bol_pdf(bol)
            bol.pdf_url = pdf_url
            bol.save()
            logger.info(f"Generated PDF for BOL {bol.bol_number} at {pdf_url}")
        except Exception as e:
            logger.error(f"Failed to generate PDF for BOL {bol.bol_number}: {str(e)}")
            # Continue without PDF - don't fail the BOL creation
            pdf_url = f"/media/bol_pdfs/{bol.bol_number}.pdf"
            bol.pdf_url = pdf_url
            bol.save()

        return Response({
            'ok': True,
            'bolNo': bol.bol_number,
            'bolId': bol.id,
            'pdfUrl': pdf_url
        })

    except ValueError as e:
        logger.error(f"Validation error in create_bol: {str(e)}")
        return Response(
            {'error': 'Invalid input data', 'detail': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Unexpected error in create_bol: {str(e)}")
        return Response({'ok': False, 'error': 'An unexpected error occurred'},
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Inventory balances
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def balances(request):
    try:
        products = Product.objects.filter(is_active=True)
        result = []
        for product in products:
            shipped = BOL.objects.filter(product=product).aggregate(
                total=models.Sum('net_tons')
            )['total'] or 0

            result.append({
                'id': product.id,
                'name': product.name,
                'startTons': float(product.start_tons),
                'shipped': float(shipped),
                'remaining': float(product.start_tons - shipped)
            })

        return Response(result)
    except Exception as e:
        logger.error(f"Error in balances: {str(e)}")
        return Response(
            {'error': 'An unexpected error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# =============================
# Release management endpoints
# =============================
from datetime import datetime

def _parse_date_any(s: str):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_release(request):
    try:
        data = request.data if isinstance(request.data, dict) else {}
        # Required
        release_number = data.get('releaseNumber') or data.get('release_number')
        if not release_number:
            return Response({'error': 'releaseNumber required'}, status=status.HTTP_400_BAD_REQUEST)

        # Create or upsert release
        rel, created = Release.objects.get_or_create(
            release_number=release_number,
            defaults={
                'release_date': _parse_date_any(data.get('releaseDate')),
                'customer_id_text': data.get('customerId', ''),
                'customer_po': data.get('customerPO', ''),
                'ship_via': data.get('shipVia', ''),
                'fob': data.get('fob', ''),
                'ship_to_name': (data.get('shipTo') or {}).get('name', ''),
                'ship_to_street': (data.get('shipTo') or {}).get('street', ''),
                'ship_to_city': (data.get('shipTo') or {}).get('city', ''),
                'ship_to_state': (data.get('shipTo') or {}).get('state', ''),
                'ship_to_zip': (data.get('shipTo') or {}).get('zip', ''),
                'lot': (data.get('material') or {}).get('lot', ''),
                'material_description': (data.get('material') or {}).get('description', ''),
                'quantity_net_tons': data.get('quantityNetTons', None),
                'updated_by': request.user.username,
            }
        )
        if not created:
            # Update core fields if re-approving
            rel.release_date = _parse_date_any(data.get('releaseDate')) or rel.release_date
            for f, k in [
                ('customer_id_text','customerId'),
                ('customer_po','customerPO'),
                ('ship_via','shipVia'),
                ('fob','fob')
            ]:
                v = data.get(k)
                if v:
                    setattr(rel, f, v)
            ship = data.get('shipTo') or {}
            for f in ['name','street','city','state','zip']:
                if ship.get(f):
                    setattr(rel, f'ship_to_{f}', ship.get(f))
            mat = data.get('material') or {}
            if mat.get('lot'): rel.lot = mat.get('lot')
            if mat.get('description'): rel.material_description = mat.get('description')
            if data.get('quantityNetTons') is not None:
                rel.quantity_net_tons = data.get('quantityNetTons')
            rel.updated_by = request.user.username
            rel.save()

        # Replace loads
        rel.loads.all().delete()
        sched = data.get('schedule') or []
        per_load = None
        try:
            if data.get('quantityNetTons') and len(sched):
                per_load = float(data['quantityNetTons'])/max(len(sched),1)
        except Exception:
            per_load = None
        for i, row in enumerate(sched, start=1):
            ReleaseLoad.objects.create(
                release=rel,
                seq=i,
                date=_parse_date_any(row.get('date') if isinstance(row, dict) else None),
                planned_tons=per_load,
                updated_by=request.user.username,
            )

        return Response({'ok': True, 'id': rel.id, 'created': created, 'release': ReleaseSerializer(rel).data})
    except Exception as e:
        logger.error(f"approve_release error: {e}", exc_info=True)
        return Response({'error': 'Failed to save release', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def open_releases(request):
    try:
        rels = Release.objects.filter(status='OPEN').order_by('-created_at')
        result = []
        for r in rels:
            loads_total = r.loads.count()
            shipped = r.loads.filter(status='SHIPPED').count()
            remaining = loads_total - shipped
            tons_total = float(r.quantity_net_tons or 0)
            tons_shipped = float(r.loads.filter(status='SHIPPED').aggregate(sum=models.Sum('planned_tons'))['sum'] or 0)
            tons_remaining = max(0.0, tons_total - tons_shipped)
            next_date = r.loads.filter(status='PENDING').order_by('date').values_list('date', flat=True).first()
            last_shipped = r.loads.filter(status='SHIPPED').order_by('-date').values_list('date', flat=True).first()
            result.append({
                'id': r.id,
                'releaseNumber': r.release_number,
                'customer': r.customer_id_text,
                'totalLoads': loads_total,
                'loadsShipped': shipped,
                'loadsRemaining': remaining,
                'totalTons': tons_total,
                'tonsShipped': tons_shipped,
                'tonsRemaining': tons_remaining,
                'nextScheduledDate': next_date,
                'lastShippedDate': last_shipped,
            })
        return Response(result)
    except Exception as e:
        logger.error(f"open_releases error: {e}", exc_info=True)
        return Response({'error': 'Failed to load open releases', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# BOL history
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bol_history(request):
    try:
        product_id = request.GET.get('productId')
        if not product_id:
            return Response({'error': 'productId required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

        bols = BOL.objects.filter(product=product).order_by('date')

        shipped = sum(float(bol.net_tons) for bol in bols)
        remaining = float(product.start_tons) - shipped

        return Response({
            'summary': {
                'start': float(product.start_tons),
                'shipped': shipped,
                'remaining': remaining
            },
            'rows': [
                {
                    'id': bol.id,
                    'bolNo': bol.bol_number,
                    'date': bol.date,
                    'truckNo': bol.truck_number,
                    'netTons': float(bol.net_tons),
                    'pdfUrl': bol.pdf_url
                }
                for bol in bols
            ]
        })

    except Exception as e:
        logger.error(f"Error in bol_history: {str(e)}")
        return Response(
            {'error': 'An unexpected error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# BOL detail view
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bol_detail(request, bol_id):
    try:
        bol = BOL.objects.get(id=bol_id)
        return Response({
            'id': bol.id,
            'bolNo': bol.bol_number,
            'productName': bol.product_name,
            'buyerName': bol.buyer_name,
            'shipTo': bol.ship_to,
            'carrierName': bol.carrier_name,
            'truckNo': bol.truck_number,
            'trailerNo': bol.trailer_number,
            'date': bol.date,
            'netTons': float(bol.net_tons),
            'notes': bol.notes,
            'pdfUrl': bol.pdf_url
        })
    except BOL.DoesNotExist:
        logger.error(f"BOL {bol_id} not found")
        return Response({'error': 'BOL not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in bol_detail: {str(e)}")
        return Response(
            {'error': 'An unexpected error occurred'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# CSRF-exempt Session auth for file upload parse endpoint only
class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # Disable CSRF check; session must still be authenticated

# Release upload and parse (Phase 1: parse only)
@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def upload_release(request):
    """
    Accept a release PDF, parse header/material/schedule fields, and return JSON.
    Does NOT write to DB yet (Phase 1). Stores nothing server-side.

    Optional query param: ?ai=1 to enable local AI fallback (Ollama) when fields
    are missing or format varies.
    """
    try:
        f = request.FILES.get('file')
        if not f:
            return Response({'error': 'No file provided (form field "file").'}, status=status.HTTP_400_BAD_REQUEST)

        ai_param = str(request.query_params.get('ai', '0')).lower()
        if ai_param in ('1', 'true', 'yes', 'local'):
            ai_mode = 'local'
        elif ai_param in ('cloud', 'remote', 'groq'):
            ai_mode = 'cloud'
        else:
            ai_mode = None
        data = parse_release_pdf(f, ai_mode=ai_mode)
        return Response({'ok': True, 'parsed': data, 'ai': ai_mode})
    except Exception as e:
        logger.error(f"Error parsing release PDF: {e}", exc_info=True)
        return Response({'error': 'Failed to parse PDF', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
