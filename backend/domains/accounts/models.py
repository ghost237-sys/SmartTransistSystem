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

    def __str__(self):
        return f'{self.username} ({self.role})'