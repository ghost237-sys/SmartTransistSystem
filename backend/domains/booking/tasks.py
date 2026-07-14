from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging

from .models import Booking, LinkedBooking, MissedConnectionEvent, TransactionalVoucher
from domains.routing.eta import estimate_arrival
from domains.tracking.redis_client import get_vehicle_position

logger = logging.getLogger(__name__)


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


@shared_task
def monitor_transfer_bay():
    """
    Transfer Bay Monitoring: Watches commuters' ETA to transfer stops and
    triggers the second leg seat lock at the right moment for linked trips.
    
    For linked bookings (Mode 3), this task:
    1. Monitors first leg bookings with status 'pending_transfer'
    2. Calculates ETA to transfer station using GPS
    3. When ETA is within trigger window, books the second leg
    4. Updates booking status from 'pending_transfer' to 'confirmed'
    
    This task runs every minute to monitor all pending transfer bookings.
    """
    from domains.routing.models import Stop
    
    # Get all bookings waiting in the transfer bay
    pending_transfers = Booking.objects.filter(
        status='pending_transfer'
    ).select_related(
        'trip__vehicle',
        'trip__route',
        'boarding_stop',
        'alighting_stop'
    )
    
    bookings_processed = 0
    
    for booking in pending_transfers:
        # Get the linked booking record
        linked_booking = LinkedBooking.objects.filter(
            first_leg_booking=booking
        ).select_related(
            'second_leg_booking__trip',
            'transfer_station'
        ).first()
        
        if not linked_booking:
            continue
        
        second_booking = linked_booking.second_leg_booking
        transfer_station = linked_booking.transfer_station
        
        # Skip if second leg is already confirmed
        if second_booking.status == 'confirmed':
            booking.status = 'confirmed'
            booking.save()
            continue
        
        # Get the transfer stop for the first route
        first_trip = booking.trip
        transfer_stop = booking.alighting_stop  # For linked trips, alighting stop is transfer point
        
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
            # Bus 2 has already departed - this is a missed connection
            continue
        
        # Trigger window: When Bus 1 ETA is within 15 minutes of transfer station
        # This gives enough time to secure the seat on Bus 2
        trigger_window_minutes = 15
        
        if bus1_eta_minutes <= trigger_window_minutes:
            # Time to book the second leg
            with transaction.atomic():
                # Check if second trip still has seats
                if second_trip.available_seats <= 0:
                    # No seats available - handle as missed connection
                    linked_booking.status = 'missed_connection'
                    linked_booking.save()
                    booking.status = 'missed_delay'
                    booking.save()
                    
                    # Create voucher for second leg
                    missed_event = MissedConnectionEvent.objects.create(
                        linked_booking=linked_booking,
                        first_leg_trip=first_trip,
                        second_leg_trip=second_trip,
                        first_leg_eta_minutes=bus1_eta_minutes,
                        second_leg_departure_buffer=time_until_departure,
                    )
                    create_transactional_voucher(missed_event, second_booking)
                    continue
                
                # Book the second leg
                second_booking.status = 'confirmed'
                second_booking.confirmed_at = timezone.now()
                second_booking.generate_ticket_codes()
                second_booking.save()
                
                # Update first leg status
                booking.status = 'confirmed'
                booking.save()
                
                # Update linked booking status
                linked_booking.status = 'transfer_complete'
                linked_booking.save()
                
                bookings_processed += 1
    
    return f'Monitored {pending_transfers.count()} pending transfers, processed {bookings_processed} second leg bookings.'


@shared_task
def monitor_transfer_proximity():
    """
    Transfer Proximity Monitoring: Monitors LINK_LEG_1 bookings and triggers
    automatic seat lock on LINK_LEG_2 when Bus A approaches the transfer station.
    
    For new multi-mode linked trips using booking_type and linked_booking fields:
    1. Queries all LINK_LEG_1 bookings with status 'confirmed' or 'boarded' (active/in-transit)
    2. Fetches live GPS coordinates of Bus A relative to pending_transfer_stop
    3. Calculates distance/ETA to transfer station
    4. If distance < transfer_trigger_km or ETA threshold reached:
       - Fetches the linked LINK_LEG_2 booking
       - Attempts to lock/confirm seat on Bus B
       - If successful: transitions Leg 2 to CONFIRMED, broadcasts WebSocket update
       - If Bus B full: logs failure, fires WebSocket alert for manual rerouting
    
    This task runs every 30 seconds via Celery Beat.
    """
    from domains.tracking.redis_client import publish_position_update
    from django.contrib.gis.geos import Point
    from django.contrib.gis.measure import D
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Get all active LINK_LEG_1 bookings (confirmed or boarded - in transit)
    active_leg1_bookings = Booking.objects.filter(
        booking_type=Booking.BookingType.LINK_LEG_1,
        status__in=['confirmed', 'boarded']
    ).select_related(
        'trip__vehicle',
        'trip__route',
        'linked_booking__trip__vehicle',
        'linked_booking__trip__route',
        'pending_transfer_stop'
    )
    
    bookings_processed = 0
    failures_handled = 0
    
    for leg1_booking in active_leg1_bookings:
        # Get the linked Leg 2 booking
        leg2_booking = leg1_booking.linked_booking
        
        if not leg2_booking or leg2_booking.booking_type != Booking.BookingType.LINK_LEG_2:
            continue
        
        # Skip if Leg 2 is already confirmed
        if leg2_booking.status == 'confirmed':
            continue
        
        # Get transfer station
        transfer_station = leg2_booking.pending_transfer_stop
        if not transfer_station:
            logger.warning(f"Leg 1 booking {leg1_booking.id} has no pending_transfer_stop")
            continue
        
        # Get Bus A (Leg 1) live position
        leg1_trip = leg1_booking.trip
        position = get_vehicle_position(str(leg1_trip.vehicle_id))
        
        if not position:
            logger.warning(f"No GPS data for vehicle {leg1_trip.vehicle_id} on trip {leg1_trip.id}")
            continue
        
        # Calculate distance from Bus A to transfer station
        vehicle_point = Point(position['longitude'], position['latitude'], srid=4326)
        
        # Transform to metric SRID for accurate distance
        distance_meters = vehicle_point.transform(3857, clone=True).distance(
            transfer_station.location.transform(3857, clone=True)
        )
        distance_km = distance_meters / 1000
        
        # Get trigger threshold from booking (fallback to default 2.0 km)
        trigger_km = leg2_booking.transfer_trigger_km
        
        # Check if within trigger distance
        if distance_km <= trigger_km:
            # Time to lock seat on Bus B (Leg 2)
            with transaction.atomic():
                leg2_trip = leg2_booking.trip
                
                # Check if Bus B still has available seats
                if leg2_trip.available_seats <= 0:
                    # Bus B is full - handle edge case
                    logger.error(
                        f"Bus B (trip {leg2_trip.id}) full when triggering transfer for "
                        f"leg1_booking {leg1_booking.id}. Manual rerouting required."
                    )
                    
                    # Update Leg 2 status to indicate failure
                    leg2_booking.status = 'missed_delay'
                    leg2_booking.save()
                    
                    # Fire WebSocket alert to user
                    _broadcast_transfer_alert(
                        leg1_booking.commuter.id,
                        leg1_booking.id,
                        leg2_booking.id,
                        'no_seats_available',
                        f'Transfer failed: Bus B is full. Please contact support for rerouting.'
                    )
                    
                    failures_handled += 1
                    continue
                
                # Lock seat on Bus B - confirm Leg 2 booking
                leg2_booking.status = 'confirmed'
                leg2_booking.fare_paid = leg2_trip.fare
                leg2_booking.confirmed_at = timezone.now()
                leg2_booking.generate_ticket_codes()
                leg2_booking.save()
                
                # Broadcast real-time update to commuter via WebSocket
                _broadcast_transfer_success(
                    leg1_booking.commuter.id,
                    leg1_booking.id,
                    leg2_booking.id,
                    leg2_booking.short_code,
                    leg2_booking.qr_code_token
                )
                
                bookings_processed += 1
                logger.info(
                    f"Successfully locked seat on Bus B (trip {leg2_trip.id}) for "
                    f"leg2_booking {leg2_booking.id}. Distance to transfer: {distance_km:.2f}km"
                )
    
    return (
        f'Monitored {active_leg1_bookings.count()} active LINK_LEG_1 bookings, '
        f'processed {bookings_processed} Leg 2 seat locks, '
        f'handled {failures_handled} failures.'
    )


def _broadcast_transfer_success(user_id, leg1_booking_id, leg2_booking_id, short_code, qr_token):
    """
    Broadcasts a successful transfer seat lock to the commuter via WebSocket.
    """
    from channels.layers import get_channel_layer
    import asyncio
    import json
    
    channel_layer = get_channel_layer()
    
    async def send_notification():
        await channel_layer.group_send(
            f'user_{user_id}',
            {
                'type': 'transfer.success',
                'leg1_booking_id': str(leg1_booking_id),
                'leg2_booking_id': str(leg2_booking_id),
                'short_code': short_code,
                'qr_token': qr_token,
                'message': 'Your transfer seat has been confirmed. Boarding pass ready.',
                'timestamp': timezone.now().isoformat(),
            }
        )
    
    # Run async function in sync context
    try:
        asyncio.run(send_notification())
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to broadcast transfer success: {e}")


def _broadcast_transfer_alert(user_id, leg1_booking_id, leg2_booking_id, alert_type, message):
    """
    Broadcasts a transfer failure alert to the commuter via WebSocket.
    """
    from channels.layers import get_channel_layer
    import asyncio
    
    channel_layer = get_channel_layer()
    
    async def send_alert():
        await channel_layer.group_send(
            f'user_{user_id}',
            {
                'type': 'transfer.alert',
                'leg1_booking_id': str(leg1_booking_id),
                'leg2_booking_id': str(leg2_booking_id),
                'alert_type': alert_type,
                'message': message,
                'timestamp': timezone.now().isoformat(),
            }
        )
    
    # Run async function in sync context
    try:
        asyncio.run(send_alert())
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to broadcast transfer alert: {e}")


@shared_task
def handle_bus_cancellation(cancelled_trip_id, reason='bus_cancelled'):
    """
    Celery task for handling automatic reassignment of bookings when buses are cancelled.
    
    This task is triggered when an operator cancels a scheduled bus run. It:
    1. Queries all active CONFIRMED bookings associated with that bus
    2. Focuses on RETURN_INWARD types and standard single trips
    3. For each affected booking, searches for the next available scheduled bus on the same route
    4. Executes reassignment with atomic locks to protect seat counts
    5. Logs reassignment events in BookingReassignment for audit tracking
    6. Triggers WebSocket broadcasts to affected commuters
    7. Flags bookings as PENDING_MANUAL_REROUTE if no seats are available
    8. Dispatches critical alerts to admin dashboard for manual intervention
    
    Args:
        cancelled_trip_id: UUID of the cancelled trip
        reason: Reason for cancellation (default: 'bus_cancelled')
    
    Returns:
        dict with summary of reassignment results
    """
    from .services import BusCancellationService
    
    logger.info(f"Starting bus cancellation task trip {cancelled_trip_id}")
    
    try:
        results = BusCancellationService.handle_bus_cancellation(cancelled_trip_id, reason)
        logger.info(f"Bus cancellation task completed: {results}")
        return results
    except Exception as e:
        logger.error(f"Bus cancellation task failed: {e}")
        return {
            'error': str(e),
            'reassigned_count': 0,
            'manual_reroute_count': 0,
            'failed_count': 1
        }