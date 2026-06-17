import uuid
from django.contrib.gis.db import models as gis_models
from django.db import models


class VehiclePosition(models.Model):
    """
    Historical log of GPS positions reported by drivers, every ~3 seconds.
    The live/current position lives in Redis (fast lookup); this table is
    the durable record used for route replay, analytics, and disputes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.CASCADE, related_name='position_history')
    trip = models.ForeignKey(
        'routing.Trip', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='position_history'
    )
    location = gis_models.PointField(srid=4326)
    speed_kmh = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    recorded_at = models.DateTimeField()

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['vehicle', '-recorded_at']),
        ]

    def __str__(self):
        return f'{self.vehicle.plate_number} @ {self.recorded_at}'