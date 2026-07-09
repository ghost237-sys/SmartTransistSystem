from celery import shared_task
from django.utils import timezone

from .models import QueueEntry


@shared_task
def enforce_time_cap(queue_entry_id):
    """
    Check if a queue entry has exceeded its time cap in the loading bay.
    If so, mark it as exceeded.
    """
    try:
        entry = QueueEntry.objects.get(id=queue_entry_id)
    except QueueEntry.DoesNotExist:
        return
    
    # Only enforce if still in loading bay
    if entry.status not in ['called_up', 'loading']:
        return
    
    # Check if time cap exceeded
    if entry.called_up_at:
        time_elapsed = (timezone.now() - entry.called_up_at).total_seconds() / 60
        if time_elapsed > entry.time_cap_minutes:
            entry.time_cap_exceeded = True
            entry.save()
    
    # Could also add notification logic here (SMS, push notification, etc.)
    # For now, just marking the flag is sufficient for the demo
