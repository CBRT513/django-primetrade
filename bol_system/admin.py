from django.contrib import admin
from .models import *

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_tons', 'shipped_tons_display', 'remaining_tons_display', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']
    readonly_fields = ['shipped_tons_display', 'remaining_tons_display']
    
    def shipped_tons_display(self, obj):
        return f"{obj.shipped_tons:.2f}"
    shipped_tons_display.short_description = "Shipped"
    
    def remaining_tons_display(self, obj):
        return f"{obj.remaining_tons:.2f}"
    remaining_tons_display.short_description = "Remaining"

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['customer', 'city', 'state', 'is_active']
    list_filter = ['is_active', 'state']
    search_fields = ['customer', 'city']

class TruckInline(admin.TabularInline):
    model = Truck
    extra = 1

@admin.register(Carrier)
class CarrierAdmin(admin.ModelAdmin):
    list_display = ['carrier_name', 'contact_name', 'phone', 'is_active']
    list_filter = ['is_active']
    search_fields = ['carrier_name', 'contact_name']
    inlines = [TruckInline]

@admin.register(BOL)
class BOLAdmin(admin.ModelAdmin):
    list_display = ['bol_number', 'product_name', 'buyer_name', 'carrier_name', 'net_tons', 'created_at']
    list_filter = ['product', 'carrier', 'created_at']
    search_fields = ['bol_number', 'buyer_name']
    readonly_fields = ['bol_number', 'total_weight_lbs_display']
    
    def total_weight_lbs_display(self, obj):
        return f"{obj.total_weight_lbs:.0f} lbs"
    total_weight_lbs_display.short_description = "Total Weight"

@admin.register(BOLCounter)
class BOLCounterAdmin(admin.ModelAdmin):
    list_display = ['year', 'sequence']
    readonly_fields = ['year', 'sequence']

@admin.register(CompanyBranding)
class CompanyBrandingAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not CompanyBranding.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False