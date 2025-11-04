from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from django.db import models, connection, transaction, IntegrityError
from django.db.models.functions import Coalesce
from .models import Product, Customer, Carrier, Truck, BOL, Release, ReleaseLoad, CustomerShipTo, Lot, AuditLog
from .serializers import ProductSerializer, CustomerSerializer, CarrierSerializer, TruckSerializer, ReleaseSerializer, ReleaseLoadSerializer, CustomerShipToSerializer, AuditLogSerializer
from .pdf_generator import generate_bol_pdf
from .release_parser import parse_release_pdf
import logging
import os
import base64
import tempfile
from decimal import Decimal
import re
import json
import urllib.request
import urllib.error
from datetime import datetime

logger = logging.getLogger(__name__)

def _ip_of(request):
    try:
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR','')
    except Exception:
        return ''

def audit(request, action: str, obj=None, message: str = '', extra: dict | None = None):
    try:
        from .models import AuditLog  # local import to avoid circular during migrations
        entry = AuditLog.objects.create(
            action=action,
            object_type=(obj.__class__.__name__ if obj is not None else ''),
            object_id=(str(getattr(obj, 'id', '') or getattr(obj, 'pk', '') or '')),
            message=message,
            user_email=(getattr(request.user, 'email', '') or getattr(request.user, 'username', '')),
            ip=_ip_of(request),
            method=getattr(request, 'method', ''),
            path=getattr(request, 'path', ''),
            user_agent=request.META.get('HTTP_USER_AGENT',''),
            extra=extra
        )
        # Optional Galactica forwarder
        try:
            url = os.getenv('GALACTICA_URL')
            if url:
                payload = {
                    'ts': datetime.utcnow().isoformat() + 'Z',
                    'action': action,
                    'object_type': entry.object_type,
                    'object_id': entry.object_id,
                    'message': message,
                    'user_email': entry.user_email,
                    'ip': entry.ip,
                    'method': entry.method,
                    'path': entry.path,
                    'user_agent': entry.user_agent,
                    'extra': extra,
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json', 'Authorization': f"Bearer {os.getenv('GALACTICA_API_KEY','')}"},
                    method='POST'
                )
                urllib.request.urlopen(req, timeout=3)
        except Exception as _e:
            # Do not break main flow if external logging fails
            logger.debug(f"Galactica logging skipped: {_e}")
    except Exception as e:
        logger.warning(f"Audit log failed: {e}")

# CSRF-exempt Session auth (used by upload_release and approve_release)
class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # Disable CSRF check; session must still be authenticated

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

    # Support upsert via POST so the existing frontend can use one endpoint
    def post(self, request, *args, **kwargs):
        try:
            data = request.data if isinstance(request.data, dict) else {}
            pid = data.get('id')
            name = (data.get('name') or '').strip()
            start = data.get('start_tons', None)
            is_active = data.get('is_active', True)

            if pid:
                # Update existing product
                try:
                    prod = Product.objects.get(id=pid)
                except Product.DoesNotExist:
                    return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
                if name:
                    prod.name = name
                if start is not None:
                    try:
                        prod.start_tons = Decimal(str(start))
                    except Exception:
                        return Response({'error': 'start_tons must be a number'}, status=status.HTTP_400_BAD_REQUEST)
                prod.is_active = bool(is_active)
                prod.updated_by = request.user.username
                try:
                    prod.save()
                except IntegrityError as e:
                    return Response({'error': 'Product already exists', 'detail': str(e)}, status=status.HTTP_409_CONFLICT)
                audit(request, 'PRODUCT_UPDATED', prod, f"Product updated: {prod.name}")
                return Response({'ok': True, 'id': prod.id})
            else:
                # Create new product
                if not name:
                    return Response({'error': 'name is required'}, status=status.HTTP_400_BAD_REQUEST)
                try:
                    start_val = Decimal(str(start if start is not None else '0'))
                except Exception:
                    return Response({'error': 'start_tons must be a number'}, status=status.HTTP_400_BAD_REQUEST)
                try:
                    prod = Product.objects.create(
                        name=name,
                        start_tons=start_val,
                        is_active=bool(is_active),
                        updated_by=request.user.username,
                    )
                except IntegrityError as e:
                    return Response({'error': 'Product already exists', 'detail': str(e)}, status=status.HTTP_409_CONFLICT)
                audit(request, 'PRODUCT_CREATED', prod, f"Product created: {prod.name}")
                return Response({'ok': True, 'id': prod.id})
        except Exception as e:
            logger.error(f"product upsert error: {e}", exc_info=True)
            return Response({'error': 'Failed to save product', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Customer endpoints
class CustomerListView(generics.ListCreateAPIView):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Customer.objects.filter(is_active=True).order_by('customer')

# Ship-To endpoints (per-customer)
@api_view(['GET','POST'])
@permission_classes([IsAuthenticated])
def customer_shiptos(request, customer_id: int):
    try:
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'GET':
            rows = customer.ship_tos.order_by('name','street','city').all()
            return Response(CustomerShipToSerializer(rows, many=True).data)

        # POST upsert
        data = request.data if isinstance(request.data, dict) else {}
        shipto_id = data.get('id')
        name = (data.get('name') or '').strip()
        street = (data.get('street') or '').strip()
        street2 = (data.get('street2') or '').strip()
        city = (data.get('city') or '').strip()
        state = (data.get('state') or '').strip()[:2]
        zip_code = (data.get('zip') or '').strip()
        is_active = data.get('is_active', True)

        if not all([street, city, state, zip_code]):
            return Response({'error': 'street, city, state, zip are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if shipto_id:
                st = CustomerShipTo.objects.get(id=shipto_id, customer=customer)
                st.name = name
                st.street = street
                st.street2 = street2
                st.city = city
                st.state = state
                st.zip = zip_code
                st.is_active = is_active
                st.updated_by = request.user.username
                st.save()
                audit(request, 'CUSTOMER_SHIPTO_UPDATED', st, f"Ship-To updated for customer {customer.customer}")
                return Response({'ok': True, 'id': st.id})
            else:
                st, created = CustomerShipTo.objects.get_or_create(
                    customer=customer,
                    street=street,
                    city=city,
                    state=state,
                    zip=zip_code,
                    defaults={'name': name, 'street2': street2, 'is_active': is_active, 'updated_by': request.user.username}
                )
                if not created:
                    updated = False
                    if name and st.name != name:
                        st.name = name
                        updated = True
                    if street2 and st.street2 != street2:
                        st.street2 = street2
                        updated = True
                    if updated:
                        st.updated_by = request.user.username
                        st.save(update_fields=['name', 'street2', 'updated_by'])
                audit(request, 'CUSTOMER_SHIPTO_CREATED' if created else 'CUSTOMER_SHIPTO_UPSERT', st, f"Ship-To saved for customer {customer.customer}")
                return Response({'ok': True, 'id': st.id, 'created': created})
        except CustomerShipTo.DoesNotExist:
            return Response({'error': 'Ship-To not found'}, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError as e:
            return Response({'error': 'Duplicate Ship-To for this customer', 'detail': str(e)}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            logger.error(f"customer_shiptos error: {e}", exc_info=True)
            return Response({'error': 'Failed to save ship-to', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"customer_shiptos outer error: {e}", exc_info=True)
        return Response({'error': 'Unexpected error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                    audit(request, 'CARRIER_UPDATED', carrier, f"Carrier updated: {carrier.carrier_name}")

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
                audit(request, 'CARRIER_CREATED', carrier, f"Carrier created: {carrier.carrier_name}")
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

        # If binding to a pending load, enforce required fields differently
        load_id = data.get('loadId') or data.get('load_id')
        if load_id:
            # Basic required for bound flow
            for field in ['date', 'netTons']:
                if not data.get(field):
                    return Response({'error': f'Missing field: {field}'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Legacy free-form flow
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

        # Resolve from load if provided
        release_load = None
        release_obj = None
        product = None
        customer = None
        carrier = None

        if load_id:
            try:
                release_load = ReleaseLoad.objects.select_related('release', 'release__customer_ref', 'release__carrier_ref', 'release__lot_ref', 'release__lot_ref__product').get(id=load_id)
            except ReleaseLoad.DoesNotExist:
                return Response({'error': 'Load not found'}, status=status.HTTP_404_NOT_FOUND)
            if release_load.status != 'PENDING':
                return Response({'error': 'This load has already shipped'}, status=status.HTTP_409_CONFLICT)
            release_obj = release_load.release
            # Product from lot_ref.product or require productId
            product = getattr(getattr(release_obj, 'lot_ref', None), 'product', None)
            if not product and data.get('productId'):
                try:
                    product = Product.objects.get(id=data['productId'])
                except Product.DoesNotExist:
                    return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
            if not product:
                return Response({'error': 'Product not set for this release/lot'}, status=status.HTTP_400_BAD_REQUEST)
            customer = getattr(release_obj, 'customer_ref', None)
            # Carrier: prefer payload carrierId override, else release.carrier_ref must exist
            if data.get('carrierId'):
                try:
                    carrier = Carrier.objects.get(id=data.get('carrierId'))
                except Carrier.DoesNotExist:
                    return Response({'error': 'Carrier not found'}, status=status.HTTP_404_NOT_FOUND)
            else:
                carrier = getattr(release_obj, 'carrier_ref', None)
                if not carrier:
                    return Response({'error': 'Carrier is required'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Legacy resolution
            try:
                product = Product.objects.get(id=data['productId'])
            except Product.DoesNotExist:
                return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
            try:
                carrier = Carrier.objects.get(id=data.get('carrierId', ''))
            except Carrier.DoesNotExist:
                return Response({'error': 'Carrier not found'}, status=status.HTTP_404_NOT_FOUND)
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

        # Build locked fields if using load
        if release_load:
            buyer_name = getattr(customer, 'customer', None) or release_obj.customer_id_text
            # Build ship-to address with optional street2
            addr_parts = [release_obj.ship_to_name, release_obj.ship_to_street]
            if release_obj.ship_to_street2:
                addr_parts.append(release_obj.ship_to_street2)
            city_line = ", ".join([p for p in [release_obj.ship_to_city, release_obj.ship_to_state] if p])
            zip_part = f" {release_obj.ship_to_zip}" if release_obj.ship_to_zip else ''
            addr_parts.append(f"{city_line}{zip_part}".strip())
            ship_to_text = "\n".join([p for p in addr_parts if p]).strip()
            customer_po = release_obj.customer_po or ''
        else:
            buyer_name = data['buyerName']
            ship_to_text = data['shipTo']
            customer_po = data.get('customerPO', '')

        # Create BOL
        bol = BOL.objects.create(
            product=product,
            product_name=product.name,
            date=data['date'],
            buyer_name=buyer_name,
            ship_to=ship_to_text,
            carrier=carrier,
            carrier_name=carrier.carrier_name,
            truck=truck,
            truck_number=truck.truck_number if truck else data.get('truckNo', ''),
            trailer_number=truck.trailer_number if truck else data.get('trailerNo', ''),
            net_tons=net_tons,
            notes=data.get('notes', ''),
            customer=customer,
            customer_po=customer_po,
            created_by_email=f'{request.user.username}@primetrade.com',
            lot_ref=release_obj.lot_ref if release_load else None,
            release_number=f'{release_obj.release_number}-{release_load.seq}' if release_load else '',
            special_instructions=release_obj.special_instructions if release_load else ''
        )

        # If load provided, mark shipped and attach
        if release_load:
            release_load.status = 'SHIPPED'
            release_load.bol = bol
            release_load.actual_tons = net_tons
            release_load.save(update_fields=['status','bol','actual_tons','updated_at','updated_by'])
            # If all loads shipped, close release
            try:
                if release_load.release.loads.filter(status='PENDING').count() == 0:
                    release_load.release.status = 'COMPLETE'
                    release_load.release.save(update_fields=['status','updated_at'])
            except Exception:
                pass

        logger.info(f"BOL {bol.bol_number} created by {request.user.username} with {net_tons} tons")
        audit(request, 'BOL_CREATED', bol, f"BOL created {bol.bol_number}", {'netTons': net_tons})

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
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def approve_release(request):
    try:
        data = request.data if isinstance(request.data, dict) else {}
        logger.info(f"approve_release called with schedule: {len(data.get('schedule', []))} items, material.analysis: {bool(data.get('material', {}).get('analysis'))}")
        # Required
        release_number = data.get('releaseNumber') or data.get('release_number')
        if not release_number:
            return Response({'error': 'releaseNumber required'}, status=status.HTTP_400_BAD_REQUEST)

        # Reject duplicates
        if Release.objects.filter(release_number=release_number).exists():
            existing = Release.objects.filter(release_number=release_number).first()
            audit(request, 'RELEASE_APPROVE_DUPLICATE', existing, f"Duplicate attempt: {release_number}", {'releaseNumber': release_number})
            return Response(
                {
                    'error': 'Duplicate release_number',
                    'releaseNumber': release_number,
                    'id': existing.id if existing else None,
                },
                status=status.HTTP_409_CONFLICT
            )

        # Chemistry tolerance (configurable)
        try:
            tol = float(os.getenv('LOT_CHEM_TOLERANCE', '0.01'))
        except Exception:
            tol = 0.01

        # Normalize inputs
        release_date = _parse_date_any(data.get('releaseDate'))
        customer_id_text = (data.get('customerId') or '').strip()
        ship = data.get('shipTo') or data.get('shipToRaw') or {}
        # Ship-To parsing fallback if only provide combined address
        street = ship.get('street') or ''
        street2 = ship.get('street2') or ''
        city = ship.get('city') or ''
        state = ship.get('state') or ''
        zip_code = ship.get('zip') or ''
        if (not street or not city or not state or not zip_code) and ship.get('address'):
            addr = ship.get('address')
            # Try to parse "<street>\n<city>, <ST> <ZIP>" or "<street>, <city>, <ST> <ZIP>"
            m = re.search(r"^(.*?)[\n,]\s*([^,\n]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)$", addr.strip())
            if m:
                street = street or m.group(1).strip()
                city = city or m.group(2).strip()
                state = state or m.group(3).strip()
                zip_code = zip_code or m.group(4).strip()

        carrier_name = (data.get('carrier') or data.get('shipVia') or data.get('carrierName') or '').strip()

        mat = data.get('material') or {}
        lot_code = (mat.get('lot') or '').strip()
        analysis = mat.get('analysis') or {}

        # Determine or create Product from material description (if provided)
        desc = (mat.get('description') or '').strip()
        product_obj = None
        if desc:
            try:
                product_obj = Product.objects.get(name__iexact=desc)
            except Product.DoesNotExist:
                product_obj = Product.objects.create(
                    name=desc,
                    start_tons=Decimal('0'),
                    is_active=True,
                    updated_by=request.user.username,
                )

        with transaction.atomic():
            # Create Release (text fields captured for audit)
            rel = Release.objects.create(
                release_number=release_number,
                release_date=release_date,
                customer_id_text=customer_id_text,
                customer_po=data.get('customerPO', ''),
                ship_via=data.get('shipVia', ''),
                fob=data.get('fob', ''),
                ship_to_name=ship.get('name', ''),
                ship_to_street=street,
                ship_to_street2=street2,
                ship_to_city=city,
                ship_to_state=state,
                ship_to_zip=zip_code,
                lot=lot_code,
                material_description=(mat.get('description') or ''),
                quantity_net_tons=data.get('quantityNetTons', None),
                special_instructions=data.get('specialInstructions', ''),
                updated_by=request.user.username,
            )

            # Upsert Customer
            customer_obj = None
            if customer_id_text:
                customer_obj, _ = Customer.objects.get_or_create(
                    customer=customer_id_text,
                    defaults={
                        'address': street or '',
                        'city': city or '',
                        'state': (state or '')[:2],
                        'zip': zip_code or '',
                        'is_active': True,
                    }
                )
                rel.customer_ref = customer_obj

            # Upsert Ship-To
            ship_to_obj = None
            if customer_obj and street and city and state and zip_code:
                ship_to_obj, _ = CustomerShipTo.objects.get_or_create(
                    customer=customer_obj,
                    street=street,
                    city=city,
                    state=state[:2],
                    zip=zip_code,
                    defaults={'name': ship.get('name', ''), 'street2': street2, 'is_active': True}
                )
                # If name or street2 updated, keep latest values
                updated = False
                if ship.get('name') and ship_to_obj.name != ship.get('name'):
                    ship_to_obj.name = ship.get('name')
                    updated = True
                if street2 and ship_to_obj.street2 != street2:
                    ship_to_obj.street2 = street2
                    updated = True
                if updated:
                    ship_to_obj.save(update_fields=['name', 'street2'])
                rel.ship_to_ref = ship_to_obj

            # Upsert Carrier
            carrier_obj = None
            if carrier_name:
                carrier_obj, _ = Carrier.objects.get_or_create(
                    carrier_name=carrier_name,
                    defaults={'is_active': True}
                )
                rel.carrier_ref = carrier_obj

            # Upsert/validate Lot
            lot_obj = None
            if lot_code:
                try:
                    lot_obj = Lot.objects.get(code=lot_code)
                    # Validate chemistry within tolerance
                    mismatches = []
                    def _val(x):
                        try:
                            return float(x) if x is not None else None
                        except Exception:
                            return None
                    for k_model, k_parsed in [('c','C'),('si','Si'),('s','S'),('p','P'),('mn','Mn')]:
                        existing = getattr(lot_obj, k_model, None)
                        parsed = analysis.get(k_parsed)
                        exf = _val(existing)
                        paf = _val(parsed)
                        if exf is not None and paf is not None:
                            if abs(exf - paf) > tol:
                                mismatches.append({'element': k_parsed, 'existing': exf, 'parsed': paf, 'delta': abs(exf - paf)})
                    if mismatches:
                        return Response({'error': 'Lot chemistry mismatch', 'lot': lot_code, 'tolerance': tol, 'mismatches': mismatches}, status=status.HTTP_409_CONFLICT)
                    # If lot exists and has no product but we determined one, set it
                    if product_obj and not lot_obj.product:
                        lot_obj.product = product_obj
                        lot_obj.save(update_fields=['product'])
                except Lot.DoesNotExist:
                    # Create draft lot with analysis
                    lot_obj = Lot.objects.create(
                        code=lot_code,
                        product=product_obj,
                        c=Decimal(str(analysis.get('C'))) if analysis.get('C') is not None else None,
                        si=Decimal(str(analysis.get('Si'))) if analysis.get('Si') is not None else None,
                        s=Decimal(str(analysis.get('S'))) if analysis.get('S') is not None else None,
                        p=Decimal(str(analysis.get('P'))) if analysis.get('P') is not None else None,
                        mn=Decimal(str(analysis.get('Mn'))) if analysis.get('Mn') is not None else None,
                        updated_by=request.user.username,
                    )
                rel.lot_ref = lot_obj

            # Mirror latest lot chemistry onto product for quick double-checking
            try:
                target_product = product_obj or (lot_obj.product if lot_obj else None)
                if target_product and lot_obj:
                    changed = False
                    if target_product.last_lot_code != lot_obj.code:
                        target_product.last_lot_code = lot_obj.code; changed = True
                    for f in ['c','si','s','p','mn']:
                        newv = getattr(lot_obj, f, None)
                        if newv is not None and getattr(target_product, f) != newv:
                            setattr(target_product, f, newv); changed = True
                    if changed:
                        target_product.updated_by = request.user.username
                        target_product.save()
            except Exception:
                pass

            # Persist Release with refs
            rel.save()
            audit(request, 'RELEASE_APPROVE_CREATED', rel, f"Approved release {rel.release_number}", {'loads': rel.total_loads})

            # Create loads
            sched = data.get('schedule') or []
            logger.info(f"Creating {len(sched)} loads for release {rel.release_number}")
            per_load = None
            try:
                if data.get('quantityNetTons') and len(sched):
                    per_load = float(data['quantityNetTons'])/max(len(sched),1)
            except Exception:
                per_load = None
            for i, row in enumerate(sched, start=1):
                load = ReleaseLoad.objects.create(
                    release=rel,
                    seq=i,
                    date=_parse_date_any(row.get('date') if isinstance(row, dict) else None),
                    planned_tons=per_load,
                    updated_by=request.user.username,
                )
                logger.info(f"Created load {i} for release {rel.release_number}: {load.id}")

        normalized_ids = {
            'customerId': rel.customer_ref.id if rel.customer_ref else None,
            'shipToId': rel.ship_to_ref.id if rel.ship_to_ref else None,
            'carrierId': rel.carrier_ref.id if rel.carrier_ref else None,
            'lotId': rel.lot_ref.id if rel.lot_ref else None,
        }

        return Response({'ok': True, 'id': rel.id, 'created': True, 'normalized': normalized_ids, 'release': ReleaseSerializer(rel).data})
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
            # Use actual_tons for SHIPPED loads, fallback to planned_tons for backward compatibility
            tons_shipped = float(r.loads.filter(status='SHIPPED').aggregate(
                sum=models.Sum(Coalesce('actual_tons', 'planned_tons'))
            )['sum'] or 0)
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

# Pending loads for BOL creation (only unshipped loads)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_release_loads(request):
    try:
        loads = ReleaseLoad.objects.filter(status='PENDING').select_related(
            'release', 'release__customer_ref', 'release__ship_to_ref', 'release__carrier_ref', 'release__lot_ref', 'release__lot_ref__product'
        ).order_by('date','seq')
        result = []
        for ld in loads:
            r = ld.release
            prod = getattr(getattr(r, 'lot_ref', None), 'product', None)
            result.append({
                'loadId': ld.id,
                'releaseId': r.id,
                'releaseNumber': r.release_number,
                'label': f"{r.release_number} - Load {ld.seq}",
                'seq': ld.seq,
                'scheduledDate': ld.date,
                'plannedTons': float(ld.planned_tons or 0),
                'customer': {
                    'id': getattr(r.customer_ref, 'id', None),
                    'name': getattr(r.customer_ref, 'customer', r.customer_id_text)
                },
                'shipTo': {
                    'name': r.ship_to_name,
                    'street': r.ship_to_street,
                    'street2': r.ship_to_street2,
                    'city': r.ship_to_city,
                    'state': r.ship_to_state,
                    'zip': r.ship_to_zip,
                },
                'customerPO': r.customer_po,
                'carrier': {
                    'id': getattr(r.carrier_ref, 'id', None),
                    'name': getattr(getattr(r, 'carrier_ref', None), 'carrier_name', r.ship_via)
                },
                'lot': {
                    'id': getattr(r.lot_ref, 'id', None),
                    'code': r.lot,
                    'c': getattr(getattr(r, 'lot_ref', None), 'c', None),
                    'si': getattr(getattr(r, 'lot_ref', None), 'si', None),
                    's': getattr(getattr(r, 'lot_ref', None), 's', None),
                    'p': getattr(getattr(r, 'lot_ref', None), 'p', None),
                    'mn': getattr(getattr(r, 'lot_ref', None), 'mn', None)
                },
                'product': {
                    'id': getattr(prod, 'id', None),
                    'name': getattr(prod, 'name', r.material_description)
                }
            })
        return Response(result)
    except Exception as e:
        logger.error(f"pending_release_loads error: {e}", exc_info=True)
        return Response({'error': 'Failed to load pending loads', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Load detail with release context (for BOL pre-fill)
@api_view(['GET'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def load_detail_api(request, load_id):
    try:
        load = ReleaseLoad.objects.select_related('release__customer_ref', 'release__ship_to_ref', 'release__carrier_ref', 'release__lot_ref').get(id=load_id)
    except ReleaseLoad.DoesNotExist:
        return Response({'error': 'Load not found'}, status=status.HTTP_404_NOT_FOUND)

    # Return load data with nested release context
    release = load.release
    data = {
        'load': ReleaseLoadSerializer(load).data,
        'release': {
            'id': release.id,
            'release_number': release.release_number,
            'customer_id_text': release.customer_id_text,
            'customer_ref_id': release.customer_ref.id if release.customer_ref else None,
            'ship_to_name': release.ship_to_name,
            'ship_to_street': release.ship_to_street,
            'ship_to_street2': release.ship_to_street2,
            'ship_to_city': release.ship_to_city,
            'ship_to_state': release.ship_to_state,
            'ship_to_zip': release.ship_to_zip,
            'ship_to_ref_id': release.ship_to_ref.id if release.ship_to_ref else None,
            'customer_po': release.customer_po,
            'carrier_ref_id': release.carrier_ref.id if release.carrier_ref else None,
            'lot_ref': {
                'id': release.lot_ref.id if release.lot_ref else None,
                'code': release.lot_ref.code if release.lot_ref else None,
                'product': release.lot_ref.product.id if (release.lot_ref and release.lot_ref.product) else None
            } if release.lot_ref else None,
            'material_description': release.material_description
        }
    }
    return Response(data)

# Release detail (GET/PATCH)
@api_view(['GET','PATCH'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def release_detail_api(request, release_id):
    try:
        rel = Release.objects.select_related('customer_ref', 'ship_to_ref', 'carrier_ref', 'lot_ref').prefetch_related('loads__bol').get(id=release_id)
    except Release.DoesNotExist:
        return Response({'error': 'Release not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        data = ReleaseSerializer(rel).data

        # Add loads_summary
        loads = rel.loads.all()
        shipped_loads = loads.filter(status='SHIPPED')
        pending_loads = loads.filter(status='PENDING')
        cancelled_loads = loads.filter(status='CANCELLED')

        # Calculate shipped tonnage using Coalesce(actual_tons, planned_tons)
        from django.db.models import Sum
        shipped_tons = float(shipped_loads.aggregate(
            sum=Sum(Coalesce('actual_tons', 'planned_tons'))
        )['sum'] or 0)

        data['loads_summary'] = {
            'total_loads': loads.count(),
            'shipped_loads': shipped_loads.count(),
            'pending_loads': pending_loads.count(),
            'cancelled_loads': cancelled_loads.count(),
            'shipped_tons': shipped_tons,
            'total_tons': float(rel.quantity_net_tons or 0)
        }

        return Response(data)

    # PATCH update
    try:
        data = request.data if isinstance(request.data, dict) else {}
        tol = float(os.getenv('LOT_CHEM_TOLERANCE', '0.01'))

        # Read fields (camelCase or snake_case)
        release_date = _parse_date_any(data.get('releaseDate') or data.get('release_date'))
        customer_id_text = (data.get('customerId') or data.get('customer_id_text') or rel.customer_id_text or '').strip()
        customer_po = data.get('customerPO') or data.get('customer_po')
        ship_via = data.get('shipVia') or data.get('ship_via')
        fob = data.get('fob') or data.get('FOB')
        qty = data.get('quantityNetTons') or data.get('quantity_net_tons')
        status_val = data.get('status')
        carrier_name = (data.get('carrier') or data.get('carrierName') or data.get('shipVia') or '').strip()

        ship = data.get('shipTo') or {}
        street = ship.get('street') or rel.ship_to_street or ''
        street2 = ship.get('street2') or rel.ship_to_street2 or ''
        city = ship.get('city') or rel.ship_to_city or ''
        state = ship.get('state') or rel.ship_to_state or ''
        zip_code = ship.get('zip') or rel.ship_to_zip or ''
        if (not street or not city or not state or not zip_code) and ship.get('address'):
            # Try to parse "<street>\n<city>, <ST> <ZIP>" or "<street>, <city>, <ST> <ZIP>"
            m = re.search(r"^(.*?)[\n,]\s*([^,\n]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)$", ship.get('address').strip())
            if m:
                street = street or m.group(1).strip()
                city = city or m.group(2).strip()
                state = state or m.group(3).strip()
                zip_code = zip_code or m.group(4).strip()

        mat = data.get('material') or {}
        lot_code = (mat.get('lot') or rel.lot or '').strip()
        desc = (mat.get('description') or rel.material_description or '').strip()
        analysis = mat.get('analysis') or {}

        with transaction.atomic():
            # Update simple fields
            if release_date: rel.release_date = release_date
            if customer_id_text: rel.customer_id_text = customer_id_text
            if customer_po is not None: rel.customer_po = customer_po
            if ship_via is not None: rel.ship_via = ship_via
            if fob is not None: rel.fob = fob
            if qty is not None: rel.quantity_net_tons = qty
            if status_val: rel.status = status_val

            # Upsert relateds
            customer_obj = None
            if customer_id_text:
                customer_obj, _ = Customer.objects.get_or_create(
                    customer=customer_id_text,
                    defaults={'address': street or '', 'city': city or '', 'state': (state or '')[:2], 'zip': zip_code or '', 'is_active': True}
                )
                rel.customer_ref = customer_obj

            if customer_obj and street and city and state and zip_code:
                ship_to_obj, _ = CustomerShipTo.objects.get_or_create(
                    customer=customer_obj, street=street, city=city, state=state[:2], zip=zip_code,
                    defaults={'name': ship.get('name') or rel.ship_to_name or '', 'street2': street2}
                )
                updated = False
                if ship.get('name') and ship_to_obj.name != ship.get('name'):
                    ship_to_obj.name = ship.get('name')
                    updated = True
                if street2 and ship_to_obj.street2 != street2:
                    ship_to_obj.street2 = street2
                    updated = True
                if updated:
                    ship_to_obj.save(update_fields=['name', 'street2'])
                rel.ship_to_ref = ship_to_obj

            if carrier_name:
                carrier_obj, _ = Carrier.objects.get_or_create(carrier_name=carrier_name, defaults={'is_active': True})
                rel.carrier_ref = carrier_obj

            # Product auto-create from description
            product_obj = None
            if desc:
                try:
                    product_obj = Product.objects.get(name__iexact=desc)
                except Product.DoesNotExist:
                    product_obj = Product.objects.create(name=desc, start_tons=Decimal('0'), is_active=True, updated_by=request.user.username)

            # Lot upsert/validate
            lot_obj = None
            if lot_code:
                try:
                    lot_obj = Lot.objects.get(code=lot_code)
                    # Validate or enrich chemistry
                    def _val(x):
                        try: return float(x) if x is not None else None
                        except: return None
                    mismatches = []
                    for k_model, k_parsed in [('c','C'),('si','Si'),('s','S'),('p','P'),('mn','Mn')]:
                        exf = _val(getattr(lot_obj, k_model, None))
                        paf = _val(analysis.get(k_parsed))
                        if exf is not None and paf is not None and abs(exf - paf) > tol:
                            mismatches.append({'element': k_parsed, 'existing': exf, 'parsed': paf, 'delta': abs(exf - paf)})
                        if exf is None and paf is not None:
                            setattr(lot_obj, k_model, Decimal(str(paf)))
                    # Attach product if missing
                    if product_obj and not lot_obj.product:
                        lot_obj.product = product_obj
                    if mismatches:
                        return Response({'error': 'Lot chemistry mismatch', 'lot': lot_code, 'tolerance': tol, 'mismatches': mismatches}, status=status.HTTP_409_CONFLICT)
                    lot_obj.updated_by = request.user.username
                    lot_obj.save()
                except Lot.DoesNotExist:
                    lot_obj = Lot.objects.create(
                        code=lot_code,
                        product=product_obj,
                        c=Decimal(str(analysis.get('C'))) if analysis.get('C') is not None else None,
                        si=Decimal(str(analysis.get('Si'))) if analysis.get('Si') is not None else None,
                        s=Decimal(str(analysis.get('S'))) if analysis.get('S') is not None else None,
                        p=Decimal(str(analysis.get('P'))) if analysis.get('P') is not None else None,
                        mn=Decimal(str(analysis.get('Mn'))) if analysis.get('Mn') is not None else None,
                        updated_by=request.user.username,
                    )
                rel.lot_ref = lot_obj

            # Mirror latest lot chemistry onto product for quick double-checking
            try:
                target_product = product_obj or (lot_obj.product if lot_obj else None)
                if target_product and lot_obj:
                    changed = False
                    if target_product.last_lot_code != lot_obj.code:
                        target_product.last_lot_code = lot_obj.code; changed = True
                    for f in ['c','si','s','p','mn']:
                        newv = getattr(lot_obj, f, None)
                        if newv is not None and getattr(target_product, f) != newv:
                            setattr(target_product, f, newv); changed = True
                    if changed:
                        target_product.updated_by = request.user.username
                        target_product.save()
            except Exception:
                pass

            # Persist text mirrors
            if ship.get('name') is not None: rel.ship_to_name = ship.get('name')
            rel.ship_to_street = street
            rel.ship_to_street2 = street2
            rel.ship_to_city = city
            rel.ship_to_state = state[:2] if state else ''
            rel.ship_to_zip = zip_code
            if lot_code is not None: rel.lot = lot_code
            if desc is not None: rel.material_description = desc
            rel.updated_by = request.user.username
            rel.save()

        audit(request, 'RELEASE_UPDATED', rel, f"Updated release {rel.release_number}")
        return Response(ReleaseSerializer(rel).data)
    except Exception as e:
        logger.error(f"release_detail_api error: {e}", exc_info=True)
        return Response({'error': 'Failed to update release', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Audit log list (simple)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_logs(request):
    try:
        limit = int(request.GET.get('limit', '200'))
        rows = AuditLog.objects.all().order_by('-created_at')[:max(1, min(limit, 1000))]
        return Response(AuditLogSerializer(rows, many=True).data)
    except Exception as e:
        logger.error(f"audit_logs error: {e}", exc_info=True)
        return Response({'error':'Failed to load audit logs'}, status=status.HTTP_400_BAD_REQUEST)

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
