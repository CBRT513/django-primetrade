from django.contrib import admin
from .models import (
    Product, Customer, Carrier, Truck, BOL, BOLCounter, CompanyBranding,
    RoleRedirectConfig, Tenant, Release, ReleaseLoad, Lot, AuditLog, CustomerShipTo,
    UserCustomerAccess
)


# =============================================================================
# Tenant Admin Mixin for data isolation in Django Admin
# =============================================================================
class TenantAdminMixin:
    """
    Mixin for admin classes to filter by tenant.

    For superusers: Shows all data with tenant column
    For staff users: Filter based on session tenant (if available)
    """

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Non-superusers see data filtered by their tenant
        tenant = getattr(request, 'tenant', None)
        if tenant:
            return qs.filter(tenant=tenant)
        return qs

    def get_list_display(self, request):
        list_display = list(super().get_list_display(request))
        # Add tenant column for superusers
        if request.user.is_superuser and 'tenant' not in list_display:
            list_display.insert(0, 'tenant')
        return list_display

    def get_list_filter(self, request):
        list_filter = list(super().get_list_filter(request))
        # Add tenant filter for superusers
        if request.user.is_superuser and 'tenant' not in list_filter:
            list_filter.insert(0, 'tenant')
        return list_filter


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'code']


@admin.register(Product)
class ProductAdmin(TenantAdminMixin, admin.ModelAdmin):
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
class CustomerAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ['customer', 'city', 'state', 'is_active']
    list_filter = ['is_active', 'state']
    search_fields = ['customer', 'city']

class TruckInline(admin.TabularInline):
    model = Truck
    extra = 1

@admin.register(Carrier)
class CarrierAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ['carrier_name', 'contact_name', 'phone', 'is_active']
    list_filter = ['is_active']
    search_fields = ['carrier_name', 'contact_name']
    inlines = [TruckInline]

@admin.register(BOL)
class BOLAdmin(TenantAdminMixin, admin.ModelAdmin):
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


@admin.register(RoleRedirectConfig)
class RoleRedirectConfigAdmin(admin.ModelAdmin):
    """Admin interface for role-based landing page configuration"""
    list_display = ['role_name', 'landing_page', 'is_active', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['role_name', 'landing_page']
    list_editable = ['landing_page', 'is_active']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Role Configuration', {
            'fields': ('role_name', 'landing_page', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# =============================================================================
# Additional Tenant-Filtered Admin Classes
# =============================================================================
class ReleaseLoadInline(admin.TabularInline):
    model = ReleaseLoad
    extra = 0
    readonly_fields = ['seq', 'date', 'planned_tons', 'status', 'bol']


@admin.register(Release)
class ReleaseAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ['release_number', 'customer_id_text', 'status', 'quantity_net_tons', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['release_number', 'customer_id_text', 'customer_po']
    inlines = [ReleaseLoadInline]


@admin.register(Lot)
class LotAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ['code', 'product', 'c', 'si', 's', 'p', 'mn']
    list_filter = ['product']
    search_fields = ['code']


@admin.register(AuditLog)
class AuditLogAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ['action', 'object_type', 'object_id', 'user_email', 'created_at']
    list_filter = ['action', 'object_type', 'created_at']
    search_fields = ['action', 'object_type', 'object_id', 'user_email', 'message']
    readonly_fields = [
        'action', 'object_type', 'object_id', 'message', 'user_email',
        'ip', 'method', 'path', 'user_agent', 'extra', 'created_at'
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CustomerShipTo)
class CustomerShipToAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ['customer', 'name', 'city', 'state', 'is_active']
    list_filter = ['is_active', 'state']
    search_fields = ['customer__customer', 'name', 'city']


@admin.register(UserCustomerAccess)
class UserCustomerAccessAdmin(admin.ModelAdmin):
    """Admin interface for managing user-customer associations (Client Portal)."""
    list_display = ['user_email', 'customer', 'is_primary', 'access_level', 'created_at']
    list_filter = ['is_primary', 'access_level', 'created_at']
    search_fields = ['user_email', 'customer__customer']
    autocomplete_fields = ['customer']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('User Association', {
            'fields': ('user_email', 'customer')
        }),
        ('Access Settings', {
            'fields': ('is_primary', 'access_level')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )