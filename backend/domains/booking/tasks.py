from celery import shared_task
from django.utils import timezone

from .models import Booking


@shared_task
def expire_stale_bookings():
    """
    Runs periodically (via Celery Beat) to flip any `held` booking whose
    hold window has passed into `expired`, freeing the seat back to the
    pool. This is the safety net for cases where the M-Pesa callback
    never arrives at all (network failure, Safaricom outage, etc.) —
    without this, a held booking would block a seat forever.
    """
    stale = Booking.all_objects.filter(status='held', hold_expires_at__lt=timezone.now())
    count = stale.update(status='expired')
    return f'Expired {count} stale booking(s).'