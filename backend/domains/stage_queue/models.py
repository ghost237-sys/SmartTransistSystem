import uuid
from django.db import models
from domains.tenants.models import TenantScopedModel


class Stage(TenantScopedModel):
    """
    A physical bus stage/terminal — e.g. Thika Town Stage, Kencom CBD.
    One stage per route terminus. Tracks loading bay capacity.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    route = models.ForeignKey(
        'routing.Route', on_delete=models.PROTECT,
        related_name='stages', null=True, blank=True
    )
    loading_bay_capacity = models.PositiveIntegerField(
        default=2,
        help_text='Max buses allowed in the loading bay simultaneously.'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def loading_bay_count(self):
        return self.queue_entries.filter(status='loading').count()

    @property
    def loading_bay_available(self):
        return self.loading_bay_count < self.loading_bay_capacity

    @property
    def next_in_queue(self):
        return self.queue_entries.filter(
            status='holding', confirmed=True
        ).order_by('confirmed_at').first()


class QueueEntry(TenantScopedModel):
    """
    One bus's slot in the queue at a specific stage.
    Tracks the full lifecycle from arrival to departure.
    """
    class Status(models.TextChoices):
        HOLDING   = 'holding',   'In holding zone'
        CALLED_UP = 'called_up', 'Called to loading bay'
        LOADING   = 'loading',   'Loading passengers'
        DEPARTED  = 'departed',  'Departed'
        SKIPPED   = 'skipped',   'Skipped by stage manager'
        FULL      = 'full',      'Vehicle full, ready to depart'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name='queue_entries')
    vehicle = models.ForeignKey(
        'fleet.Vehicle', on_delete=models.PROTECT, related_name='queue_entries'
    )
    driver = models.ForeignKey(
        'accounts.User', on_delete=models.PROTECT,
        related_name='queue_entries', limit_choices_to={'role': 'driver'}
    )
    conductor = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conductor_queue_entries', limit_choices_to={'role': 'conductor'}
    )
    route = models.ForeignKey(
        'routing.Route', on_delete=models.PROTECT,
        related_name='queue_entries', null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.HOLDING
    )
    confirmed = models.BooleanField(
        default=False,
        help_text='Stage manager has physically verified this bus has arrived.'
    )
    position = models.PositiveIntegerField(
        default=0,
        help_text='Manual position in queue for stage manager reordering.'
    )
    time_cap_minutes = models.PositiveIntegerField(
        default=15,
        help_text='How long this bus may stay in the loading bay before being flagged.'
    )
    arrived_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    called_up_at = models.DateTimeField(null=True, blank=True)
    loading_started_at = models.DateTimeField(null=True, blank=True)
    departed_at = models.DateTimeField(null=True, blank=True)
    time_cap_exceeded = models.BooleanField(default=False)
    trip = models.ForeignKey(
        'routing.Trip', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='queue_entry'
    )

    class Meta:
        ordering = ['position', 'arrived_at']

    def __str__(self):
        vehicle_id = self.vehicle.fleet_code or self.vehicle.plate_number
        return f'{vehicle_id} @ {self.stage.name} ({self.status})'

    @property
    def queue_position(self):
        if self.status not in ['holding', 'called_up']:
            return None
        if self.position > 0:
            return self.position
        if self.status != 'holding' or not self.confirmed_at:
            return None
        ahead = QueueEntry.all_objects.filter(
            stage=self.stage,
            status='holding',
            confirmed=True,
            confirmed_at__lt=self.confirmed_at
        ).count()
        return ahead + 1