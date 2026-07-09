from celery import shared_task
from django.utils import timezone

from .models import Notification
from .sms import send_sms


def _send_and_log(user, event_type, message):
    """
    Shared helper: creates a Notification record, attempts SMS send,
    updates status to sent or failed, and records retry count.
    Called from each task below rather than duplicating this logic.
    """
    notification = Notification.objects.create(
        user=user,
        channel='sms',
        event_type=event_type,
        message=message,
        status='queued',
    )

    phone = getattr(user, 'phone_number', None)
    if not phone:
        notification.status = 'failed'
        notification.save()
        return

    # Normalize to international format if needed
    if phone.startswith('0'):
        phone = '+254' + phone[1:]
    elif phone.startswith('254'):
        phone = '+' + phone
    elif not phone.startswith('+'):
        phone = '+254' + phone

    try:
        send_sms(phone, message)
        notification.status = 'sent'
        notification.sent_at = timezone.now()
    except Exception as e:
        notification.status = 'failed'
        notification.retry_count += 1

    notification.save()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_confirmed_sms(self, booking_id):
    try:
        from domains.booking.models import Booking
        booking = Booking.all_objects.get(id=booking_id)
        if not booking.commuter:
            return
        message = (
            f"Booking confirmed! Your seat on {booking.trip.route.name} "
            f"is confirmed. Short code: {booking.short_code}. Show this to the conductor."
        )
        _send_and_log(booking.commuter, 'booking_confirmed', message)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_trip_departed_without_boarding_sms(self, booking_id):
    try:
        from domains.booking.models import Booking
        booking = Booking.all_objects.get(id=booking_id)
        if not booking.commuter:
            return
        message = (
            f"Your bus on {booking.trip.route.name} has departed. "
            f"You were not recorded as having boarded. "
            f"Please contact support if you believe this is an error."
        )
        _send_and_log(booking.commuter, 'trip_departed_without_boarding', message)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_daily_revenue_summary_sms(self, tenant_id):
    try:
        from datetime import date
        from domains.tenants.models import Tenant
        from domains.fleet.analytics import get_fleet_analytics
        from domains.accounts.models import User

        tenant = Tenant.objects.get(id=tenant_id)
        today = date.today()
        data = get_fleet_analytics(tenant, today, today)

        fleet_owners = User.objects.filter(tenant=tenant, role='fleet_owner')
        message = (
            f"Daily summary for {today}: "
            f"{data['total_trips']} trips, "
            f"{data['total_passengers']} passengers, "
            f"KES {data['total_revenue']} revenue."
        )
        for owner in fleet_owners:
            _send_and_log(owner, 'daily_revenue_summary', message)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_document_expiry_warning_sms(self, vehicle_id):
    try:
        from datetime import date, timedelta
        from domains.fleet.models import Vehicle
        from domains.accounts.models import User

        vehicle = Vehicle.all_objects.get(id=vehicle_id)
        today = date.today()
        threshold = today + timedelta(days=30)
        alerts = []

        if vehicle.insurance_expiry and vehicle.insurance_expiry <= threshold:
            alerts.append(f"insurance expires {vehicle.insurance_expiry}")
        if vehicle.inspection_expiry and vehicle.inspection_expiry <= threshold:
            alerts.append(f"inspection expires {vehicle.inspection_expiry}")

        if not alerts:
            return

        message = f"Alert: {vehicle.plate_number} - {', '.join(alerts)}. Please renew to avoid grounding."
        fleet_owners = User.objects.filter(tenant=vehicle.tenant, role='fleet_owner')
        for owner in fleet_owners:
            _send_and_log(owner, 'document_expiry_warning', message)
    except Exception as exc:
        raise self.retry(exc=exc)