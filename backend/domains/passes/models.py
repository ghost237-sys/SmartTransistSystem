import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from domains.tenants.models import TenantScopedModel


class PassTier(models.Model):
    """Defines subscription tiers with pricing and rules."""
    
    class TierType(models.TextChoices):
        WEEKLY = 'weekly', 'Weekly Bundle'
        MONTHLY = 'monthly', 'Monthly Season Pass'
        POSTPAID = 'postpaid', 'Post-Paid Line'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='pass_tiers',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=100)
    tier_type = models.CharField(max_length=20, choices=TierType.choices)
    trip_allowance = models.PositiveIntegerField(
        help_text='Number of trips included in the pass'
    )
    discount_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Discount percentage off regular fare'
    )
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text='Price for the pass (if prepaid)'
    )
    duration_days = models.PositiveIntegerField(
        help_text='Validity period in days'
    )
    min_credit_score = models.IntegerField(
        blank=True, 
        null=True,
        help_text='Minimum credit score required for this tier'
    )
    max_credit_limit = models.DecimalField(
        blank=True, 
        null=True,
        max_digits=10, 
        decimal_places=2,
        help_text='Maximum credit limit for post-paid tier'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-discount_percent']
    
    def __str__(self):
        return f'{self.name} ({self.tier_type})'


class CommuterPass(TenantScopedModel):
    """Active subscription instance for a commuter."""
    
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        EXPIRED = 'expired', 'Expired'
        SUSPENDED = 'suspended', 'Suspended'
        CANCELLED = 'cancelled', 'Cancelled'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='commuter_passes',
        limit_choices_to={'role': 'commuter'}
    )
    tier = models.ForeignKey(
        PassTier,
        on_delete=models.PROTECT,
        related_name='passes'
    )
    trips_remaining = models.PositiveIntegerField(default=0)
    trips_used = models.PositiveIntegerField(default=0)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    current_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Current outstanding balance for post-paid'
    )
    credit_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Credit limit for post-paid tier'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    auto_renew = models.BooleanField(default=False)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'tenant', 'status']
    
    def __str__(self):
        return f'{self.user.username} - {self.tier.name} ({self.status})'
    
    def can_use_pass(self):
        """Check if pass can be used for a trip."""
        if self.status != self.Status.ACTIVE:
            return False
        if self.end_date < timezone.now():
            return False
        if self.tier.tier_type in [PassTier.TierType.WEEKLY, PassTier.TierType.MONTHLY]:
            return self.trips_remaining > 0
        elif self.tier.tier_type == PassTier.TierType.POSTPAID:
            return self.current_balance < self.credit_limit
        return False
    
    def use_trip(self, fare_amount):
        """Deduct trip or add charge based on tier type."""
        from django.utils import timezone
        
        if self.tier.tier_type in [PassTier.TierType.WEEKLY, PassTier.TierType.MONTHLY]:
            if self.trips_remaining > 0:
                self.trips_remaining -= 1
                self.trips_used += 1
        elif self.tier.tier_type == PassTier.TierType.POSTPAID:
            discounted_fare = fare_amount * (Decimal('1') - self.tier.discount_percent / Decimal('100'))
            self.current_balance += discounted_fare
        
        self.last_used_at = timezone.now()
        self.save()


class CreditScore(models.Model):
    """Credit score for post-paid eligibility."""
    
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='credit_score',
        limit_choices_to={'role': 'commuter'}
    )
    score = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Credit score (0-100)'
    )
    total_trips = models.PositiveIntegerField(default=0)
    on_time_payments = models.PositiveIntegerField(default=0)
    missed_payments = models.PositiveIntegerField(default=0)
    last_calculated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Credit Score'
        verbose_name_plural = 'Credit Scores'
    
    def __str__(self):
        return f'{self.user.username}: {self.score}'
    
    def calculate_score(self):
        """Recalculate credit score based on payment history."""
        if self.total_trips == 0:
            return 50
        
        payment_ratio = self.on_time_payments / max(self.total_trips, 1)
        base_score = int(payment_ratio * 100)
        
        # Bonus for consistent usage
        if self.total_trips > 20:
            base_score = min(100, base_score + 5)
        
        self.score = base_score
        self.save()
        return self.score


class CreditTransaction(models.Model):
    """Transaction log for post-paid accounts."""
    
    class TransactionType(models.TextChoices):
        CHARGE = 'charge', 'Charge'
        PAYMENT = 'payment', 'Payment'
        ADJUSTMENT = 'adjustment', 'Adjustment'
        SETTLEMENT = 'settlement', 'Weekly Settlement'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pass_instance = models.ForeignKey(
        CommuterPass,
        on_delete=models.CASCADE,
        related_name='credit_transactions'
    )
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_before = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.transaction_type}: {self.amount}'


class PassUsage(models.Model):
    """Record of pass usage for analytics."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pass_instance = models.ForeignKey(
        CommuterPass,
        on_delete=models.CASCADE,
        related_name='usage_records'
    )
    booking = models.ForeignKey(
        'booking.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pass_usage'
    )
    original_fare = models.DecimalField(max_digits=8, decimal_places=2)
    discount_applied = models.DecimalField(max_digits=8, decimal_places=2)
    final_amount = models.DecimalField(max_digits=8, decimal_places=2)
    route_name = models.CharField(max_length=255, blank=True)
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-used_at']
    
    def __str__(self):
        return f'{self.pass_instance} - {self.final_amount}'


class WeeklySettlement(models.Model):
    """Weekly settlement record for post-paid accounts."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pass_instance = models.ForeignKey(
        CommuterPass,
        on_delete=models.CASCADE,
        related_name='weekly_settlements'
    )
    week_start = models.DateField()
    week_end = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    mpesa_receipt = models.CharField(max_length=100, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-week_start']
        unique_together = ['pass_instance', 'week_start']
    
    def __str__(self):
        return f'{self.week_start} - {self.total_amount} ({self.status})'
