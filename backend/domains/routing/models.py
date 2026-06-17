import uuid
from django.contrib.gis.db import models as gis_models
from django.db import models

from domains.tenants.models import TenantScopedModel


class Route(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text='e.g. "Nairobi - Mombasa"')
    path = gis_models.LineStringField(srid=4326, help_text='Ordered route geometry, for map rendering.')
    distance_km = models.DecimalField(max_digits=6, decimal_places=2)
    estimated_duration_minutes = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Stop(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='stops')
    name = models.CharField(max_length=255)
    location = gis_models.PointField(srid=4326)
    sequence = models.PositiveIntegerField(help_text='Order of this stop along the route, starting at 0.')

    class Meta:
        ordering = ['route', 'sequence']
        unique_together = ['route', 'sequence']

    def __str__(self):
        return f'{self.name} (stop {self.sequence} on {self.route.name})'


class Trip(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='trips')
    vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.CASCADE, related_name='trips')
    driver = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='trips_as_driver', limit_choices_to={'role': 'driver'}
    )
    conductor = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='trips_as_conductor', limit_choices_to={'role': 'conductor'}
    )
    departure_time = models.DateTimeField()
    total_seats = models.PositiveIntegerField(help_text='Snapshot of vehicle capacity at trip creation time.')
    fare = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=[
            ('scheduled', 'Scheduled'),
            ('departed', 'Departed'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='scheduled',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['departure_time']

    def __str__(self):
        return f'{self.route.name} @ {self.departure_time}'

    @property
    def available_seats(self):
        booked = self.bookings.filter(status='confirmed').count()
        return max(self.total_seats - booked, 0)



class Seat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='seats')
    seat_number = models.PositiveIntegerField()
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ['trip', 'seat_number']
        unique_together = ['trip', 'seat_number']

    def __str__(self):
        return f'Seat {self.seat_number} on {self.trip}'

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if is_new and not self.total_seats:
            self.total_seats = self.vehicle.capacity
        super().save(*args, **kwargs)
        if is_new:
            Seat.objects.bulk_create([
                Seat(trip=self, seat_number=i)
                for i in range(1, self.total_seats + 1)
            ])