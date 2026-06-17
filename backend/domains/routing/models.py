import uuid
from django.contrib.gis.db import models as gis_models
from django.db import models

from domains.tenants.models import Tenant


class Route(models.Model):
    """
    A defined path between two points, e.g. Nairobi -> Mombasa.
    The actual path geometry is stored as a LineString for map display
    and future distance/ETA calculations.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='routes')
    name = models.CharField(max_length=255, help_text='e.g. "Nairobi - Mombasa"')
    path = gis_models.LineStringField(srid=4326, help_text='Ordered route geometry, for map rendering.')
    distance_km = models.DecimalField(max_digits=6, decimal_places=2)
    estimated_duration_minutes = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Stop(models.Model):
    """
    A specific boarding/alighting point along a route.
    Ordered via sequence so we know stop 1, 2, 3 along the path.
    """
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


class Trip(models.Model):
    """
    A specific scheduled departure of a vehicle along a route.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='trips')
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