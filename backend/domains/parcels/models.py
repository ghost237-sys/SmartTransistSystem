import uuid
from django.db import models

from domains.tenants.models import TenantScopedModel


class Parcel(TenantScopedModel):
    """
    A parcel registered at an origin terminal for transport to a
    destination terminal on a scheduled bus trip.
    """
    class Status(models.TextChoices):
        REGISTERED   = 'registered',   'Registered at origin'
        LOADED       = 'loaded',       'Loaded onto vehicle'
        IN_TRANSIT   = 'in_transit',   'In transit'
        ARRIVED      = 'arrived',      'Arrived at destination terminal'
        COLLECTED    = 'collected',    'Collected by recipient'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tracking_code = models.CharField(max_length=12, unique=True, db_index=True)

    # Sender
    sender_name  = models.CharField(max_length=255)
    sender_phone = models.CharField(max_length=20)

    # Recipient
    recipient_name  = models.CharField(max_length=255)
    recipient_phone = models.CharField(max_length=20)

    # Logistics
    trip = models.ForeignKey(
        'routing.Trip', on_delete=models.PROTECT, related_name='parcels',
        null=True, blank=True,
        help_text='The trip this parcel is travelling on.'
    )
    origin_stop      = models.ForeignKey(
        'routing.Stop', on_delete=models.PROTECT,
        related_name='parcels_origin', null=True, blank=True
    )
    destination_stop = models.ForeignKey(
        'routing.Stop', on_delete=models.PROTECT,
        related_name='parcels_destination', null=True, blank=True
    )

    description   = models.TextField(blank=True)
    weight_kg     = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    declared_value = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    fee           = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    status    = models.CharField(max_length=20, choices=Status.choices, default=Status.REGISTERED)
    qr_token  = models.CharField(max_length=64, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.tracking_code} — {self.sender_name} → {self.recipient_name}'


class ParcelScanEvent(models.Model):
    """
    Immutable log entry for every QR scan in the parcel's chain of
    custody. Never deleted — this is the audit trail.
    """
    class EventType(models.TextChoices):
        LOADED     = 'loaded',     'Loaded onto vehicle'
        OFFLOADED  = 'offloaded',  'Offloaded at destination'
        COLLECTED  = 'collected',  'Collected by recipient'

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcel     = models.ForeignKey(Parcel, on_delete=models.PROTECT, related_name='scan_events')
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    scanned_by = models.ForeignKey(
        'accounts.User', on_delete=models.PROTECT, related_name='parcel_scans'
    )
    vehicle    = models.ForeignKey(
        'fleet.Vehicle', on_delete=models.PROTECT,
        related_name='parcel_scans', null=True, blank=True
    )
    notes      = models.TextField(blank=True)
    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scanned_at']

    def __str__(self):
        return f'{self.parcel.tracking_code} — {self.event_type} @ {self.scanned_at}'