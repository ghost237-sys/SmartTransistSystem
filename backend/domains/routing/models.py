import uuid
from django.contrib.gis.db import models as gis_models
from django.db import models

from domains.tenants.models import TenantScopedModel


class Route(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    path = gis_models.LineStringField(srid=4326)
    distance_km = models.DecimalField(max_digits=6, decimal_places=2)
    estimated_duration_minutes = models.PositiveIntegerField()
    max_pickup_distance_km = models.PositiveIntegerField(
        default=50,
        help_text='Maximum distance in km a bus can be from commuter and still be shown.'
    )
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
    departure_time = models.DateTimeField(
        null=True, blank=True,
        help_text='For on-demand routes this is when the service started, not a fixed schedule.'
    )
    total_seats = models.PositiveIntegerField()
    fare = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='active',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.route.name} — {self.vehicle.fleet_code or self.vehicle.plate_number}'

    @property
    def available_seats(self):
        occupied = self.bookings.filter(status__in=['confirmed', 'boarded']).count()
        return max(self.total_seats - occupied, 0)

    def seats_opening_at(self, stop):
        return self.bookings.filter(status='confirmed', alighting_stop=stop).count()



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


class TransferStation(models.Model):
    """
    A physical location where passengers can transfer between routes.
    This is a stop that serves as a connection point between different routes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    location = gis_models.PointField(srid=4326)
    buffer_minutes = models.PositiveIntegerField(
        default=5,
        help_text='Minimum buffer time in minutes required for a safe transfer'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class LinkedRoute(models.Model):
    """
    Defines a connection between two routes via a transfer station.
    Passengers can book a journey that spans both routes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='linked_as_first')
    second_route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='linked_as_second')
    transfer_station = models.ForeignKey(TransferStation, on_delete=models.CASCADE, related_name='linked_routes')
    first_route_stop = models.ForeignKey(
        Stop, on_delete=models.CASCADE, related_name='linked_as_first_stop',
        help_text='Stop on first route where passenger alights to transfer'
    )
    second_route_stop = models.ForeignKey(
        Stop, on_delete=models.CASCADE, related_name='linked_as_second_stop',
        help_text='Stop on second route where passenger boards after transfer'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['first_route', 'second_route', 'transfer_station']

    def __str__(self):
        return f'{self.first_route.name} → {self.second_route.name} via {self.transfer_station.name}'