import uuid
from django.db import models

from domains.tenants.models import Tenant


class Fleet(models.Model):
    """
    A collection of vehicles under one tenant. Most tenants will have
    exactly one fleet, but the model allows an operator to logically
    split vehicles (e.g. by region or vehicle class) if needed.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='fleets')
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} ({self.tenant.name})'


class Vehicle(models.Model):
    class VehicleType(models.TextChoices):
        BUS = 'bus', 'Bus'
        MATATU = 'matatu', 'Matatu'
        SHUTTLE = 'shuttle', 'Shuttle'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='vehicles')
    fleet = models.ForeignKey(Fleet, on_delete=models.CASCADE, related_name='vehicles')
    plate_number = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices, default=VehicleType.MATATU)
    capacity = models.PositiveIntegerField(help_text='Total passenger seats, excluding driver/conductor.')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.plate_number} ({self.get_vehicle_type_display()})'