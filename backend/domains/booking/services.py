"""
Two-way booking service for monitoring connections and handling missed connections.
Integrates with GPS tracking to detect when connections are at risk.
"""
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
import logging

from domains.booking.models import Booking, TwoWayBooking, MissedConnectionEvent, TransactionalVoucher, BookingReassignment
from domains.tracking.redis_client import get_vehicle_position

logger = logging.getLogger(__name__)


class ConnectionMonitor:
    """Monitors two-way booking connections and triggers missed connection events."""
    
    CONNECTION_BUFFER_MINUTES = 5  # Trigger missed connection if ETA within 5 minutes
    
    @classmethod
    def check_all_active_connections(cls):
        """
        Check all active two-way bookings for connection issues.
        This should be called periodically (e.g., every minute via Celery beat).
        """
        active_bookings = TwoWayBooking.objects.filter(
            status=TwoWayBooking.Status.ACTIVE
        )
        
        for two_way_booking in active_bookings:
            if cls.check_connection_status(two_way_booking):
                cls.handle_missed_connection(two_way_booking)
    
    @classmethod
    def check_connection_status(cls, two_way_booking):
        """
        Check if a specific two-way booking's connection is at risk.
        Returns True if connection is likely to be missed.
        """
        outbound = two_way_booking.get_outbound_leg()
        return_leg = two_way_booking.get_return_leg()
        
        if not outbound or not return_leg:
            return False
        
        # Get current GPS position of outbound bus
        vehicle_position = get_vehicle_position(str(outbound.trip.vehicle_id))
        if not vehicle_position:
            return False
        
        # Calculate ETA to transfer station (simplified - would use routing engine)
        # For now, check if bus is significantly delayed
        current_time = timezone.now()
        scheduled_departure = return_leg.trip.departure_time
        
        # If return trip departure is within buffer minutes, trigger missed connection
        time_until_return = (scheduled_departure - current_time).total_seconds() / 60
        
        if time_until_return <= cls.CONNECTION_BUFFER_MINUTES:
            return True
        
        return False
    
    @classmethod
    def handle_missed_connection(cls, two_way_booking):
        """
        Handle a missed connection event:
        1. Update booking statuses
        2. Release seat on return trip
        3. Create transactional voucher
        4. Trigger notification to user
        """
        with transaction.atomic():
            return_leg = two_way_booking.get_return_leg()
            
            # Update two-way booking status
            two_way_booking.status = TwoWayBooking.Status.MISSED_CONNECTION
            two_way_booking.save()
            
            # Update return leg status
            return_leg.status = 'missed_delay'
            return_leg.save()
            
            # Create transactional voucher for return leg fare
            voucher = TransactionalVoucher.objects.create(
                user=two_way_booking.commuter,
                amount=return_leg.fare_paid,
                original_booking=return_leg,
                expires_at=timezone.now() + timedelta(days=30),
            )
            
            # Update two-way booking with voucher info
            two_way_booking.voucher_amount = voucher.amount
            two_way_booking.voucher_expires_at = voucher.expires_at
            two_way_booking.save()
            
            # Create missed connection event record
            MissedConnectionEvent.objects.create(
                linked_booking=None,  # Not a linked booking, but two-way
                first_leg_trip=two_way_booking.get_outbound_leg().trip,
                second_leg_trip=return_leg.trip,
                first_leg_eta_minutes=0,  # Would be calculated from GPS
                second_leg_departure_buffer=0,  # Would be calculated
            )
            
            # TODO: Trigger real-time notification to user's dashboard
            # This would use WebSocket or push notification system


class ReRoutingService:
    """Service for finding alternative routes when connections are missed."""
    
    @classmethod
    def find_alternative_trips(cls, missed_booking, origin_stop, destination_stop):
        """
        Find alternative trips for a missed connection.
        Returns list of available trip options.
        """
        from domains.routing.models import Trip, Stop
        
        # Find trips on the same route departing after current time
        current_time = timezone.now()
        
        # Get the route from the missed booking
        original_route = missed_booking.trip.route
        
        # Find available trips on same route
        alternative_trips = Trip.objects.filter(
            route=original_route,
            status='scheduled',
            departure_time__gt=current_time,
        ).order_by('departure_time')[:5]  # Get next 5 available trips
        
        return alternative_trips
    
    @classmethod
    def apply_re_route(cls, two_way_booking, alternative_trip):
        """
        Apply re-routing by creating a new booking leg.
        """
        with transaction.atomic():
            return_leg = two_way_booking.get_return_leg()
            
            # Create new booking for alternative trip
            new_booking = Booking.objects.create(
                tenant=two_way_booking.tenant,
                commuter=two_way_booking.commuter,
                trip=alternative_trip,
                status='confirmed',
                fare_paid=0,  # Already paid via voucher
                boarding_stop=return_leg.boarding_stop,
                alighting_stop=return_leg.alighting_stop,
                is_two_way=True,
                two_way_booking=two_way_booking,
                leg_order=2,  # This becomes the new return leg
                confirmed_at=timezone.now(),
            )
            
            # Update two-way booking status
            two_way_booking.status = TwoWayBooking.Status.RECOVERED
            two_way_booking.recovery_option_chosen = 're_route'
            two_way_booking.recovery_trip = alternative_trip
            two_way_booking.save()
            
            # Mark old return leg as cancelled
            return_leg.status = 'cancelled'
            return_leg.save()
            
            return new_booking


class RefundService:
    """Service for handling refunds when users opt for refund instead of re-route."""
    
    @classmethod
    def process_refund(cls, two_way_booking):
        """
        Process refund for missed connection leg.
        Creates voucher for future use.
        """
        with transaction.atomic():
            return_leg = two_way_booking.get_return_leg()
            
            # Update two-way booking status
            two_way_booking.status = TwoWayBooking.Status.CANCELLED
            two_way_booking.recovery_option_chosen = 'refund'
            two_way_booking.save()
            
            # Mark return leg as refunded
            return_leg.status = 'refunded'
            return_leg.save()
            
            # Voucher already created when missed connection was detected
            # Just ensure it's active for user to use
            voucher = TransactionalVoucher.objects.filter(
                original_booking=return_leg,
                status='active'
            ).first()
            
            if voucher:
                # Voucher is already active and ready for use
                pass
            
            return voucher


class BusCancellationService:
    """
    Service for handling automatic reassignment of bookings when buses are cancelled or severely delayed.
    Implements atomic seat management and real-time notifications.
    """
    
    @classmethod
    def handle_bus_cancellation(cls, cancelled_trip_id, reason='bus_cancelled'):
        """
        Main entry point for handling bus cancellation.
        
        Args:
            cancelled_trip_id: UUID of the cancelled trip
            reason: Reason for cancellation (default: 'bus_cancelled')
        
        Returns:
            dict with summary of reassignment results
        """
        from domains.routing.models import Trip
        
        logger.info(f"Handling bus cancellation for trip {cancelled_trip_id}")
        
        # Get the cancelled trip
        try:
            cancelled_trip = Trip.objects.select_for_update().get(id=cancelled_trip_id)
        except Trip.DoesNotExist:
            logger.error(f"Trip {cancelled_trip_id} not found")
            return {'error': 'Trip not found', 'reassigned_count': 0, 'manual_reroute_count': 0}
        
        # Update trip status to cancelled
        cancelled_trip.status = 'cancelled'
        cancelled_trip.save()
        
        # Get all affected bookings - focus on RETURN_INWARD and confirmed bookings
        affected_bookings = Booking.objects.filter(
            trip=cancelled_trip,
            status__in=['confirmed', 'held'],
            booking_type__in=[Booking.BookingType.RETURN_INWARD, Booking.BookingType.SINGLE]
        ).select_related('commuter', 'trip__route', 'trip__vehicle')
        
        logger.info(f"Found {affected_bookings.count()} affected bookings for trip {cancelled_trip_id}")
        
        results = {
            'reassigned_count': 0,
            'manual_reroute_count': 0,
            'failed_count': 0,
            'bookings_processed': []
        }
        
        # Process each booking with atomic locks
        for booking in affected_bookings:
            try:
                with transaction.atomic():
                    # Lock the booking for update
                    locked_booking = Booking.objects.select_for_update().get(id=booking.id)
                    
                    # Find next available trip on same route
                    new_trip = cls._find_next_available_trip(
                        cancelled_trip.route,
                        cancelled_trip.departure_time,
                        locked_booking
                    )
                    
                    if new_trip:
                        # Successfully found alternative trip
                        cls._execute_reassignment(
                            locked_booking, cancelled_trip, new_trip, reason
                        )
                        results['reassigned_count'] += 1
                        results['bookings_processed'].append({
                            'booking_id': str(locked_booking.id),
                            'status': 'reassigned',
                            'new_trip_id': str(new_trip.id)
                        })
                    else:
                        # No available trips - flag for manual reroute
                        cls._flag_manual_reroute(
                            locked_booking, cancelled_trip, reason
                        )
                        results['manual_reroute_count'] += 1
                        results['bookings_processed'].append({
                            'booking_id': str(locked_booking.id),
                            'status': 'pending_manual_reroute',
                            'new_trip_id': None
                        })
                        
                        # Send critical alert to admin dashboard
                        cls._send_admin_alert(locked_booking, cancelled_trip)
                    
            except Exception as e:
                logger.error(f"Failed to reassign booking {booking.id}: {e}")
                results['failed_count'] += 1
                results['bookings_processed'].append({
                    'booking_id': str(booking.id),
                    'status': 'failed',
                    'error': str(e)
                })
        
        logger.info(
            f"Bus cancellation complete: {results['reassigned_count']} reassigned, "
            f"{results['manual_reroute_count']} pending manual, "
            f"{results['failed_count']} failed"
        )
        
        return results
    
    @classmethod
    def _find_next_available_trip(cls, route, after_time, booking):
        """
        Find the next available trip on the same route with open seat capacity.
        
        Args:
            route: The route to search for alternative trips
            after_time: Search for trips departing after this time
            booking: The booking being reassigned (for seat availability check)
        
        Returns:
            Trip object if available, None otherwise
        """
        from domains.routing.models import Trip
        
        # Find active trips on same route departing after the cancelled time
        current_time = timezone.now()
        
        available_trips = Trip.objects.filter(
            route=route,
            status='active',
            departure_time__gt=after_time if after_time else current_time
        ).select_related('vehicle').order_by('departure_time')
        
        # Find first trip with available seats
        for trip in available_trips:
            # Use select_for_update to lock the trip for seat check
            locked_trip = Trip.objects.select_for_update().get(id=trip.id)
            
            # Check if trip has available seats
            if locked_trip.available_seats > 0:
                return locked_trip
        
        return None
    
    @classmethod
    def _execute_reassignment(cls, booking, original_trip, new_trip, reason):
        """
        Execute the reassignment of a booking to a new trip.
        
        Args:
            booking: The booking to reassign
            original_trip: The original cancelled trip
            new_trip: The new trip to reassign to
            reason: Reason for reassignment
        """
        # Store original trip details
        original_departure = original_trip.departure_time
        original_plate = original_trip.vehicle.plate_number
        
        # Update booking to new trip
        booking.trip = new_trip
        booking.status = 'confirmed'  # Ensure confirmed status
        
        # Regenerate ticket codes for new trip
        booking.generate_ticket_codes()
        booking.save()
        
        # Create reassignment record for audit trail
        reassignment = BookingReassignment.objects.create(
            tenant=booking.tenant,
            booking=booking,
            original_trip=original_trip,
            new_trip=new_trip,
            reason=reason,
            status=BookingReassignment.ReassignmentStatus.SUCCESS,
            original_departure_time=original_departure,
            new_departure_time=new_trip.departure_time,
            original_vehicle_plate=original_plate,
            new_vehicle_plate=new_trip.vehicle.plate_number,
            created_at=timezone.now(),
            resolved_at=timezone.now(),
        )
        
        # Send real-time notification to commuter
        cls._send_reassignment_notification(booking, new_trip, reassignment)
        
        logger.info(f"Successfully reassigned booking {booking.id} to trip {new_trip.id}")
    
    @classmethod
    def _flag_manual_reroute(cls, booking, original_trip, reason):
        """
        Flag a booking for manual rerouting when no automatic reassignment is possible.
        
        Args:
            booking: The booking to flag
            original_trip: The original cancelled trip
            reason: Reason for reassignment
        """
        # Update booking status
        booking.status = 'pending_manual_reroute'
        booking.save()
        
        # Create reassignment record with pending status
        reassignment = BookingReassignment.objects.create(
            tenant=booking.tenant,
            booking=booking,
            original_trip=original_trip,
            new_trip=None,
            reason=reason,
            status=BookingReassignment.ReassignmentStatus.PENDING_MANUAL,
            original_departure_time=original_trip.departure_time,
            original_vehicle_plate=original_trip.vehicle.plate_number,
            admin_notes='No available trips on route for automatic reassignment. Manual intervention required.',
            created_at=timezone.now(),
        )
        
        logger.warning(f"Booking {booking.id} flagged for manual rerouting")
    
    @classmethod
    def _send_reassignment_notification(cls, booking, new_trip, reassignment):
        """
        Send real-time WebSocket notification to affected commuter.
        
        Args:
            booking: The reassigned booking
            new_trip: The new trip
            reassignment: The reassignment record
        """
        from channels.layers import get_channel_layer
        import asyncio
        import json
        
        channel_layer = get_channel_layer()
        
        # Format departure time
        departure_time_str = new_trip.departure_time.strftime('%I:%M %p') if new_trip.departure_time else 'TBD'
        
        message = (
            f"Your evening return bus has changed. We've automatically secured your seat "
            f"on the next available bus leaving at {departure_time_str} "
            f"(Bus Plate: {new_trip.vehicle.plate_number})."
        )
        
        async def send_notification():
            await channel_layer.group_send(
                f'user_{booking.commuter.id}',
                {
                    'type': 'booking.reassigned',
                    'booking_id': str(booking.id),
                    'original_trip_id': str(reassignment.original_trip.id) if reassignment.original_trip else None,
                    'new_trip_id': str(new_trip.id),
                    'new_departure_time': departure_time_str,
                    'new_vehicle_plate': new_trip.vehicle.plate_number,
                    'new_route_name': new_trip.route.name,
                    'message': message,
                    'reassignment_id': str(reassignment.id),
                    'timestamp': timezone.now().isoformat(),
                }
            )
        
        # Run async function in sync context
        try:
            asyncio.run(send_notification())
            
            # Update reassignment record
            reassignment.notification_sent = True
            reassignment.notification_sent_at = timezone.now()
            reassignment.save()
            
            logger.info(f"Sent reassignment notification to user {booking.commuter.id}")
        except Exception as e:
            logger.error(f"Failed to send reassignment notification: {e}")
    
    @classmethod
    def _send_admin_alert(cls, booking, cancelled_trip):
        """
        Send critical alert to admin dashboard for manual rerouting cases.
        
        Args:
            booking: The booking requiring manual intervention
            cancelled_trip: The cancelled trip
        """
        from channels.layers import get_channel_layer
        import asyncio
        
        channel_layer = get_channel_layer()
        
        async def send_alert():
            await channel_layer.group_send(
                'admin_alerts',
                {
                    'type': 'admin.manual_reroute_required',
                    'booking_id': str(booking.id),
                    'commuter_id': str(booking.commuter.id),
                    'commuter_name': booking.commuter.username,
                    'cancelled_trip_id': str(cancelled_trip.id),
                    'route_name': cancelled_trip.route.name,
                    'original_departure': cancelled_trip.departure_time.isoformat() if cancelled_trip.departure_time else None,
                    'message': f'Manual rerouting required for booking {booking.id} - no available trips on route',
                    'priority': 'critical',
                    'timestamp': timezone.now().isoformat(),
                }
            )
        
        # Run async function in sync context
        try:
            asyncio.run(send_alert())
            logger.info(f"Sent admin alert for booking {booking.id}")
        except Exception as e:
            logger.error(f"Failed to send admin alert: {e}")
