from django.db import models, transaction
from django.core.validators import RegexValidator
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TimestampedModel(models.Model):
    """Base model with common timestamp fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=200, blank=True, default='system')
    
    class Meta:
        abstract = True

class Product(TimestampedModel):
    name = models.CharField(max_length=200, unique=True)
    start_tons = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def shipped_tons(self):
        return self.bol_set.aggregate(
            total=models.Sum('net_tons')
        )['total'] or 0
    
    @property
    def remaining_tons(self):
        return self.start_tons - self.shipped_tons

class Customer(TimestampedModel):
    customer = models.CharField(max_length=200, unique=True)
    address = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    zip = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['customer']
    
    def __str__(self):
        return self.customer
    
    @property
    def full_address(self):
        return f"{self.address}\n{self.city}, {self.state} {self.zip}"

class Carrier(TimestampedModel):
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
    year = models.IntegerField(unique=True)
    sequence = models.IntegerField(default=0)
    
    @classmethod
    def get_next_bol_number(cls):
        current_year = datetime.now().year
        with transaction.atomic():
            counter, created = cls.objects.select_for_update().get_or_create(
                year=current_year,
                defaults={'sequence': 0}
            )
            counter.sequence += 1
            counter.save()
            return f"PRT-{current_year}-{counter.sequence:04d}"

class BOL(TimestampedModel):
    bol_number = models.CharField(max_length=20, unique=True, db_index=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=200)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)
    buyer_name = models.CharField(max_length=200)
    ship_to = models.TextField()
    customer_po = models.CharField(max_length=100, blank=True)
    carrier = models.ForeignKey(Carrier, on_delete=models.CASCADE)
    carrier_name = models.CharField(max_length=200)
    truck = models.ForeignKey(Truck, on_delete=models.CASCADE, null=True, blank=True)
    truck_number = models.CharField(max_length=50)
    trailer_number = models.CharField(max_length=50)
    date = models.CharField(max_length=20)  # Keep as string to match Firebase
    net_tons = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True)
    pdf_url = models.URLField(blank=True)
    created_by_email = models.CharField(max_length=200, default='system@primetrade.com')
    
    class Meta:
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.bol_number:
            self.bol_number = BOLCounter.get_next_bol_number()
        if self.product and not self.product_name:
            self.product_name = self.product.name
        if self.carrier and not self.carrier_name:
            self.carrier_name = self.carrier.carrier_name
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.bol_number
    
    @property
    def total_weight_lbs(self):
        return float(self.net_tons) * 2204.62

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