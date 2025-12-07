from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from django.db import models, connection, transaction, IntegrityError
from django.db.models.functions import Coalesce
from django.core.files.storage import default_storage
from .models import Product, Customer, Carrier, Truck, BOL, Release, ReleaseLoad, CustomerShipTo, Lot, AuditLog, Tenant
from .serializers import ProductSerializer, CustomerSerializer, CarrierSerializer, TruckSerializer, ReleaseSerializer, ReleaseLoadSerializer, CustomerShipToSerializer, AuditLogSerializer
from .pdf_generator import generate_bol_pdf
from .release_parser import parse_release_pdf
from .email_utils import send_bol_notification
from .security import validate_tenant_access, get_tenant_filter
from primetrade_project.decorators import require_role, require_role_for_writes
from bol_system.permissions import feature_permission_required
from django.views.decorators.csrf import ensure_csrf_cookie
# Customer filtering utilities removed - all authenticated users see all data
from django.utils.decorators import method_decorator
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

def _derive_pdf_key(path_or_url: str | None):
    """Convert a stored URL/path into an S3 object key."""
    if not path_or_url:
        return None
    if path_or_url.startswith('http'):
        m = re.search(r'(media/.+)$', path_or_url)
        return m.group(1) if m else None
    return path_or_url.lstrip('/')

def audit(request, action: str, obj=None, message: str = '', extra: dict | None = None):
    try:
        from .models import AuditLog  # local import to avoid circular during migrations
        tenant = getattr(request, 'tenant', None)
        entry = AuditLog.objects.create(
            tenant=tenant,
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

# CSRF token endpoint - ensures cookie is set for JavaScript
from django.http import JsonResponse
from django.middleware.csrf import get_token

@ensure_csrf_cookie
def csrf_token_view(request):
    """Return CSRF token and ensure cookie is set.

    Call this endpoint on page load to ensure the csrftoken cookie exists
    before making POST requests.
    """
    return JsonResponse({'csrfToken': get_token(request)})

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

# User context endpoint (returns role and permissions for frontend)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_role('Admin', 'Office', 'Client')  # All authenticated users need this for dashboard
@feature_permission_required('dashboard', 'view')
def user_context(request):
    """
    Return user context including role and permissions for frontend.

    Security (Phase 2 Fix):
    - All authenticated users (Admin, Office, Client) can access
    - Required for client dashboard to load

    Permission Logic (RBAC Dec 2025):
    - can_write: true if user has "create" or "modify" for any feature
    - is_admin: true if role is "Admin" or has "full_access" permission
    """
    app_role = request.session.get('primetrade_role', {})
    user_role = app_role.get('role', 'viewer')
    permissions = app_role.get('permissions', ['read'])

    # Get feature permissions from session (RBAC system)
    feature_permissions = request.session.get('feature_permissions', {})

    # Check for write access:
    # 1. Legacy: "write" in top-level permissions array
    # 2. Admin: "full_access" in top-level permissions
    # 3. RBAC: Any feature has "create" or "modify" permission
    has_write_permission = (
        'write' in permissions
        or 'full_access' in permissions
        or any(
            'create' in perms or 'modify' in perms
            for perms in feature_permissions.values()
        )
    )

    # Check for admin access:
    # 1. "full_access" in top-level permissions
    # 2. Role is "Admin" (case-insensitive)
    is_admin = 'full_access' in permissions or user_role.lower() == 'admin'

    return Response({
        'user': {
            'email': request.user.email if request.user.email else request.user.username,
            'role': user_role,
            'permissions': permissions,
            'is_authenticated': True
        },
        'can_write': has_write_permission,
        'is_admin': is_admin
    })

# Product endpoints
@method_decorator(require_role('Admin', 'Office', 'Client'), name='dispatch')
@method_decorator(feature_permission_required('products', 'view'), name='dispatch')
class ProductListView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Filter by tenant for data isolation
        return Product.objects.filter(is_active=True, **get_tenant_filter(self.request)).order_by('name')

    # Support upsert via POST so the existing frontend can use one endpoint
    def post(self, request, *args, **kwargs):
        # Check role for write operations - Product management is Admin-only
        app_role = request.session.get('primetrade_role', {})
        user_role = app_role.get('role')
        if user_role != 'admin':
            user_email = request.user.email if request.user.is_authenticated else 'unknown'
            logger.warning(
                f"Access denied: {user_email} (role={user_role or 'none'}) "
                f"attempted ProductListView POST. Product management is Admin-only."
            )
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden(
                f"Access denied. Product management requires Admin role. "
                f"Your current role: {user_role or 'none'}."
            )

        try:
            data = request.data if isinstance(request.data, dict) else {}
            pid = data.get('id')
            name = (data.get('name') or '').strip()
            start = data.get('start_tons', None)
            is_active = data.get('is_active', True)

            if pid:
                # Update existing product
                try:
                    prod = Product.objects.get(id=pid, **get_tenant_filter(request))
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
@ensure_csrf_cookie
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@require_role('Admin', 'Office')  # Internal staff only - customer management is internal
@feature_permission_required('customers', 'view')
def customer_list(request):
    try:
        if request.method == 'GET':
            customers = Customer.objects.filter(**get_tenant_filter(request)).order_by('customer')
            return Response(CustomerSerializer(customers, many=True).data)

        # POST - create or update
        data = request.data if isinstance(request.data, dict) else {}
        cust_id = data.get('id')
        customer_name = (data.get('customer') or '').strip()
        address = (data.get('address') or '').strip()
        address2 = (data.get('address2') or '').strip()
        city = (data.get('city') or '').strip()
        state = (data.get('state') or '').strip()[:2]
        zip_code = (data.get('zip') or '').strip()
        is_active = data.get('is_active', True)

        if not all([customer_name, address, city, state, zip_code]):
            return Response({'error': 'customer, address, city, state, zip are required'}, status=status.HTTP_400_BAD_REQUEST)

        if cust_id:
            # Update existing customer
            try:
                cust = Customer.objects.get(id=cust_id, **get_tenant_filter(request))
                cust.customer = customer_name
                cust.address = address
                cust.address2 = address2
                cust.city = city
                cust.state = state
                cust.zip = zip_code
                cust.is_active = is_active
                cust.updated_by = request.user.username
                cust.save()
                audit(request, 'CUSTOMER_UPDATED', cust, f"Customer updated: {cust.customer}")
                return Response({'ok': True, 'id': cust.id})
            except Customer.DoesNotExist:
                return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Create new customer
            try:
                cust = Customer.objects.create(
                    tenant=getattr(request, 'tenant', None),
                    customer=customer_name,
                    address=address,
                    address2=address2,
                    city=city,
                    state=state,
                    zip=zip_code,
                    is_active=is_active,
                    updated_by=request.user.username
                )
                audit(request, 'CUSTOMER_CREATED', cust, f"Customer created: {cust.customer}")
                return Response({'ok': True, 'id': cust.id})
            except IntegrityError as e:
                return Response({'error': 'Customer already exists', 'detail': str(e)}, status=status.HTTP_409_CONFLICT)
    except Exception as e:
        logger.error(f"customer upsert error: {e}", exc_info=True)
        return Response({'error': 'Failed to save customer', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Customer detail endpoint (single customer by ID)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_role('Admin', 'Office')  # Internal staff only
@feature_permission_required('customers', 'view')
def customer_detail(request, customer_id: int):
    """
    Get details for a single customer by ID.

    Security (Phase 2 - Nov 2025):
    - Admin/Office only (internal customer management)
    - Client users cannot access customer details
    """
    try:
        customer = Customer.objects.get(id=customer_id, **get_tenant_filter(request))
        return Response(CustomerSerializer(customer).data)
    except Customer.DoesNotExist:
        return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"customer_detail error: {e}", exc_info=True)
        return Response({'error': 'Failed to fetch customer', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Ship-To endpoints (per-customer)
@api_view(['GET','POST'])
@permission_classes([IsAuthenticated])
@require_role_for_writes('admin', 'office')  # POST operations require Admin or Office role (both have write permission)
@feature_permission_required('customers', 'view')
def customer_shiptos(request, customer_id: int):
    try:
        try:
            customer = Customer.objects.get(id=customer_id, **get_tenant_filter(request))
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

# Customer branding endpoint (for branded dashboard)
@api_view(['GET'])
@permission_classes([AllowAny])  # Allow unauthenticated access for public dashboard
def customer_branding(request):
    """
    Returns customer branding information (logo URL, colors) for the dashboard.
    Query params:
      - customer_id: optional customer ID to get specific branding
      - customer_name: optional customer name to lookup branding
    If no params provided, returns default PrimeTrade branding.

    SECURITY NOTE: This endpoint intentionally does NOT use tenant filtering.
    It's a public endpoint for fetching non-sensitive branding data (logos, colors).
    No sensitive business data is exposed through this endpoint.
    """
    try:
        customer_id = request.GET.get('customer_id')
        customer_name = request.GET.get('customer_name')

        customer = None
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                pass
        elif customer_name:
            try:
                customer = Customer.objects.get(customer__iexact=customer_name)
            except Customer.DoesNotExist:
                pass

        if customer:
            return Response({
                'logo_url': customer.logo_url or '/static/primetrade-logo.jpg',
                'primary_color': customer.primary_color or '#2563eb',
                'secondary_color': customer.secondary_color or '#667eea',
                'customer_name': customer.customer
            })
        else:
            # Default PrimeTrade branding
            return Response({
                'logo_url': '/static/primetrade-logo.jpg',
                'primary_color': '#2563eb',
                'secondary_color': '#667eea',
                'customer_name': 'PrimeTrade'
            })
    except Exception as e:
        logger.error(f"customer_branding error: {e}", exc_info=True)
        return Response({'error': 'Failed to fetch branding'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Lot endpoints
@ensure_csrf_cookie
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@require_role_for_writes('admin', 'office')
@feature_permission_required('products', 'view')
def lot_list(request):
    """List all lots or create a new lot."""
    from .serializers import LotSerializer
    try:
        if request.method == 'GET':
            lots = Lot.objects.select_related('product').all().order_by('-code')
            return Response(LotSerializer(lots, many=True).data)

        # POST - create new lot
        data = request.data if isinstance(request.data, dict) else {}
        code = (data.get('code') or '').strip()
        if not code:
            return Response({'error': 'code is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Check for duplicate
        if Lot.objects.filter(code=code).exists():
            return Response({'error': f'Lot {code} already exists'}, status=status.HTTP_409_CONFLICT)

        # Get product if provided
        product_id = data.get('product')
        product_obj = None
        if product_id:
            try:
                product_obj = Product.objects.get(id=product_id, **get_tenant_filter(request))
            except Product.DoesNotExist:
                pass

        lot = Lot.objects.create(
            code=code,
            product=product_obj,
            c=data.get('c') or None,
            si=data.get('si') or None,
            s=data.get('s') or None,
            p=data.get('p') or None,
            mn=data.get('mn') or None,
            updated_by=request.user.username,
        )
        audit(request, 'LOT_CREATED', lot, f"Lot created: {code}")
        return Response(LotSerializer(lot).data, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"lot_list error: {e}", exc_info=True)
        return Response({'error': 'Failed to process lot request', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Carrier endpoints with trucks
@ensure_csrf_cookie
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@require_role_for_writes('admin', 'office')  # POST operations require Admin or Office role (needed for BOL creation)
@feature_permission_required('carriers', 'view')
def carrier_list(request):
    try:
        if request.method == 'POST':
            # Create or update carrier
            data = request.data
            carrier_id = data.get('id')

            if carrier_id:
                # Update existing carrier
                try:
                    carrier = Carrier.objects.get(id=carrier_id, **get_tenant_filter(request))
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
                    tenant=getattr(request, 'tenant', None),
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
        carriers = Carrier.objects.filter(is_active=True, **get_tenant_filter(request)).order_by('carrier_name')
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
@require_role('admin', 'office')  # Preview requires Admin or Office role (both have write permission)
@feature_permission_required('bol', 'create')
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

        # Check if creating from a release load to pull additional data
        release_load = None
        release_obj = None
        load_id = data.get('loadId') or data.get('load_id')
        if load_id:
            try:
                release_load = ReleaseLoad.objects.select_related(
                    'release',
                    'release__lot_ref'
                ).get(id=load_id)
                release_obj = release_load.release
            except ReleaseLoad.DoesNotExist:
                pass  # Continue without release data

        # Get related objects for display names (tenant-scoped)
        try:
            product = Product.objects.get(id=data['productId'], **get_tenant_filter(request))
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            carrier = Carrier.objects.get(id=data.get('carrierId', ''), **get_tenant_filter(request))
        except Carrier.DoesNotExist:
            return Response({'error': 'Carrier not found'}, status=status.HTTP_404_NOT_FOUND)

        truck = None
        if data.get('truckId'):
            try:
                # Truck inherits tenant through carrier relationship
                truck = Truck.objects.get(id=data.get('truckId'), carrier__tenant=getattr(request, 'tenant', None))
            except Truck.DoesNotExist:
                return Response({'error': 'Truck not found'}, status=status.HTTP_404_NOT_FOUND)

        # Build preview data dictionary (matching actual BOL structure)
        # If from release, pull care_of_co, lot_ref, and release_number from release
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
            'specialInstructions': data.get('specialInstructions', ''),
            'releaseNumber': f'{release_obj.release_number}-{release_load.seq}' if release_load else data.get('releaseNumber', ''),
            'care_of_co': release_obj.care_of_co if release_obj else data.get('careOfCo', 'PrimeTrade, LLC'),
            'lot_ref': release_obj.lot_ref if release_obj else None,
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
@require_role('admin', 'office')  # Allow Admin and Office roles to create BOLs (both have write permission)
@feature_permission_required('bol', 'create')
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
                    product = Product.objects.get(id=data['productId'], **get_tenant_filter(request))
                except Product.DoesNotExist:
                    return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
            if not product:
                return Response({'error': 'Product not set for this release/lot'}, status=status.HTTP_400_BAD_REQUEST)
            customer = getattr(release_obj, 'customer_ref', None)
            # Carrier: prefer payload carrierId override, else release.carrier_ref must exist
            if data.get('carrierId'):
                try:
                    carrier = Carrier.objects.get(id=data.get('carrierId'), **get_tenant_filter(request))
                except Carrier.DoesNotExist:
                    return Response({'error': 'Carrier not found'}, status=status.HTTP_404_NOT_FOUND)
            else:
                carrier = getattr(release_obj, 'carrier_ref', None)
                if not carrier:
                    return Response({'error': 'Carrier is required'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Legacy resolution (tenant-scoped)
            try:
                product = Product.objects.get(id=data['productId'], **get_tenant_filter(request))
            except Product.DoesNotExist:
                return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
            try:
                carrier = Carrier.objects.get(id=data.get('carrierId', ''), **get_tenant_filter(request))
            except Carrier.DoesNotExist:
                return Response({'error': 'Carrier not found'}, status=status.HTTP_404_NOT_FOUND)
            if data.get('customerId'):
                try:
                    customer = Customer.objects.get(id=data.get('customerId'), **get_tenant_filter(request))
                except Customer.DoesNotExist:
                    return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)

        truck = None
        if data.get('truckId'):
            try:
                # Truck inherits tenant through carrier relationship
                truck = Truck.objects.get(id=data.get('truckId'), carrier__tenant=getattr(request, 'tenant', None))
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
            special_instructions=release_obj.special_instructions if release_load else '',
            care_of_co=release_obj.care_of_co if release_load else 'PrimeTrade, LLC'
        )

        # If load provided, mark shipped and attach
        if release_load:
            release_load.status = 'SHIPPED'
            release_load.bol = bol
            release_load.save(update_fields=['status','bol','updated_at','updated_by'])
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
            bol.pdf_key = _derive_pdf_key(pdf_url)
            bol.save(update_fields=['pdf_url', 'pdf_key', 'updated_at'])
            logger.info(f"Generated PDF for BOL {bol.bol_number} at {pdf_url}")
        except Exception as e:
            logger.error(f"Failed to generate PDF for BOL {bol.bol_number}: {str(e)}")
            # Continue without PDF - don't fail the BOL creation
            pdf_url = f"/media/bol_pdfs/{bol.bol_number}.pdf"
            bol.pdf_url = pdf_url
            bol.pdf_key = _derive_pdf_key(pdf_url)
            bol.save(update_fields=['pdf_url', 'pdf_key', 'updated_at'])

        # Send email notification
        try:
            send_bol_notification(bol, pdf_url)
        except Exception as e:
            logger.error(f"Failed to send email notification for BOL {bol.bol_number}: {str(e)}")
            # Don't fail BOL creation if email fails

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
@require_role('Admin', 'Office', 'Client')  # Client dashboard needs this for inventory display
@feature_permission_required('reports', 'view')
def balances(request):
    try:
        # Filter by tenant for data isolation
        products = Product.objects.filter(is_active=True, **get_tenant_filter(request))
        result = []
        for product in products:
            # Use official weight if available, otherwise fall back to CBRT weight
            bols = BOL.objects.filter(product=product, **get_tenant_filter(request))
            shipped = 0
            for bol in bols:
                try:
                    # Use official weight if it exists and is not None
                    if hasattr(bol, 'official_weight_tons') and bol.official_weight_tons is not None:
                        shipped += float(bol.official_weight_tons)
                    else:
                        shipped += float(bol.net_tons)
                except (TypeError, ValueError) as e:
                    logger.warning(f"Error processing BOL {bol.id} weight: {e}, using net_tons")
                    shipped += float(bol.net_tons)

            start_tons = float(product.start_tons)
            result.append({
                'id': product.id,
                'name': product.name,
                'startTons': round(start_tons, 2),
                'shipped': round(shipped, 2),
                'remaining': round(start_tons - shipped, 2)
            })

        return Response(result)
    except Exception as e:
        logger.error(f"Error in balances: {str(e)}", exc_info=True)
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
@require_role('admin', 'office')  # Allow Admin and Office roles to approve releases (both have write permission)
@feature_permission_required('releases', 'modify')
def approve_release(request):
    try:
        data = request.data if isinstance(request.data, dict) else {}
        logger.info(f"approve_release called with schedule: {len(data.get('schedule', []))} items, material.analysis: {bool(data.get('material', {}).get('analysis'))}")
        # Required
        release_number = data.get('releaseNumber') or data.get('release_number')
        if not release_number:
            return Response({'error': 'releaseNumber required'}, status=status.HTTP_400_BAD_REQUEST)

        # Handle duplicate release numbers
        existing_active = Release.objects.filter(release_number=release_number).exclude(status='CANCELLED').first()
        if existing_active:
            # Block duplicates for active (non-cancelled) releases
            audit(request, 'RELEASE_APPROVE_DUPLICATE', existing_active, f"Duplicate attempt: {release_number}", {'releaseNumber': release_number})
            return Response(
                {
                    'error': 'Duplicate release_number',
                    'releaseNumber': release_number,
                    'id': existing_active.id,
                },
                status=status.HTTP_409_CONFLICT
            )

        # If there's a cancelled release with this number, delete it to allow re-creation
        cancelled_release = Release.objects.filter(release_number=release_number, status='CANCELLED').first()
        if cancelled_release:
            logger.info(f"Deleting cancelled release {release_number} (ID: {cancelled_release.id}) to allow re-creation by {request.user.username}")
            audit(request, 'RELEASE_DELETED', cancelled_release, f"Deleted cancelled release {release_number} for re-creation")
            cancelled_release.delete()  # This will cascade delete associated loads

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
            # DOTALL flag allows .*? to match across newlines for multi-line streets
            m = re.search(r"^(.*?)[\n,]\s*([^,\n]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)$", addr.strip(), re.DOTALL)
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
                care_of_co=data.get('careOfCo', 'PrimeTrade, LLC'),
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
@require_role('Admin', 'Office', 'Client')  # Client dashboard needs this for releases display
@feature_permission_required('releases', 'view')
def list_releases(request):
    """List releases with optional status filter. Defaults to OPEN."""
    try:
        from datetime import date as date_class
        today = date_class.today()

        # Get status filter from query params (default to OPEN for backward compatibility)
        status_filter = request.query_params.get('status', 'OPEN').upper()

        # Filter by tenant for data isolation
        tenant_filter = get_tenant_filter(request)
        if status_filter == 'ALL':
            rels = Release.objects.filter(**tenant_filter).order_by('-created_at')
        else:
            rels = Release.objects.filter(status=status_filter, **tenant_filter).order_by('-created_at')
        result = []
        for r in rels:
            loads_total = r.loads.count()
            shipped = r.loads.filter(status='SHIPPED').count()
            remaining = loads_total - shipped
            tons_total = float(r.quantity_net_tons or 0)

            # Calculate weight breakdown: official vs planned
            shipped_loads = r.loads.filter(status='SHIPPED')
            tons_official = float(shipped_loads.filter(bol__official_weight_tons__isnull=False).aggregate(
                sum=models.Sum('bol__official_weight_tons')
            )['sum'] or 0)
            tons_planned = float(shipped_loads.filter(bol__official_weight_tons__isnull=True).aggregate(
                sum=models.Sum('planned_tons')
            )['sum'] or 0)
            tons_shipped = tons_official + tons_planned
            tons_remaining = max(0.0, tons_total - tons_shipped)

            next_date = r.loads.filter(status='PENDING').order_by('date').values_list('date', flat=True).first()
            last_shipped = r.loads.filter(status='SHIPPED').order_by('-date').values_list('date', flat=True).first()

            # Urgency calculations
            days_until_next = None
            is_overdue = False
            urgency_level = 'upcoming'
            if next_date:
                next_date_obj = datetime.strptime(next_date, '%Y-%m-%d').date() if isinstance(next_date, str) else next_date
                days_until_next = (next_date_obj - today).days
                is_overdue = days_until_next < 0
                if days_until_next < 0:
                    urgency_level = 'overdue'
                elif days_until_next <= 2:
                    urgency_level = 'due-soon'

            days_open = (today - r.created_at.date()).days if r.created_at else None

            result.append({
                'id': r.id,
                'releaseNumber': r.release_number,
                'customer': r.customer_id_text,
                'status': r.status,
                'totalLoads': loads_total,
                'loadsShipped': shipped,
                'loadsRemaining': remaining,
                'totalTons': tons_total,
                'tonsShipped': tons_shipped,
                'tonsOfficial': tons_official,
                'tonsPlanned': tons_planned,
                'tonsRemaining': tons_remaining,
                'nextScheduledDate': next_date,
                'lastShippedDate': last_shipped,
                'daysUntilNextLoad': days_until_next,
                'isOverdue': is_overdue,
                'urgencyLevel': urgency_level,
                'daysOpen': days_open,
            })
        return Response(result)
    except Exception as e:
        logger.error(f"list_releases error: {e}", exc_info=True)
        return Response({'error': 'Failed to load releases', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Pending loads for BOL creation (only unshipped loads)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_role('Admin', 'Office', 'Client')  # Client dashboard loading schedule needs this
@feature_permission_required('releases', 'view')
def pending_release_loads(request):
    try:
        from datetime import date as date_class, timedelta
        today = date_class.today()

        # Calculate current calendar week (Sunday-Saturday)
        # Sunday is the start of the week
        days_since_sunday = (today.weekday() + 1) % 7  # Monday=0, so Sunday=6 -> convert to Sunday=0
        this_week_start = today - timedelta(days=days_since_sunday)
        this_week_end = this_week_start + timedelta(days=6)
        next_week_start = this_week_end + timedelta(days=1)
        next_week_end = next_week_start + timedelta(days=6)

        # TODO Phase 2: tenant filter once tenant_id is available
        loads = ReleaseLoad.objects.filter(status='PENDING').select_related(
            'release', 'release__customer_ref', 'release__ship_to_ref', 'release__carrier_ref', 'release__lot_ref', 'release__lot_ref__product'
        ).order_by('date','seq')
        result = []
        for ld in loads:
            r = ld.release
            prod = getattr(getattr(r, 'lot_ref', None), 'product', None)

            # Parse scheduled date and calculate urgency
            sched_date = datetime.strptime(ld.date, '%Y-%m-%d').date() if isinstance(ld.date, str) else ld.date
            days_until = (sched_date - today).days

            # Determine urgency level using calendar weeks (Sunday-Saturday)
            if days_until < 0:
                urgency = 'overdue'
            elif days_until == 0:
                urgency = 'today'
            elif this_week_start <= sched_date <= this_week_end:
                urgency = 'this-week'
            elif next_week_start <= sched_date <= next_week_end:
                urgency = 'next-week'
            else:
                urgency = 'later'

            # Calculate ISO week number for grouping
            week_num = sched_date.isocalendar()[1]

            result.append({
                'loadId': ld.id,
                'releaseId': r.id,
                'releaseNumber': r.release_number,
                'label': f"{r.release_number} - Load {ld.seq}",
                'seq': ld.seq,
                'scheduledDate': ld.date,
                'plannedTons': float(ld.planned_tons or 0),
                'daysUntil': days_until,
                'urgency': urgency,
                'weekGroup': week_num,
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
@require_role('Admin', 'Office', 'Client')  # All authenticated users - Phase 2 audit fix
@feature_permission_required('releases', 'view')
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
@require_role_for_writes('admin', 'office')  # PATCH operations require Admin or Office role (both have write permission)
@feature_permission_required('releases', 'view')
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

        # Calculate shipped tonnage using official weight from BOL, fallback to planned_tons
        from django.db.models import Sum
        shipped_tons = float(shipped_loads.aggregate(
            sum=Sum(Coalesce('bol__official_weight_tons', 'planned_tons'))
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
        special_instructions = data.get('specialInstructions')
        care_of_co = data.get('careOfCo')

        ship = data.get('shipTo') or {}
        street = ship.get('street') or rel.ship_to_street or ''
        street2 = ship.get('street2') or rel.ship_to_street2 or ''
        city = ship.get('city') or rel.ship_to_city or ''
        state = ship.get('state') or rel.ship_to_state or ''
        zip_code = ship.get('zip') or rel.ship_to_zip or ''
        if (not street or not city or not state or not zip_code) and ship.get('address'):
            # Try to parse "<street>\n<city>, <ST> <ZIP>" or "<street>, <city>, <ST> <ZIP>"
            # DOTALL flag allows .*? to match across newlines for multi-line streets
            m = re.search(r"^(.*?)[\n,]\s*([^,\n]+),\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)$", ship.get('address').strip(), re.DOTALL)
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
            # Handle release cancellation
            if status_val == 'CANCELLED':
                # Check if any loads have been shipped
                shipped_count = rel.loads.filter(status='SHIPPED').count()
                if shipped_count > 0:
                    return Response(
                        {'error': f'Cannot cancel release: {shipped_count} load(s) have already been shipped'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                # Cancel all pending loads
                cancelled_loads = rel.loads.filter(status='PENDING').update(status='CANCELLED')
                logger.info(f"Cancelled release {rel.release_number}: {cancelled_loads} pending loads cancelled by {request.user.username}")

            # Update simple fields
            if release_date: rel.release_date = release_date
            if customer_id_text: rel.customer_id_text = customer_id_text
            if customer_po is not None: rel.customer_po = customer_po
            if ship_via is not None: rel.ship_via = ship_via
            if fob is not None: rel.fob = fob
            if qty is not None: rel.quantity_net_tons = qty
            if status_val: rel.status = status_val
            if special_instructions is not None: rel.special_instructions = special_instructions
            if care_of_co is not None: rel.care_of_co = care_of_co

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
@require_role('Admin', 'Office')  # Internal staff only - Client cannot access
@feature_permission_required('reports', 'view')
def audit_logs(request):
    """
    Return audit logs - INTERNAL STAFF ONLY.

    Security (Phase 2 - Nov 2025):
    - Admin/Office roles only (internal operations data)
    - Client users get 403 Forbidden
    - All audit logs visible to internal staff
    """
    try:
        limit = int(request.GET.get('limit', '200'))
        rows = AuditLog.objects.filter(**get_tenant_filter(request)).order_by('-created_at')[:max(1, min(limit, 1000))]
        return Response(AuditLogSerializer(rows, many=True).data)
    except Exception as e:
        logger.error(f"audit_logs error: {e}", exc_info=True)
        return Response({'error':'Failed to load audit logs'}, status=status.HTTP_400_BAD_REQUEST)

# BOL history
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_role('Admin', 'Office', 'Client')  # All authenticated users
@feature_permission_required('bol', 'view')
def bol_history(request):
    """
    Return BOL history for all authenticated users.

    Security (Phase 2 - Nov 2025):
    - All authenticated users (Admin, Office, Client) see ALL BOLs
    - Access control is at the authentication level (must be logged in)
    - Write operations restricted by @require_role decorators on other endpoints
    - Client role is read-only (no create/update/delete permissions)
    """
    try:
        # Phase 2 Security: All authenticated users (Admin, Office, Client) see all BOLs
        # Filter by tenant for data isolation
        base_queryset = BOL.objects.filter(**get_tenant_filter(request))

        role_info = request.session.get('primetrade_role', {})
        user_role = role_info.get('role', 'Unknown')

        product_id = request.GET.get('productId')

        if product_id:
            # Product-specific history (legacy behavior)
            try:
                product = Product.objects.get(id=product_id, **get_tenant_filter(request))
            except Product.DoesNotExist:
                return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

            bols = base_queryset.filter(product=product).order_by('date')
            # Use official weight if available, otherwise CBRT weight
            shipped = 0
            for bol in bols:
                try:
                    if hasattr(bol, 'official_weight_tons') and bol.official_weight_tons is not None:
                        shipped += float(bol.official_weight_tons)
                    else:
                        shipped += float(bol.net_tons)
                except (TypeError, ValueError) as e:
                    logger.warning(f"Error processing BOL {bol.id} weight in history: {e}")
                    shipped += float(bol.net_tons)
            start_tons = float(product.start_tons)
            remaining = start_tons - shipped
            summary = {
                'start': round(start_tons, 2),
                'shipped': round(shipped, 2),
                'remaining': round(remaining, 2)
            }
        else:
            # All BOLs (for weight management page)
            # Phase 2 Security: Uses filtered base_queryset
            bols = base_queryset.order_by('-created_at')
            summary = None

        # Build rows with safe weight handling
        rows = []
        logger.info(f"Serializing {bols.count()} BOLs for history endpoint")
        for bol in bols:
            try:
                logger.debug(f"Serializing BOL {bol.bol_number} (ID: {bol.id})")
                # Determine which weight to display
                has_official = hasattr(bol, 'official_weight_tons') and bol.official_weight_tons is not None
                display_weight = float(bol.official_weight_tons) if has_official else float(bol.net_tons)

                # Resolve PDF URLs using signer (pdf_key preferred, pdf_url legacy fallback)
                pdf_url = bol.get_pdf_url()

                stamped_pdf_url = None
                if bol.stamped_pdf_url and bol.stamped_pdf_url.strip():
                    try:
                        # Extract S3 key from URL or use directly if already a key
                        stamped_key = None
                        if bol.stamped_pdf_url.startswith('http'):
                            # Extract key from full S3 URL
                            match = re.search(r'amazonaws\.com/(.+)$', bol.stamped_pdf_url)
                            if match:
                                stamped_key = match.group(1)
                        else:
                            # Already a key
                            stamped_key = bol.stamped_pdf_url.lstrip('/')
                        
                        # Generate signed URL if we have a key
                        if stamped_key:
                            stamped_pdf_url = default_storage.url(stamped_key)
                        else:
                            # Fallback to original if key extraction failed
                            logger.warning(f"Could not extract key from stamped_pdf_url for BOL {bol.id}: {bol.stamped_pdf_url}")
                            stamped_pdf_url = bol.stamped_pdf_url
                    except Exception as url_err:
                        logger.warning(f"Could not generate signed stamped_pdf_url for BOL {bol.id}: {url_err}")
                        stamped_pdf_url = bol.stamped_pdf_url  # Fallback to original value

                row_data = {
                    'id': bol.id,
                    'bolNo': bol.bol_number,
                    'date': bol.date,
                    'truckNo': bol.truck_number,
                    'netTons': round(display_weight, 2),  # Best available weight
                    'cbrtWeightTons': round(float(bol.net_tons), 2),  # Always include CBRT weight for reference
                    'pdfUrl': pdf_url,
                    'stampedPdfUrl': stamped_pdf_url,
                    'productName': bol.product_name,
                    'buyerName': bol.buyer_name,
                    'officialWeightTons': round(float(bol.official_weight_tons), 2) if has_official else None,
                    'varianceTons': round(float(bol.weight_variance_tons), 2) if hasattr(bol, 'weight_variance_tons') and bol.weight_variance_tons else None,
                    'variancePercent': round(float(bol.weight_variance_percent), 2) if hasattr(bol, 'weight_variance_percent') and bol.weight_variance_percent else None,
                    'enteredBy': bol.official_weight_entered_by if hasattr(bol, 'official_weight_entered_by') else None,
                    'enteredAt': bol.official_weight_entered_at.isoformat() if hasattr(bol, 'official_weight_entered_at') and bol.official_weight_entered_at else None
                }
                rows.append(row_data)
                logger.debug(f"Successfully serialized BOL {bol.bol_number}")
            except Exception as e:
                logger.error(f"Error serializing BOL {bol.bol_number} (ID: {bol.id}): {e}", exc_info=True)
                # Skip this BOL if it can't be serialized
                continue

        return Response({
            'summary': summary,
            'rows': rows
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
@require_role('Admin', 'Office', 'Client')  # All authenticated users - Phase 2 audit fix
@feature_permission_required('bol', 'view')
def bol_detail(request, bol_id):
    try:
        bol = BOL.objects.get(id=bol_id, **get_tenant_filter(request))
        # Convert S3 path to full URL (only if not already a URL)
        pdf_url = bol.pdf_url if (bol.pdf_url and bol.pdf_url.startswith('http')) else (default_storage.url(bol.pdf_url) if bol.pdf_url else None)

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
            'pdfUrl': pdf_url
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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_role('admin', 'office')  # Allow Admin and Office roles to set official weights (both have write permission)
@feature_permission_required('bol', 'modify')
def set_official_weight(request, bol_id):
    """
    Set official certified scale weight for a BOL.

    Requires: officialWeightTons (decimal)
    Auto-calculates variance and logs who/when.
    """
    try:
        bol = BOL.objects.get(id=bol_id, **get_tenant_filter(request))

        # Validate input
        weight_tons = request.data.get('officialWeightTons')
        if weight_tons is None or weight_tons == '':
            return Response({'error': 'officialWeightTons is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            weight_tons = Decimal(str(weight_tons))
        except (ValueError, TypeError):
            return Response({'error': 'officialWeightTons must be a valid number'}, status=status.HTTP_400_BAD_REQUEST)

        if weight_tons <= 0:
            return Response({'error': 'officialWeightTons must be positive'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if official weight already set
        if bol.official_weight_tons is not None:
            return Response({
                'error': 'Official weight already set',
                'detail': f'Official weight of {bol.official_weight_tons} tons was entered on {bol.official_weight_entered_at} by {bol.official_weight_entered_by}'
            }, status=status.HTTP_409_CONFLICT)

        # Set official weight using model method (handles variance calculation)
        entered_by = request.user.email or request.user.username
        bol.set_official_weight(weight_tons, entered_by)

        # Audit log
        audit(request, 'OFFICIAL_WEIGHT_SET', bol,
              f"Official weight set to {weight_tons} tons (CBRT: {bol.net_tons} tons, variance: {bol.weight_variance_tons} tons / {bol.weight_variance_percent}%)",
              extra={
                  'bol_number': bol.bol_number,
                  'official_weight_tons': float(weight_tons),
                  'cbrt_weight_tons': float(bol.net_tons),
                  'variance_tons': float(bol.weight_variance_tons),
                  'variance_percent': float(bol.weight_variance_percent)
              })

        logger.info(f"Official weight set for BOL {bol.bol_number}: {weight_tons} tons by {entered_by}")

        pdf_url = bol.get_pdf_url()
        stamped_pdf_url = bol.stamped_pdf_url if (bol.stamped_pdf_url and bol.stamped_pdf_url.startswith('http')) else (default_storage.url(bol.stamped_pdf_url) if bol.stamped_pdf_url else None)

        return Response({
            'ok': True,
            'bolNumber': bol.bol_number,
            'officialWeightTons': round(float(bol.official_weight_tons), 2),
            'cbrtWeightTons': round(float(bol.net_tons), 2),
            'varianceTons': round(float(bol.weight_variance_tons), 2),
            'variancePercent': round(float(bol.weight_variance_percent), 2),
            'enteredBy': bol.official_weight_entered_by,
            'enteredAt': bol.official_weight_entered_at.isoformat() if bol.official_weight_entered_at else None,
            'pdfUrl': pdf_url,
            'stampedPdfUrl': stamped_pdf_url
        })

    except BOL.DoesNotExist:
        logger.error(f"BOL {bol_id} not found")
        return Response({'error': 'BOL not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error setting official weight for BOL {bol_id}: {str(e)}", exc_info=True)
        return Response({'error': 'Failed to set official weight', 'detail': str(e)},
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
@require_role('admin')  # Regenerating PDFs requires admin role (sensitive operation)
@feature_permission_required('admin', 'modify')
def regenerate_bol_pdf(request, bol_id):
    """
    Regenerate the PDF for a BOL using current data.
    Useful when BOL data changes after creation or PDF is corrupted.
    """
    try:
        bol = BOL.objects.get(id=bol_id, **get_tenant_filter(request))

        # Regenerate PDF
        try:
            pdf_url = generate_bol_pdf(bol)
            bol.pdf_url = pdf_url
            bol.pdf_key = _derive_pdf_key(pdf_url)
            bol.save(update_fields=['pdf_url', 'pdf_key', 'updated_at'])
            logger.info(f"Regenerated PDF for BOL {bol.bol_number} at {pdf_url}")

            # Audit log
            audit(request, 'BOL_PDF_REGENERATED', bol,
                  f"PDF regenerated for BOL {bol.bol_number}",
                  extra={'bol_number': bol.bol_number, 'pdf_url': pdf_url})

            return Response({
                'success': True,
                'message': f'PDF regenerated for BOL {bol.bol_number}',
                'pdfUrl': pdf_url,
                'bolNumber': bol.bol_number
            })
        except Exception as pdf_error:
            logger.error(f"Failed to regenerate PDF for BOL {bol.bol_number}: {str(pdf_error)}", exc_info=True)
            return Response({
                'error': 'Failed to generate PDF',
                'detail': str(pdf_error)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except BOL.DoesNotExist:
        logger.error(f"BOL {bol_id} not found for PDF regeneration")
        return Response({'error': 'BOL not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error regenerating PDF for BOL {bol_id}: {str(e)}", exc_info=True)
        return Response({'error': 'Failed to regenerate PDF', 'detail': str(e)},
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_role('Admin', 'Office', 'Client')  # All authenticated users - Phase 2 audit fix
@feature_permission_required('bol', 'view')
def download_bol_pdf(request, bol_id):
    """
    Generate a fresh download link for a BOL PDF.

    With S3, this returns a signed URL with 24-hour expiration.
    Logs all downloads for audit compliance.

    Returns:
        {
            'downloadUrl': 'https://s3.amazonaws.com/...',
            'expiresIn': 86400,
            'bolNumber': 'PRT-2025-0005'
        }
    """
    try:
        bol = BOL.objects.get(id=bol_id, **get_tenant_filter(request))

        # Generate signed URL (prefers pdf_key; falls back to legacy pdf_url)
        from django.core.files.storage import default_storage

        download_url = bol.get_pdf_url()
        if not download_url and bol.pdf_key:
            # Try to generate explicitly if get_pdf_url failed
            try:
                download_url = default_storage.url(bol.pdf_key)
            except Exception:
                pass

        if not download_url:
            logger.error(f"No PDF available for BOL {bol.bol_number}")
            return Response({'error': 'PDF not available'}, status=status.HTTP_404_NOT_FOUND)

        # Audit log the download
        user_email = request.user.email or request.user.username
        audit(request, 'BOL_DOWNLOADED', bol,
              f"BOL PDF downloaded by {user_email}",
              extra={
                  'bol_number': bol.bol_number,
                  'user_email': user_email
              })

        logger.info(f"BOL PDF download requested: {bol.bol_number} by {user_email}")

        return Response({
            'downloadUrl': download_url,
            'expiresIn': 86400,  # 24 hours
            'bolNumber': bol.bol_number,
            'fileName': f"{bol.bol_number}.pdf"
        })

    except BOL.DoesNotExist:
        logger.error(f"BOL {bol_id} not found for download")
        return Response({'error': 'BOL not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error generating download link for BOL {bol_id}: {str(e)}", exc_info=True)
        return Response({'error': 'Failed to generate download link', 'detail': str(e)},
                       status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Release upload and parse (Phase 1: parse only)
@api_view(['POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
@require_role('admin', 'office')  # Allow Admin and Office roles to upload releases (both have write permission)
@feature_permission_required('releases', 'create')
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


# =============================
# EOM Inventory Report endpoint
# =============================
@api_view(['GET'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
@require_role('Admin', 'Office')  # Internal staff only
@feature_permission_required('reports', 'view')
def inventory_report(request):
    """
    EOM Inventory Report with date range filtering.

    Query params:
    - from_date: Start of period (YYYY-MM-DD or MM/DD/YYYY)
    - to_date: End of period (YYYY-MM-DD or MM/DD/YYYY)
    - format: 'json' (default) or 'pdf'

    Returns per-product:
    - Beginning inventory (start_tons minus BOLs shipped BEFORE from_date)
    - Shipped during period (BOLs with date in range)
    - Ending inventory (beginning minus shipped)
    - BOL details for the period
    """
    try:
        from_date_str = request.query_params.get('from_date', '')
        to_date_str = request.query_params.get('to_date', '')
        output_format = request.query_params.get('format', 'json')

        from_date = _parse_date_any(from_date_str) if from_date_str else None
        to_date = _parse_date_any(to_date_str) if to_date_str else None

        # Validate date range if both provided
        if from_date and to_date and from_date > to_date:
            return Response(
                {'error': 'from_date must be before or equal to to_date'},
                status=status.HTTP_400_BAD_REQUEST
            )

        products = Product.objects.filter(is_active=True, **get_tenant_filter(request))
        result = []
        grand_beginning = 0
        grand_shipped = 0
        grand_ending = 0

        for product in products:
            bols = BOL.objects.filter(product=product, **get_tenant_filter(request))

            # Separate BOLs into pre-period and in-period
            shipped_before = 0
            shipped_in_period = 0
            period_bols = []

            for bol in bols:
                bol_date = _parse_date_any(bol.date)

                # Use CBRT scale weight (net_tons) per client request
                try:
                    weight = float(bol.net_tons)
                except (TypeError, ValueError):
                    weight = 0.0

                # Categorize by date
                if bol_date is None:
                    # Unknown date - include in shipped_before as conservative default
                    shipped_before += weight
                elif from_date and bol_date < from_date:
                    shipped_before += weight
                elif (from_date is None or bol_date >= from_date) and (to_date is None or bol_date <= to_date):
                    shipped_in_period += weight
                    period_bols.append({
                        'id': bol.id,
                        'bol_number': bol.bol_number,
                        'date': bol.date,
                        'weight_tons': round(weight, 2),
                        'is_official': False,  # Always CBRT weight now
                        'customer': bol.buyer_name,
                        'release_number': bol.release_number or '',
                        'pdf_url': bol.get_pdf_url() or ''
                    })
                elif to_date and bol_date > to_date:
                    # After period - don't count
                    pass
                else:
                    # Fallback for edge cases
                    shipped_before += weight

            start_tons = float(product.start_tons)
            beginning = round(start_tons - shipped_before, 2)
            shipped = round(shipped_in_period, 2)
            ending = round(beginning - shipped, 2)

            grand_beginning += beginning
            grand_shipped += shipped
            grand_ending += ending

            result.append({
                'id': product.id,
                'name': product.name,
                'start_tons': round(start_tons, 2),
                'beginning_inventory': beginning,
                'shipped_this_period': shipped,
                'ending_inventory': ending,
                'bols': sorted(period_bols, key=lambda x: x['date'] or '')
            })

        report_data = {
            'from_date': from_date.isoformat() if from_date else None,
            'to_date': to_date.isoformat() if to_date else None,
            'generated_at': datetime.now().isoformat(),
            'products': result,
            'totals': {
                'beginning_inventory': round(grand_beginning, 2),
                'shipped_this_period': round(grand_shipped, 2),
                'ending_inventory': round(grand_ending, 2)
            }
        }

        return Response(report_data)

    except Exception as e:
        logger.error(f"Error in inventory_report: {str(e)}", exc_info=True)
        return Response(
            {'error': 'An unexpected error occurred', 'detail': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


from django.contrib.auth.decorators import login_required
from django.http import HttpResponse as DjangoHttpResponse

@login_required
@require_role('Admin', 'Office')
@feature_permission_required('reports', 'view')
def inventory_report_pdf(request):
    """
    Generate PDF for EOM Inventory Report.
    Separate endpoint to avoid DRF/HttpResponse conflicts.

    Query params:
    - from_date: Start of period (YYYY-MM-DD)
    - to_date: End of period (YYYY-MM-DD)
    """
    try:
        from_date_str = request.GET.get('from_date', '')
        to_date_str = request.GET.get('to_date', '')

        from_date = _parse_date_any(from_date_str) if from_date_str else None
        to_date = _parse_date_any(to_date_str) if to_date_str else None

        # Build report data (same logic as inventory_report)
        products = Product.objects.filter(is_active=True, **get_tenant_filter(request))
        result = []
        grand_beginning = 0
        grand_shipped = 0
        grand_ending = 0

        for product in products:
            bols = BOL.objects.filter(product=product, **get_tenant_filter(request))
            shipped_before = 0
            shipped_in_period = 0
            period_bols = []

            for bol in bols:
                bol_date = _parse_date_any(bol.date)
                # Use CBRT scale weight (net_tons) per client request
                try:
                    weight = float(bol.net_tons)
                except (TypeError, ValueError):
                    weight = 0.0

                if bol_date is None:
                    shipped_before += weight
                elif from_date and bol_date < from_date:
                    shipped_before += weight
                elif (from_date is None or bol_date >= from_date) and (to_date is None or bol_date <= to_date):
                    shipped_in_period += weight
                    period_bols.append({
                        'id': bol.id,
                        'bol_number': bol.bol_number,
                        'date': bol.date,
                        'weight_tons': round(weight, 2),
                        'is_official': False,  # Always CBRT weight now
                        'customer': bol.buyer_name,
                        'release_number': bol.release_number or '',
                        'pdf_url': bol.get_pdf_url() or ''
                    })
                elif to_date and bol_date > to_date:
                    pass
                else:
                    shipped_before += weight

            start_tons = float(product.start_tons)
            beginning = round(start_tons - shipped_before, 2)
            shipped = round(shipped_in_period, 2)
            ending = round(beginning - shipped, 2)

            grand_beginning += beginning
            grand_shipped += shipped
            grand_ending += ending

            result.append({
                'id': product.id,
                'name': product.name,
                'start_tons': round(start_tons, 2),
                'beginning_inventory': beginning,
                'shipped_this_period': shipped,
                'ending_inventory': ending,
                'bols': sorted(period_bols, key=lambda x: x['date'] or '')
            })

        report_data = {
            'from_date': from_date.isoformat() if from_date else None,
            'to_date': to_date.isoformat() if to_date else None,
            'generated_at': datetime.now().isoformat(),
            'products': result,
            'totals': {
                'beginning_inventory': round(grand_beginning, 2),
                'shipped_this_period': round(grand_shipped, 2),
                'ending_inventory': round(grand_ending, 2)
            }
        }

        # Generate PDF
        from bol_system.inventory_report_pdf import generate_eom_inventory_pdf
        pdf_bytes = generate_eom_inventory_pdf(report_data)

        response = DjangoHttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"inventory_report_{from_date or 'all'}_{to_date or 'all'}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        logger.error(f"Error in inventory_report_pdf: {str(e)}", exc_info=True)
        return DjangoHttpResponse(
            f"Error generating PDF: {str(e)}",
            status=500,
            content_type='text/plain'
        )


# =============================================================================
# Client Portal APIs
# =============================================================================

def get_user_customer(request):
    """
    Get primary customer for the current user.

    Returns Customer object if user has a UserCustomerAccess record,
    None otherwise.

    Usage:
        customer = get_user_customer(request)
        if not customer:
            return Response({'error': 'No customer association'}, status=403)
    """
    from .models import UserCustomerAccess

    try:
        access = UserCustomerAccess.objects.select_related('customer').get(
            user_email=request.user.email,
            is_primary=True
        )
        return access.customer
    except UserCustomerAccess.DoesNotExist:
        return None


def get_user_customers(request):
    """
    Get all customers the current user can access.

    Returns QuerySet of UserCustomerAccess objects.
    """
    from .models import UserCustomerAccess

    return UserCustomerAccess.objects.filter(
        user_email=request.user.email
    ).select_related('customer').order_by('-is_primary', 'customer__customer')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@feature_permission_required('client_portal', 'view')
def client_context(request):
    """
    Return client portal context for single-tenant mode.

    In single-tenant mode, client_portal:view permission grants access
    to all data (read-only). No customer association required.

    Returns:
        - user_email: Current user's email
        - access_level: Always 'view' for client portal
        - mode: 'single_tenant' to indicate full data access
    """
    return Response({
        'user_email': request.user.email,
        'access_level': 'view',
        'mode': 'single_tenant',
        'customer': None,  # Not used in single-tenant mode
        'customers': [],   # Not used in single-tenant mode
        'has_customer_access': True,  # Always true - permission is the gate
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@feature_permission_required('client_portal', 'view')
def client_shipments(request):
    """
    Return all BOLs/shipments (single-tenant, read-only).

    Same format as /api/history/ for frontend compatibility.
    """
    bols = BOL.objects.select_related('product', 'customer').order_by('-created_at')

    rows = []
    for bol in bols:
        has_official = bol.official_weight_tons is not None
        display_weight = float(bol.official_weight_tons) if has_official else float(bol.net_tons or 0)

        rows.append({
            'id': bol.id,
            'bolNo': bol.bol_number,
            'date': bol.date,
            'truckNo': bol.truck_number,
            'netTons': round(display_weight, 2),
            'cbrtWeightTons': round(float(bol.net_tons or 0), 2),
            'pdfUrl': bol.get_pdf_url(),
            'productName': bol.product_name,
            'buyerName': bol.buyer_name,
            'officialWeightTons': round(float(bol.official_weight_tons), 2) if has_official else None,
        })

    return Response({
        'summary': None,
        'rows': rows
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@feature_permission_required('client_portal', 'view')
def client_pending_loads(request):
    """
    Return all pending release loads (single-tenant, read-only).

    Same format as /api/releases/pending-loads/ for frontend compatibility.
    """
    from datetime import date as date_class, timedelta
    today = date_class.today()

    # Calculate current calendar week (Sunday-Saturday)
    days_since_sunday = (today.weekday() + 1) % 7
    this_week_start = today - timedelta(days=days_since_sunday)
    this_week_end = this_week_start + timedelta(days=6)
    next_week_start = this_week_end + timedelta(days=1)
    next_week_end = next_week_start + timedelta(days=6)

    loads = ReleaseLoad.objects.filter(status='PENDING').select_related(
        'release', 'release__customer_ref', 'release__carrier_ref',
        'release__lot_ref', 'release__lot_ref__product'
    ).order_by('date', 'seq')

    result = []
    for ld in loads:
        r = ld.release
        prod = getattr(getattr(r, 'lot_ref', None), 'product', None)

        # Parse scheduled date and calculate urgency
        sched_date = datetime.strptime(ld.date, '%Y-%m-%d').date() if isinstance(ld.date, str) else ld.date
        days_until = (sched_date - today).days

        # Determine urgency level
        if days_until < 0:
            urgency = 'overdue'
        elif days_until == 0:
            urgency = 'today'
        elif this_week_start <= sched_date <= this_week_end:
            urgency = 'this-week'
        elif next_week_start <= sched_date <= next_week_end:
            urgency = 'next-week'
        else:
            urgency = 'later'

        result.append({
            'loadId': ld.id,
            'releaseId': r.id,
            'releaseNumber': r.release_number,
            'seq': ld.seq,
            'scheduledDate': ld.date,
            'plannedTons': float(ld.planned_tons or 0),
            'daysUntil': days_until,
            'urgency': urgency,
            'customer': {
                'id': getattr(r.customer_ref, 'id', None),
                'name': getattr(r.customer_ref, 'customer', r.customer_id_text)
            },
            'carrier': {
                'id': getattr(r.carrier_ref, 'id', None),
                'name': getattr(getattr(r, 'carrier_ref', None), 'carrier_name', r.ship_via)
            },
            'product': {
                'id': getattr(prod, 'id', None),
                'name': getattr(prod, 'name', r.material_description)
            },
        })

    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@feature_permission_required('client_portal', 'view')
def client_inventory(request):
    """
    Return all products with balances (tenant-scoped, read-only).

    Shows all active products with start/shipped/remaining tons.
    Uses same format as /api/balances/ for frontend compatibility.
    """
    products = Product.objects.filter(is_active=True, **get_tenant_filter(request)).order_by('name')

    # Match /api/balances/ field names for frontend compatibility
    return Response([
        {
            'id': product.id,
            'name': product.name,
            'startTons': round(float(product.start_tons), 2),
            'shipped': round(float(product.shipped_tons), 2),
            'remaining': round(float(product.remaining_tons), 2),
        }
        for product in products
    ])
