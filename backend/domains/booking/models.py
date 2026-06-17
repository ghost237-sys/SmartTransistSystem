import uuid
from django.db import models


class Booking(models.Model):
    """
    A commuter's reservation for one trip. No individual seat numbers are
    tracked — Trip.available_seats is computed by counting confirmed
    bookings against Trip.total_seats.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='bookings')
    trip = models.ForeignKey('routing.Trip', on_delete=models.CASCADE, related_name='bookings')
    commuter = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='bookings',
        limit_choices_to={'role': 'commuter'}
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('held', 'Held'),           # payment in progress, 5-minute timeout window
            ('confirmed', 'Confirmed'), # payment succeeded
            ('cancelled', 'Cancelled'),
            ('expired', 'Expired'),     # hold timed out, never paid
        ],
        default='held',
    )
    fare_paid = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    qr_code_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.commuter} - {self.trip} ({self.status})'