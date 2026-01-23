from django.db import models
from datetime import date


class DriverSession(models.Model):
    """Tracks a driver's visit from check-in to check-out."""

    # Unique code (e.g., "6044-01")
    code = models.CharField(max_length=10, unique=True, db_index=True)

    # Driver info (collected at check-in)
    driver_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    pickup_number = models.CharField(max_length=50, default='')
    carrier_name = models.CharField(max_length=200, default='')
    truck_number = models.CharField(max_length=50, default='')
    trailer_number = models.CharField(max_length=50, default='')

    # Legacy fields (kept for backward compatibility)
    visit_type = models.CharField(max_length=20, blank=True, default='pickup')
    notes = models.TextField(blank=True)

    # Status
    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('assigned', 'Assigned'),
        ('ready', 'Ready'),
        ('signed', 'Signed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')

    # BOL reference (set when office assigns BOL)
    bol_id = models.IntegerField(null=True, blank=True)
    bol_number = models.CharField(max_length=50, blank=True)

    # Timestamps
    checked_in_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Audit
    assigned_by = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-checked_in_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['status', 'checked_in_at']),
        ]

    def __str__(self):
        return f"{self.code} - {self.driver_name}"

    def is_expired(self):
        """Sessions expire after 4 hours."""
        from django.utils import timezone
        from datetime import timedelta
        if self.status in ('completed', 'cancelled', 'expired'):
            return True
        return timezone.now() > self.checked_in_at + timedelta(hours=4)
