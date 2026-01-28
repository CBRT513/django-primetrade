from django.db import models, transaction
from django.core.validators import RegexValidator
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Tenant(models.Model):
    """
    Multi-tenant support for PrimeTrade.

    Each tenant represents a distinct customer/organization with isolated data.
    All tenant-scoped models have a ForeignKey to Tenant.
    """
    name = models.CharField(max_length=100, help_text="Full tenant name (e.g., 'Liberty Steel')")
    code = models.CharField(max_length=20, unique=True, help_text="Short code (e.g., 'LIBERTY')")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class TimestampedModel(models.Model):
    """Base model with common timestamp fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200, blank=True, default='system')

    class Meta:
        abstract = True

class Product(TimestampedModel):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True,
        related_name='products', help_text='Tenant this product belongs to'
    )
    name = models.CharField(max_length=200, unique=True)
    start_tons = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    # Optional mirrors for latest lot identification and chemistry for quick double-checking
    last_lot_code = models.CharField(max_length=100, blank=True)
    c = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    si = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    s = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    p = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    mn = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def shipped_tons(self):
        """Calculate shipped tons using official weight if available, otherwise CBRT scale weight"""
        from django.db.models.functions import Coalesce
        return self.bol_set.aggregate(
            total=models.Sum(Coalesce('official_weight_tons', 'net_tons'))
        )['total'] or 0
    
    @property
    def remaining_tons(self):
        return self.start_tons - self.shipped_tons

class Customer(TimestampedModel):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True,
        related_name='customers', help_text='Tenant this customer belongs to'
    )
    customer = models.CharField(max_length=200, unique=True)
    address = models.CharField(max_length=200)
    address2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    zip = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)

    # Customer branding for dashboard
    logo_url = models.URLField(max_length=500, blank=True, help_text="URL to customer's logo image")
    primary_color = models.CharField(max_length=7, blank=True, default='#2563eb',
                                    help_text="Primary brand color (hex code, e.g., #2563eb)")
    secondary_color = models.CharField(max_length=7, blank=True, default='#667eea',
                                      help_text="Secondary brand color (hex code, e.g., #667eea)")

    class Meta:
        ordering = ['customer']

    def __str__(self):
        return self.customer

    @property
    def full_address(self):
        address_lines = [self.address]
        if self.address2:
            address_lines.append(self.address2)
        address_lines.append(f"{self.city}, {self.state} {self.zip}")
        return "\n".join(address_lines)

class CustomerShipTo(TimestampedModel):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True,
        related_name='ship_tos', help_text='Tenant this ship-to belongs to'
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='ship_tos')
    name = models.CharField(max_length=200, blank=True)
    street = models.CharField(max_length=200)
    street2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    zip = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['customer','name']
        unique_together = [['customer','street','city','state','zip']]

    def __str__(self):
        return f"{self.customer.customer} -> {self.street}, {self.city}" 

class Carrier(TimestampedModel):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True,
        related_name='carriers', help_text='Tenant this carrier belongs to'
    )
    carrier_name = models.CharField(max_length=200, unique=True)
    contact_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['carrier_name']
    
    def __str__(self):
        return self.carrier_name

class Truck(TimestampedModel):
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE, related_name='trucks')
    truck_number = models.CharField(max_length=50)
    trailer_number = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['truck_number']
        unique_together = [['carrier', 'truck_number']]
    
    def __str__(self):
        return f"{self.truck_number} / {self.trailer_number}"

class BOLCounter(models.Model):
    """
    Atomic BOL number sequence per tenant + year.

    Scope: (tenant, year) - resets annually
    Format: {prefix}-{year}-{seq:04d} e.g., PRT-2025-0001

    Note: prefix is per-tenant config, not variable at runtime.
    Each tenant has one prefix (e.g., PRT for PrimeTrade).
    """
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True, blank=True,
        related_name='bol_counters', help_text='Tenant this counter belongs to'
    )
    year = models.IntegerField()
    sequence = models.IntegerField(default=0)

    class Meta:
        unique_together = [['tenant', 'year']]

    def __str__(self):
        tenant_code = self.tenant.code if self.tenant else 'GLOBAL'
        return f"{tenant_code}-{self.year}: {self.sequence}"

    @classmethod
    def get_next_bol_number(cls, tenant=None, prefix='PRT'):
        """
        Atomically get next BOL number.

        Uses select_for_update to prevent race conditions.

        Args:
            tenant: Tenant instance (optional for backward compat)
            prefix: BOL prefix (default 'PRT', can be from tenant config)

        Returns:
            String like "PRT-2025-0001"
        """
        from django.utils import timezone
        current_year = timezone.now().year

        with transaction.atomic():
            counter, created = cls.objects.select_for_update().get_or_create(
                tenant=tenant,
                year=current_year,
                defaults={'sequence': 0}
            )
            counter.sequence += 1
            counter.save()
            return f"{prefix}-{current_year}-{counter.sequence:04d}"

class BOL(TimestampedModel):
    """
    Universal BOL with PrimeTrade-specific fields.

    Immutability: Key data is snapshotted at issuance to prevent drift.
    One active (non-void) BOL per ReleaseLoad enforced by constraint.
    """
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True,
        related_name='bols', help_text='Tenant this BOL belongs to'
    )
    bol_number = models.CharField(max_length=20, db_index=True)
    bol_date = models.DateField(null=True, blank=True, help_text='BOL date as proper DateField')
    date = models.CharField(max_length=20, blank=True)  # Legacy - keep for backward compat

    # Voiding support (enables reissues)
    is_void = models.BooleanField(default=False, db_index=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.CharField(max_length=200, blank=True)
    void_reason = models.TextField(blank=True)

    # Audit fields
    issued_by = models.CharField(max_length=200, blank=True, help_text='User who issued this BOL')

    # Canonical relationships
    release_line = models.ForeignKey(
        'ReleaseLoad',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='bols',
        help_text='The release load this BOL fulfills'
    )
    lot = models.ForeignKey(
        'Lot',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='bols',
        help_text='Snapshot at issuance - do not update'
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE)
    truck = models.ForeignKey(Truck, on_delete=models.CASCADE, null=True, blank=True)

    # Snapshot display fields (immutable after creation)
    release_display = models.CharField(max_length=30, blank=True, help_text='"123-1" format for search/PDF')
    product_name = models.CharField(max_length=200)
    buyer_name = models.CharField(max_length=200)
    carrier_name = models.CharField(max_length=200)
    truck_number = models.CharField(max_length=50)
    trailer_number = models.CharField(max_length=50)
    chemistry_display = models.CharField(max_length=200, blank=True, help_text='Formatted chemistry at issuance')

    # Address and instructions (also snapshotted)
    ship_to = models.TextField()
    customer_po = models.CharField(max_length=100, blank=True)
    special_instructions = models.TextField(blank=True, help_text='Special warehouse/BOL requirements from release')
    care_of_co = models.CharField(
        max_length=200,
        blank=True,
        default='PrimeTrade, LLC',
        help_text="Company name for 'c/o' line in BOL Ship From section (copied from release)"
    )

    # Weight (first-class fields)
    net_tons = models.DecimalField(max_digits=10, decimal_places=2, help_text='CBRT scale weight (estimate)')
    official_weight_tons = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Certified scale weight (official)')
    official_weight_entered_by = models.CharField(max_length=200, blank=True, help_text='User who entered official weight')
    official_weight_entered_at = models.DateTimeField(null=True, blank=True, help_text='When official weight was entered')
    weight_variance_tons = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Difference between official and CBRT scale')
    weight_variance_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text='Percentage variance')

    # PDF storage
    pdf_url = models.URLField(max_length=1000, blank=True)
    pdf_key = models.CharField(max_length=500, blank=True, null=True, help_text='S3 object key for signed URL generation')
    stamped_pdf_url = models.URLField(max_length=1000, blank=True, help_text='Watermarked PDF with official weight stamp')

    # Legacy fields for backward compatibility
    notes = models.TextField(blank=True)
    created_by_email = models.CharField(max_length=200, default='system@primetrade.com')
    lot_ref = models.ForeignKey('Lot', on_delete=models.SET_NULL, null=True, blank=True, related_name='bols_legacy', help_text='Legacy lot reference')
    release_number = models.CharField(max_length=20, blank=True, help_text='Legacy release number for reference')

    # Driver signature fields (for kiosk checkout)
    signature = models.TextField(blank=True, help_text='Base64-encoded PNG signature')
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by = models.CharField(max_length=100, blank=True, help_text='Driver name who signed')

    # BOL status for kiosk workflow
    BOL_STATUS_CHOICES = [
        ('created', 'Created'),
        ('ready', 'Ready for Pickup'),
        ('signed', 'Signed'),
    ]
    bol_status = models.CharField(
        max_length=20,
        choices=BOL_STATUS_CHOICES,
        default='created',
        db_index=True,
        help_text='Kiosk workflow status'
    )

    class Meta:
        ordering = ['-created_at']
        unique_together = [['tenant', 'bol_number']]
        constraints = [
            # One active (non-void) BOL per ReleaseLoad
            models.UniqueConstraint(
                fields=['release_line'],
                condition=models.Q(is_void=False),
                name='uniq_active_bol_per_release_line'
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'bol_date']),
            models.Index(fields=['tenant', 'is_void']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.bol_number:
            self.bol_number = BOLCounter.get_next_bol_number()
        if self.product and not self.product_name:
            self.product_name = self.product.name
        if self.carrier and not self.carrier_name:
            self.carrier_name = self.carrier.carrier_name
        logger.info(f"BOL {self.bol_number} saved with {self.net_tons} tons")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Override delete to revert linked ReleaseLoad to PENDING status."""
        # Get related release loads before deletion
        release_loads = ReleaseLoad.objects.filter(bol=self)

        # Revert each load to PENDING
        for load in release_loads:
            load.status = 'PENDING'
            load.bol = None
            load.save(update_fields=['status', 'bol', 'updated_at'])
            logger.info(f"Reverted ReleaseLoad {load.id} to PENDING (BOL {self.bol_number} deleted)")

        # Call parent delete
        super().delete(*args, **kwargs)

    def __str__(self):
        return self.bol_number

    @property
    def total_weight_lbs(self):
        if self.net_tons is None:
            return 0.0
        return float(self.net_tons) * 2000

    @property
    def effective_weight_tons(self):
        """Returns official weight if available, otherwise CBRT scale weight"""
        return self.official_weight_tons if self.official_weight_tons is not None else self.net_tons

    def get_pdf_url(self):
        """
        Generate a fresh signed URL for the BOL PDF.
        - If pdf_key is set, generate a signed URL via default_storage
        - If pdf_url contains an S3 URL, extract the key and generate fresh signed URL
        - This ensures URLs never expire for the user
        """
        import re
        from django.core.files.storage import default_storage

        # Try pdf_key first (preferred)
        if hasattr(self, 'pdf_key') and self.pdf_key:
            try:
                return default_storage.url(self.pdf_key)
            except Exception:
                pass

        # Extract S3 key from legacy pdf_url and generate fresh signed URL
        if self.pdf_url:
            try:
                # Extract key from S3 URL (handles both styles)
                # e.g., https://bucket.s3.region.amazonaws.com/bols/2025/PRT-2025-0001.pdf
                # or https://s3.region.amazonaws.com/bucket/bols/2025/PRT-2025-0001.pdf
                match = re.search(r'amazonaws\.com/(.+?)(?:\?|$)', self.pdf_url)
                if match:
                    s3_key = match.group(1)
                    return default_storage.url(s3_key)
            except Exception:
                pass
            # Final fallback - return stored URL (may be expired)
            return self.pdf_url
        return None

    def set_official_weight(self, weight_tons, entered_by_email):
        """Set official weight, calculate variance, and generate watermarked PDF"""
        from django.utils import timezone
        from decimal import Decimal
        from .pdf_watermark import watermark_bol_pdf

        self.official_weight_tons = Decimal(str(weight_tons))
        self.official_weight_entered_by = entered_by_email
        self.official_weight_entered_at = timezone.now()

        # Calculate variance
        self.weight_variance_tons = self.official_weight_tons - self.net_tons
        if self.net_tons != 0:
            self.weight_variance_percent = (self.weight_variance_tons / self.net_tons) * 100
        else:
            self.weight_variance_percent = Decimal('0.00')

        self.save()

        # Generate watermarked PDF with official weight stamp
        try:
            stamped_url = watermark_bol_pdf(self)
            if stamped_url:
                self.stamped_pdf_url = stamped_url
                self.save(update_fields=['stamped_pdf_url'])
                logger.info(f"Generated stamped PDF for BOL {self.bol_number}: {stamped_url}")
            else:
                logger.warning(f"Failed to generate stamped PDF for BOL {self.bol_number}")
        except Exception as e:
            logger.error(f"Error generating stamped PDF for BOL {self.bol_number}: {str(e)}", exc_info=True)

class CompanyBranding(TimestampedModel):
    company_name = models.CharField(max_length=200, default="Cincinnati Barge & Rail Terminal, LLC")
    address_line1 = models.CharField(max_length=200, default="1707 Riverside Drive")
    address_line2 = models.CharField(max_length=200, default="Cincinnati, Ohio 45202")
    phone = models.CharField(max_length=20, blank=True)
    website = models.CharField(max_length=200, default="www.BARGE2RAIL.com")
    email = models.EmailField(blank=True)
    logo_text = models.CharField(max_length=10, default="CBR")
    logo_url = models.URLField(blank=True)
    
    class Meta:
        verbose_name_plural = "Company Branding"
    
    def save(self, *args, **kwargs):
        if CompanyBranding.objects.exists() and not self.pk:
            raise ValueError("CompanyBranding is a singleton model")
        super().save(*args, **kwargs)
    
    @classmethod
    def get_instance(cls):
        instance, created = cls.objects.get_or_create(pk=1)
        return instance
    
    def __str__(self):
        return self.company_name


class EmailNotificationSettings(TimestampedModel):
    """
    Singleton settings for BOL email notifications.
    Configure recipients and enable/disable email sending.
    """
    is_enabled = models.BooleanField(
        default=True,
        help_text="Enable/disable BOL notification emails"
    )
    to_emails = models.TextField(
        default="lbryant@primetradeusa.com",
        help_text="Primary recipients (one email per line)"
    )
    cc_emails = models.TextField(
        default="orders@primetradeusa.com\ntraffic@barge2rail.com",
        help_text="CC recipients (one email per line)"
    )

    class Meta:
        verbose_name = "Email Notification Settings"
        verbose_name_plural = "Email Notification Settings"

    def save(self, *args, **kwargs):
        if EmailNotificationSettings.objects.exists() and not self.pk:
            raise ValueError("EmailNotificationSettings is a singleton model")
        super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls):
        instance, created = cls.objects.get_or_create(pk=1)
        return instance

    def get_to_list(self):
        """Return list of TO email addresses"""
        return [e.strip() for e in self.to_emails.strip().split('\n') if e.strip()]

    def get_cc_list(self):
        """Return list of CC email addresses"""
        return [e.strip() for e in self.cc_emails.strip().split('\n') if e.strip()]

    def __str__(self):
        status = "Enabled" if self.is_enabled else "Disabled"
        return f"BOL Email Notifications ({status})"


# =============================
# Lot and Release management (Phase 2)
# =============================
class Lot(TimestampedModel):
    """
    Chemistry lot tracking for pig iron.

    Chemistry describes the lot, not the release or BOL.
    Same lot code = same chemistry (single source of truth).
    Multiple releases can reference same lot without duplicating chemistry.
    """
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True,
        related_name='lots', help_text='Tenant this lot belongs to'
    )
    code = models.CharField(max_length=100, db_index=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    c = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    si = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    s = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    p = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    mn = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ['code']
        unique_together = [['tenant', 'code']]

    def __str__(self):
        return self.code

    def format_chemistry(self):
        """Format chemistry for BOL display. Uses is not None checks for proper null handling."""
        parts = []
        if self.c is not None:
            parts.append(f"C {self.c:.3f}%")
        if self.si is not None:
            parts.append(f"Si {self.si:.3f}%")
        if self.s is not None:
            parts.append(f"S {self.s:.3f}%")
        if self.p is not None:
            parts.append(f"P {self.p:.3f}%")
        if self.mn is not None:
            parts.append(f"Mn {self.mn:.3f}%")
        return " | ".join(parts)

class Release(TimestampedModel):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True,
        related_name='releases', help_text='Tenant this release belongs to'
    )
    STATUS_CHOICES = (
        ("OPEN", "Open"),
        ("COMPLETE", "Complete"),
        ("CANCELLED", "Cancelled"),
    )

    # Note: uniqueness is per-tenant, enforced via unique_together in Meta
    release_number = models.CharField(max_length=20, db_index=True)
    release_date = models.DateField(null=True, blank=True)

    customer_id_text = models.CharField(max_length=200)  # e.g., "ST. MARYS"
    customer_po = models.CharField(max_length=100, blank=True)

    ship_via = models.CharField(max_length=200, blank=True)
    fob = models.CharField(max_length=200, blank=True)

    ship_to_name = models.CharField(max_length=200, blank=True)
    ship_to_street = models.CharField(max_length=200, blank=True)
    ship_to_street2 = models.CharField(max_length=200, blank=True)
    ship_to_city = models.CharField(max_length=100, blank=True)
    ship_to_state = models.CharField(max_length=2, blank=True)
    ship_to_zip = models.CharField(max_length=10, blank=True)

    lot = models.CharField(max_length=100, blank=True)
    material_description = models.CharField(max_length=200, blank=True)

    # Normalized references
    customer_ref = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    ship_to_ref = models.ForeignKey('CustomerShipTo', on_delete=models.SET_NULL, null=True, blank=True)
    carrier_ref = models.ForeignKey(Carrier, on_delete=models.SET_NULL, null=True, blank=True)
    lot_ref = models.ForeignKey('Lot', on_delete=models.SET_NULL, null=True, blank=True)

    quantity_net_tons = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="OPEN")

    special_instructions = models.TextField(
        blank=True,
        help_text="Special warehouse/BOL requirements (e.g., Material #, delivery instructions, tarping, etc.)"
    )

    care_of_co = models.CharField(
        max_length=200,
        blank=True,
        default='PrimeTrade, LLC',
        help_text="Company name for 'c/o' line in BOL Ship From section (for blind shipping)"
    )

    # Chemistry override (when release chemistry differs from existing lot)
    chemistry_override_acknowledged = models.BooleanField(
        default=False,
        help_text="User acknowledged chemistry differs from existing lot"
    )
    chemistry_override_reason = models.TextField(
        blank=True,
        help_text="Reason for chemistry override (optional)"
    )
    chemistry_override_by = models.CharField(
        max_length=200,
        blank=True,
        help_text="User who acknowledged the override"
    )
    chemistry_override_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When override was acknowledged"
    )
    # Override chemistry values (used on BOLs instead of lot chemistry)
    chemistry_override_c = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        help_text="Override Carbon value for this release"
    )
    chemistry_override_si = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        help_text="Override Silicon value for this release"
    )
    chemistry_override_s = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        help_text="Override Sulfur value for this release"
    )
    chemistry_override_p = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        help_text="Override Phosphorus value for this release"
    )
    chemistry_override_mn = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        help_text="Override Manganese value for this release"
    )

    class Meta:
        ordering = ['-created_at']
        # Release number is unique per-tenant, not globally
        unique_together = [['tenant', 'release_number']]

    def __str__(self):
        return f"Release {self.release_number} ({self.customer_id_text})"

    @property
    def total_loads(self):
        return self.loads.count()

    @property
    def loads_shipped(self):
        return self.loads.filter(status='SHIPPED').count()

    @property
    def loads_remaining(self):
        return self.total_loads - self.loads_shipped

    def format_override_chemistry(self):
        """Format override chemistry for BOL display when chemistry differs from lot."""
        parts = []
        if self.chemistry_override_c is not None:
            parts.append(f"C {self.chemistry_override_c:.3f}%")
        if self.chemistry_override_si is not None:
            parts.append(f"Si {self.chemistry_override_si:.3f}%")
        if self.chemistry_override_s is not None:
            parts.append(f"S {self.chemistry_override_s:.3f}%")
        if self.chemistry_override_p is not None:
            parts.append(f"P {self.chemistry_override_p:.3f}%")
        if self.chemistry_override_mn is not None:
            parts.append(f"Mn {self.chemistry_override_mn:.3f}%")
        return " | ".join(parts)

    def get_chemistry_display(self):
        """Get chemistry for BOL - uses override if acknowledged, otherwise lot chemistry."""
        if self.chemistry_override_acknowledged and self.format_override_chemistry():
            return self.format_override_chemistry()
        elif self.lot_ref:
            return self.lot_ref.format_chemistry()
        return ''


class ReleaseLoad(TimestampedModel):
    """
    Individual load within a release (maps to ReleaseLine in spec).

    Status transitions:
    - PENDING → SHIPPED (when BOL created with this release_line)
    - PENDING → CANCELLED (manual)
    - SHIPPED → PENDING (if BOL voided)
    """
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True,
        related_name='release_loads', help_text='Tenant this release load belongs to'
    )
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("SHIPPED", "Shipped"),
        ("CANCELLED", "Cancelled"),
    )

    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name='loads')
    seq = models.IntegerField()  # 1..N (maps to line_number in spec)
    date = models.DateField(null=True, blank=True)
    planned_tons = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="PENDING")
    shipped_at = models.DateTimeField(null=True, blank=True, help_text='Timestamp when BOL created')
    bol = models.ForeignKey(BOL, on_delete=models.SET_NULL, null=True, blank=True, related_name='release_loads_legacy')

    class Meta:
        ordering = ['seq']
        unique_together = [['release', 'seq']]

    def __str__(self):
        return f"{self.release.release_number} load {self.seq}"

    @property
    def line_number(self):
        """Alias for seq to match spec terminology."""
        return self.seq


class AuditLog(TimestampedModel):
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True,
        related_name='audit_logs', help_text='Tenant this audit log belongs to'
    )
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    message = models.TextField(blank=True)
    user_email = models.CharField(max_length=200, blank=True)
    ip = models.CharField(max_length=45, blank=True)
    method = models.CharField(max_length=10, blank=True)
    path = models.CharField(max_length=300, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    extra = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} {self.object_type} {self.object_id} by {self.user_email}";


class RoleRedirectConfig(models.Model):
    """
    Configure landing page redirects by role.

    Allows admins to set different landing pages for different user roles
    without modifying code. For example:
    - viewer/read-only users → Client dashboard with specific product
    - user → Office interface
    - admin → Admin dashboard
    """
    role_name = models.CharField(
        max_length=20,
        unique=True,
        help_text="Role name: viewer, read-only, user, admin"
    )
    landing_page = models.CharField(
        max_length=200,
        help_text="URL to redirect to (e.g., /client.html?productId=9)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Disable to use default redirect"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Role Redirect Configuration"
        verbose_name_plural = "Role Redirect Configurations"
        ordering = ['role_name']

    def __str__(self):
        status = "✓" if self.is_active else "✗"
        return f"{status} {self.role_name} → {self.landing_page}"


class UserCustomerAccess(models.Model):
    """
    Links SSO users to customers they can access in PrimeTrade.

    This is the app-owned user-to-customer association (best practice).
    SSO handles authentication and generic roles, PrimeTrade handles
    domain-specific associations.

    Usage:
        - Client users get filtered views of only their customer's data
        - A user can have access to multiple customers
        - is_primary determines default customer for dashboard

    Admin workflow:
        1. Client user logs in via SSO with 'Client' role
        2. Admin creates UserCustomerAccess linking their email to a Customer
        3. Client portal APIs filter data by this association
    """
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, null=True,
        related_name='user_customer_access',
        help_text='Tenant this access belongs to'
    )
    user_email = models.EmailField(
        db_index=True,
        help_text='Email address from SSO (must match exactly)'
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE,
        related_name='user_access',
        help_text='Customer this user can access'
    )
    is_primary = models.BooleanField(
        default=True,
        help_text='Primary customer shown on dashboard (only one per user)'
    )
    access_level = models.CharField(
        max_length=20,
        default='view',
        choices=[
            ('view', 'View Only'),
            ('edit', 'View & Edit'),
            ('admin', 'Full Access'),
        ],
        help_text='Level of access to customer data'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.EmailField(
        blank=True,
        help_text='Admin who granted this access'
    )
    notes = models.TextField(
        blank=True,
        help_text='Internal notes about this access grant'
    )

    class Meta:
        unique_together = ['user_email', 'customer']
        verbose_name = 'User Customer Access'
        verbose_name_plural = 'User Customer Access'
        ordering = ['user_email', '-is_primary', 'customer__customer']
        indexes = [
            models.Index(fields=['user_email', 'is_primary']),
        ]

    def __str__(self):
        primary = "★" if self.is_primary else ""
        return f"{primary}{self.user_email} → {self.customer.customer} ({self.access_level})"

    def save(self, *args, **kwargs):
        # Ensure only one primary per user
        if self.is_primary:
            UserCustomerAccess.objects.filter(
                user_email=self.user_email,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
