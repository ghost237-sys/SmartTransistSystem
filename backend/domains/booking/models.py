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


class LinkedBooking(models.Model):
    """
    Represents a journey that spans two routes with a transfer.
    Links two separate bookings (one for each leg) into a single journey.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_leg_booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name='linked_as_first_leg',
        help_text='Booking for the first route (Bus 1)'
    )
    second_leg_booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name='linked_as_second_leg',
        help_text='Booking for the second route (Bus 2)'
    )
    linked_route = models.ForeignKey(
        'routing.LinkedRoute', on_delete=models.CASCADE, related_name='linked_bookings',
        null=True, blank=True
    )
    transfer_station = models.ForeignKey(
        'routing.TransferStation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='linked_bookings'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('transfer_complete', 'Transfer Complete'),
            ('missed_connection', 'Missed Connection'),
            ('cancelled', 'Cancelled'),
        ],
        default='active',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['first_leg_booking', 'second_leg_booking']

    def __str__(self):
        return f'Linked: {self.first_leg_booking} → {self.second_leg_booking}'


class MissedConnectionEvent(models.Model):
    """
    Records when a passenger misses their transfer connection.
    Triggered when Bus 1's ETA to transfer station is within buffer time
    of Bus 2's scheduled departure.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    linked_booking = models.ForeignKey(
        LinkedBooking, on_delete=models.CASCADE, related_name='missed_connection_events'
    )
    first_leg_trip = models.ForeignKey(
        'routing.Trip', on_delete=models.CASCADE, related_name='missed_connections_as_first',
        help_text='Bus 1 that was delayed'
    )
    second_leg_trip = models.ForeignKey(
        'routing.Trip', on_delete=models.CASCADE, related_name='missed_connections_as_second',
        help_text='Bus 2 that was missed'
    )
    first_leg_eta_minutes = models.FloatField(
        help_text='ETA of Bus 1 to transfer station when event was triggered'
    )
    second_leg_departure_buffer = models.FloatField(
        help_text='Time difference between Bus 1 ETA and Bus 2 departure'
    )
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Missed connection: {self.linked_booking}'


class TransactionalVoucher(models.Model):
    """
    Temporary credit voucher created when a passenger misses their connection.
    The fare value from the missed leg is credited to this voucher for future use.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    missed_connection_event = models.ForeignKey(
        MissedConnectionEvent, on_delete=models.CASCADE, related_name='vouchers'
    )
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='transactional_vouchers',
        limit_choices_to={'role': 'commuter'}
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    original_booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name='issued_vouchers'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('redeemed', 'Redeemed'),
            ('expired', 'Expired'),
        ],
        default='active',
    )
    expires_at = models.DateTimeField(
        help_text='Voucher expiration date (typically 30 days from issue)'
    )
    redeemed_at = models.DateTimeField(null=True, blank=True)
    redeemed_booking = models.ForeignKey(
        Booking, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='redeemed_vouchers'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Voucher: KES {self.amount} for {self.user.username}'