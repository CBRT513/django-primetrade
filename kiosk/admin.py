from django.contrib import admin
from .models import DriverSession


@admin.register(DriverSession)
class DriverSessionAdmin(admin.ModelAdmin):
    list_display = ['code', 'driver_name', 'carrier_name', 'pickup_number', 'status', 'checked_in_at']
    list_filter = ['status', 'checked_in_at']
    search_fields = ['code', 'driver_name', 'phone', 'carrier_name', 'pickup_number', 'bol_number']
    readonly_fields = ['code', 'checked_in_at', 'assigned_at', 'signed_at', 'completed_at']
    ordering = ['-checked_in_at']
