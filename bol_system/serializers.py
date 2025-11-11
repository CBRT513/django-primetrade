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
        fields = ['id', 'customer', 'address', 'address2', 'city', 'state', 'zip', 'is_active']

class CarrierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Carrier
        fields = ['id', 'carrier_name', 'contact_name', 'phone', 'email', 'is_active']

class TruckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Truck
        fields = ['id', 'truck_number', 'trailer_number', 'is_active']

class BOLSerializer(serializers.ModelSerializer):
    effective_weight_tons = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = BOL
        fields = ['id', 'bol_number', 'product_name', 'buyer_name', 'date',
                 'truck_number', 'net_tons', 'pdf_url', 'stamped_pdf_url',
                 'official_weight_tons', 'official_weight_entered_by', 'official_weight_entered_at',
                 'weight_variance_tons', 'weight_variance_percent', 'effective_weight_tons']

class ReleaseLoadSerializer(serializers.ModelSerializer):
    bol_number = serializers.SerializerMethodField()
    bol_pdf_url = serializers.SerializerMethodField()
    bol_stamped_pdf_url = serializers.SerializerMethodField()
    bol_created_at = serializers.SerializerMethodField()
    cbrt_tons = serializers.SerializerMethodField()
    official_weight_tons = serializers.SerializerMethodField()

    class Meta:
        model = ReleaseLoad
        fields = ['id', 'seq', 'date', 'planned_tons', 'official_weight_tons', 'cbrt_tons', 'status', 'bol', 'bol_number', 'bol_pdf_url', 'bol_stamped_pdf_url', 'bol_created_at']

    def get_bol_number(self, obj):
        return obj.bol.bol_number if obj.bol else None

    def get_bol_pdf_url(self, obj):
        if not obj.bol or not obj.bol.pdf_url:
            return None
        # Convert S3 path to full URL
        from django.core.files.storage import default_storage
        try:
            return default_storage.url(obj.bol.pdf_url)
        except:
            return obj.bol.pdf_url  # Fallback to stored value

    def get_bol_stamped_pdf_url(self, obj):
        """Get watermarked PDF URL with official weight stamp"""
        if not obj.bol or not obj.bol.stamped_pdf_url:
            return None
        # Convert S3 path to full URL
        from django.core.files.storage import default_storage
        try:
            return default_storage.url(obj.bol.stamped_pdf_url)
        except:
            return obj.bol.stamped_pdf_url  # Fallback to stored value

    def get_bol_created_at(self, obj):
        return obj.bol.created_at.isoformat() if obj.bol else None

    def get_cbrt_tons(self, obj):
        """Get CBRT weight from BOL (loader's weight entered at creation)"""
        return float(obj.bol.net_tons) if obj.bol else None

    def get_official_weight_tons(self, obj):
        """Get official certified scale weight from BOL"""
        return float(obj.bol.official_weight_tons) if obj.bol and obj.bol.official_weight_tons else None

class CustomerShipToSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerShipTo
        fields = ['id','name','street','street2','city','state','zip']

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
            'ship_via','fob','ship_to_name','ship_to_street','ship_to_street2','ship_to_city','ship_to_state','ship_to_zip',
            'lot','material_description','quantity_net_tons','status','special_instructions','loads',
            'customer_ref','ship_to_ref','carrier_ref','lot_ref'
        ]

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id','action','object_type','object_id','message','user_email','ip','method','path','user_agent','extra','created_at']
