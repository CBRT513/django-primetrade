from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import models
from .models import *
from .serializers import *
from .pdf_generator import generate_bol_pdf
import logging

logger = logging.getLogger(__name__)

# Product endpoints
class ProductListView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    
    def get_queryset(self):
        return Product.objects.filter(is_active=True).order_by('name')

# Customer endpoints  
class CustomerListView(generics.ListCreateAPIView):
    serializer_class = CustomerSerializer
    
    def get_queryset(self):
        return Customer.objects.filter(is_active=True).order_by('customer')

# Carrier endpoints with trucks
@api_view(['GET', 'POST'])
def carrier_list(request):
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
                
                return Response({'ok': True, 'id': carrier.id})
            except Carrier.DoesNotExist:
                return Response({'error': 'Carrier not found'}, status=404)
        else:
            # Create new carrier
            carrier = Carrier.objects.create(
                carrier_name=data.get('carrier_name'),
                contact_name=data.get('contact_name', ''),
                phone=data.get('phone', ''),
                email=data.get('email', ''),
                is_active=data.get('is_active', True)
            )
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

# BOL creation
@api_view(['POST'])
def create_bol(request):
    try:
        data = request.data
        
        # Validation
        required_fields = ['date', 'productId', 'buyerName', 'shipTo', 'netTons']
        for field in required_fields:
            if not data.get(field):
                return Response({'error': f'Missing field: {field}'}, 
                              status=status.HTTP_400_BAD_REQUEST)
        
        # Get related objects
        product = Product.objects.get(id=data['productId'])
        carrier = Carrier.objects.get(id=data.get('carrierId', ''))
        customer = Customer.objects.get(id=data.get('customerId', '')) if data.get('customerId') else None
        truck = Truck.objects.get(id=data.get('truckId', '')) if data.get('truckId') else None
        
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
            net_tons=float(data['netTons']),
            notes=data.get('notes', ''),
            customer=customer,
            customer_po=data.get('customerPO', ''),
            created_by_email='system@primetrade.com'
        )

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
        
    except Exception as e:
        return Response({'ok': False, 'error': str(e)}, 
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Inventory balances
@api_view(['GET'])
def balances(request):
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

# BOL history
@api_view(['GET'])
def bol_history(request):
    product_id = request.GET.get('productId')
    if not product_id:
        return Response({'error': 'productId required'}, status=400)
    
    try:
        product = Product.objects.get(id=product_id)
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
        
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=404)

# BOL detail view
@api_view(['GET'])
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
        return Response({'error': 'BOL not found'}, status=404)