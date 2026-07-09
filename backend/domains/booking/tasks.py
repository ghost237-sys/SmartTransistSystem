from celery import shared_task
from django.utils import timezone
from django.db import transaction

from .models import Booking, LinkedBooking, MissedConnectionEvent, TransactionalVoucher
from domains.routing.eta import estimate_arrival
from domains.tracking.redis_client import get_vehicle_position


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


@shared_task
def monitor_linked_connections():
    """
    Proactive Buffer Monitoring: Continuously calculates the ETA of Bus 1
    relative to the transfer station. If Bus 1's ETA falls within the buffer
    time of Bus 2's scheduled departure, a Missed Connection Event is triggered.
    
    This task runs every minute to monitor all active linked bookings.
    """
    from domains.routing.models import Stop
    
    # Get all active linked bookings
    active_linked_bookings = LinkedBooking.objects.filter(
        status='active'
    ).select_related(
        'first_leg_booking__trip',
        'second_leg_booking__trip',
        'transfer_station'
    )
    
    events_triggered = 0
    
    for linked_booking in active_linked_bookings:
        first_booking = linked_booking.first_leg_booking
        second_booking = linked_booking.second_leg_booking
        transfer_station = linked_booking.transfer_station
        
        # Skip if either booking is not confirmed
        if first_booking.status != 'confirmed' or second_booking.status != 'confirmed':
            continue
        
        # Skip if first leg is already completed
        if first_booking.status == 'boarded':
            continue
        
        # Get the transfer stop for the first route
        first_trip = first_booking.trip
        transfer_stop = None
        
        if linked_booking.linked_route:
            transfer_stop = linked_booking.linked_route.first_route_stop
        else:
            # Fallback: find the stop closest to transfer station
            stops = first_trip.route.stops.all()
            if stops.exists():
                # Simple distance-based selection
                min_distance = float('inf')
                for stop in stops:
                    if stop.location and transfer_station.location:
                        # Calculate distance (simplified)
                        distance = stop.location.distance(transfer_station.location)
                        if distance < min_distance:
                            min_distance = distance
                            transfer_stop = stop
        
        if not transfer_stop:
            continue
        
        # Calculate ETA of Bus 1 to transfer station
        eta_data = estimate_arrival(first_trip, transfer_stop)
        
        if not eta_data:
            continue
        
        bus1_eta_minutes = eta_data['eta_minutes']
        
        # Get Bus 2's scheduled departure time
        second_trip = second_booking.trip
        if not second_trip.departure_time:
            continue
        
        # Calculate time until Bus 2 departure
        time_until_departure = (second_trip.departure_time - timezone.now()).total_seconds() / 60
        
        if time_until_departure <= 0:
            # Bus 2 has already departed or is departing now
            continue
        
        # Check if Bus 1's ETA is within buffer time of Bus 2's departure
        buffer_minutes = transfer_station.buffer_minutes if transfer_station else 5
        time_difference = time_until_departure - bus1_eta_minutes
        
        # If Bus 1 will arrive after Bus 2 departs, or within the buffer window
        if time_difference < buffer_minutes:
            # Trigger missed connection event
            with transaction.atomic():
                # Check if event already exists to avoid duplicates
                existing_event = MissedConnectionEvent.objects.filter(
                    linked_booking=linked_booking,
                    resolved=False
                ).first()
                
                if existing_event:
                    continue
                
                # Create missed connection event
                missed_event = MissedConnectionEvent.objects.create(
                    linked_booking=linked_booking,
                    first_leg_trip=first_trip,
                    second_leg_trip=second_trip,
                    first_leg_eta_minutes=bus1_eta_minutes,
                    second_leg_departure_buffer=time_difference,
                )
                
                # Update linked booking status
                linked_booking.status = 'missed_connection'
                linked_booking.save()
                
                # Release the seat on Bus 2 (Automated Inventory Protection)
                release_linked_booking_seat(second_booking)
                
                # Create transactional voucher (Instant Credit Conversion)
                create_transactional_voucher(missed_event, second_booking)
                
                events_triggered += 1
    
    return f'Monitored {active_linked_bookings.count()} linked bookings, triggered {events_triggered} missed connection events.'


def release_linked_booking_seat(booking):
    """
    Automated Inventory Protection: Immediately releases the user's reserved
    seat on Bus 2 back into the public pool so that other travelers can book it.
    """
    if booking.status == 'confirmed':
        booking.status = 'cancelled'
        booking.save()
        # The seat is now available again via the available_seats property


def create_transactional_voucher(missed_event, booking):
    """
    Instant Credit Conversion: The fare value for Leg 2 is automatically
    credited to a temporary transactional voucher attached to the user's
    active session.
    """
    from datetime import timedelta
    
    voucher = TransactionalVoucher.objects.create(
        missed_connection_event=missed_event,
        user=booking.commuter,
        amount=booking.fare_paid or booking.trip.fare,
        original_booking=booking,
        expires_at=timezone.now() + timedelta(days=30),
    )
    return voucher