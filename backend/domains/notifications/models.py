import uuid
from django.db import models


class Notification(models.Model):
    """
    Audit log of every SMS/push notification sent by the system,
    dispatched via Celery workers.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='notifications')
    channel = models.CharField(max_length=10, choices=[('sms', 'SMS'), ('push', 'Push')])
    event_type = models.CharField(max_length=50, help_text='e.g. booking_confirmed, bus_approaching')
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('queued', 'Queued'),
            ('sent', 'Sent'),
            ('failed', 'Failed'),
        ],
        default='queued',
    )
    retry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.event_type} -> {self.user} ({self.status})'