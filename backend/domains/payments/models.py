import uuid
from django.db import models

from domains.tenants.models import TenantScopedModel


class Payment(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey('booking.Booking', on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    phone_number = models.CharField(max_length=20)
    mpesa_receipt_number = models.CharField(max_length=50, null=True, blank=True, unique=True)
    checkout_request_id = models.CharField(max_length=100, unique=True, help_text='Daraja idempotency key.')
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('success', 'Success'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending',
    )
    raw_callback = models.JSONField(null=True, blank=True, help_text='Full Daraja webhook payload, for debugging.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.amount} - {self.status} ({self.checkout_request_id})'