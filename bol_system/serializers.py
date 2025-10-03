from rest_framework import serializers
from .models import *

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'start_tons', 'is_active']

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