from rest_framework import serializers
from .models import *

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
    
        fields = ['id', 'name', 'start_tons', 'is_active',
                  'last_lot_code','c','si','s','p','mn']

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'customer', 'address', 'city', 'state', 'zip', 'is_active']

class CarrierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Carrier
        fields = ['id', 'carrier_name', 'contact_name', 'phone', 'email', 'is_active']

class TruckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Truck
        fields = ['id', 'truck_number', 'trailer_number', 'is_active']

class BOLSerializer(serializers.ModelSerializer):
    class Meta:
        model = BOL
        fields = ['id', 'bol_number', 'product_name', 'buyer_name', 'date', 
                 'truck_number', 'net_tons', 'pdf_url']

class ReleaseLoadSerializer(serializers.ModelSerializer):
    bol_number = serializers.SerializerMethodField()

    class Meta:
        model = ReleaseLoad
        fields = ['id', 'seq', 'date', 'planned_tons', 'status', 'bol', 'bol_number']

    def get_bol_number(self, obj):
        return obj.bol.bol_number if obj.bol else None

class CustomerShipToSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerShipTo
        fields = ['id','name','street','city','state','zip']

class LotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lot
        fields = ['id','code','c','si','s','p','mn']

class ReleaseSerializer(serializers.ModelSerializer):
    loads = ReleaseLoadSerializer(many=True, read_only=True)
    customer_ref = CustomerSerializer(read_only=True)
    ship_to_ref = CustomerShipToSerializer(read_only=True)
    carrier_ref = CarrierSerializer(read_only=True)
    lot_ref = LotSerializer(read_only=True)

    class Meta:
        model = Release
        fields = [
            'id','release_number','release_date','customer_id_text','customer_po',
            'ship_via','fob','ship_to_name','ship_to_street','ship_to_city','ship_to_state','ship_to_zip',
            'lot','material_description','quantity_net_tons','status','loads',
            'customer_ref','ship_to_ref','carrier_ref','lot_ref'
        ]

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id','action','object_type','object_id','message','user_email','ip','method','path','user_agent','extra','created_at']
