from django.contrib import admin
from .models import DriverSession


@admin.register(DriverSession)
class DriverSessionAdmin(admin.ModelAdmin):
    list_display = ['code', 'driver_name', 'phone', 'visit_type', 'status', 'checked_in_at']
    list_filter = ['status', 'visit_type', 'checked_in_at']
    search_fields = ['code', 'driver_name', 'phone', 'bol_number']
    readonly_fields = ['code', 'checked_in_at', 'assigned_at', 'signed_at', 'completed_at']
    ordering = ['-checked_in_at']
