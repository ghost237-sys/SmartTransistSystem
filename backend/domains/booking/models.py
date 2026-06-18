import secrets
import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone

from domains.tenants.models import TenantScopedModel


class Booking(TenantScopedModel):
    HOLD_DURATION_MINUTES = 5

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey('routing.Trip', on_delete=models.CASCADE, related_name='bookings')
    commuter = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='bookings',
        limit_choices_to={'role': 'commuter'},
        null=True, blank=True,
        help_text='Null for cash walk-up bookings recorded by a conductor.'
    )
    
    boarding_stop = models.ForeignKey(
        'routing.Stop', on_delete=models.PROTECT, related_name='boardings',
        null=True, blank=True,
    )
    alighting_stop = models.ForeignKey(
        'routing.Stop', on_delete=models.PROTECT, related_name='alightings',
        null=True, blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('held', 'Held'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
            ('expired', 'Expired'),
            ('boarded', 'Boarded'),  # new: distinguishes "paid" from "actually got on"
        ],
        default='held',
    )
    fare_paid = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    qr_code_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    short_code = models.CharField(max_length=6, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    boarded_at = models.DateTimeField(null=True, blank=True)
    hold_expires_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.status == 'held' and self.hold_expires_at is None:
            self.hold_expires_at = timezone.now() + timedelta(minutes=self.HOLD_DURATION_MINUTES)
        super().save(*args, **kwargs)

    def generate_ticket_codes(self):
        """
        Called once a booking is confirmed. Generates a unique QR token
        and a unique 6-digit backup code. Retries on the rare chance of
        a collision against the unique constraint.
        """
        self.qr_code_token = secrets.token_urlsafe(32)

        while True:
            candidate = f'{secrets.randbelow(1000000):06d}'
            if not Booking.all_objects.filter(short_code=candidate).exists():
                self.short_code = candidate
                break

    def __str__(self):
        return f'{self.commuter} - {self.trip} ({self.status})'