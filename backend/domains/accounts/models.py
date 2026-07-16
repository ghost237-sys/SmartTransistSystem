# Create your models here.
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

from domains.tenants.models import Tenant


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'super_admin', 'Super Admin'
        FLEET_OWNER = 'fleet_owner', 'Fleet Owner'
        DRIVER = 'driver', 'Driver'
        CONDUCTOR = 'conductor', 'Conductor'
        COMMUTER = 'commuter', 'Commuter'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.COMMUTER)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True,
        help_text='Null for super_admin and commuter roles, which are not tied to a single operator.'
    )
    phone_number = models.CharField(max_length=20, blank=True)
    demo_latitude = models.FloatField(
        null=True, blank=True,
        help_text='Preset demo location latitude for investor presentations.',
    )
    demo_longitude = models.FloatField(
        null=True, blank=True,
        help_text='Preset demo location longitude for investor presentations.',
    )
    demo_location_label = models.CharField(
        max_length=255, blank=True,
        help_text='Human-readable label for the demo location, e.g. "Githurai 45".',
    )

    def __str__(self):
        return f'{self.username} ({self.role})'


class Device(models.Model):
    device_uuid = models.UUIDField(unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    created_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.device_uuid} -> {self.user.username}'


class DeviceVerificationToken(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    phone_number = models.CharField(max_length=20)
    device_uuid = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.phone_number} ({self.device_uuid}) - Used: {self.is_used}'