import uuid
from django.db import models

from domains.tenants.models import TenantScopedModel


class Fleet(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.name} ({self.tenant.name})'


class Vehicle(TenantScopedModel):
    class VehicleType(models.TextChoices):
        BUS = 'bus', 'Bus'
        MATATU = 'matatu', 'Matatu'
        SHUTTLE = 'shuttle', 'Shuttle'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fleet = models.ForeignKey(Fleet, on_delete=models.CASCADE, related_name='vehicles')
    plate_number = models.CharField(max_length=20, unique=True)
    fleet_code = models.CharField(
        max_length=20, unique=True, null=True, blank=True,
        help_text='Short human-readable code printed on windshield, e.g. TH-047'
    )
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices, default=VehicleType.MATATU)
    capacity = models.PositiveIntegerField(help_text='Total passenger seats, excluding driver/conductor.')
    is_active = models.BooleanField(default=True)
    insurance_expiry = models.DateField(null=True, blank=True)
    inspection_expiry = models.DateField(null=True, blank=True)
    assigned_route = models.ForeignKey(
        'routing.Route',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vehicles',
        help_text='Route assigned to this vehicle'
    )
    assigned_driver = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_vehicles',
        limit_choices_to={'role': 'driver'},
        help_text='Default driver assigned to this vehicle (one driver per vehicle)'
    )
    assigned_conductor = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conductor_vehicles',
        limit_choices_to={'role': 'conductor'},
        help_text='Default conductor assigned to this vehicle'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['assigned_driver'],
                condition=models.Q(assigned_driver__isnull=False),
                name='unique_driver_assignment'
            )
        ]

    def __str__(self):
        return f'{self.fleet_code or self.plate_number} ({self.get_vehicle_type_display()})'