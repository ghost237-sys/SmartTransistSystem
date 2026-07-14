"""
GPS simulation — moves a bus along the trip's route stops and broadcasts live positions.

Run inside Docker:
  docker compose exec backend python scripts/simulate_gps.py <trip_id> <driver_username>

Full demo (depart → drive all stops → complete):
  docker compose exec backend python scripts/simulate_gps.py <trip_id> driver_kamau \\
    --conductor conductor_wanjiku --auto-lifecycle

Linked journey simulation (two buses):
  docker compose exec backend python scripts/simulate_gps.py <first_trip_id> driver_kamau \\
    --linked --second-trip-id <second_trip_id> --second-driver driver_john \\
    --conductor conductor_wanjiku

Test missed connection scenario:
  docker compose exec backend python scripts/simulate_gps.py <first_trip_id> driver_kamau \\
    --linked --second-trip-id <second_trip_id> --second-driver driver_john \\
    --test-missed

Test transfer geofence breach (LINK_LEG_1 -> LINK_LEG_2):
  docker compose exec backend python scripts/simulate_gps.py --test-transfer

Test bus breakdown and automatic reassignment:
  docker compose exec backend python scripts/simulate_gps.py --test-breakdown [--trip-id <trip_id>]

Options:
  --interval SECONDS     Seconds between position pings (default: 3)
  --steps-per-leg N      Interpolation points between each stop (default: 25)
  --pause-at-stops SEC   Pause at each stop before continuing (default: 5)
  --conductor USER       Conductor username for depart/complete (default: conductor_wanjiku)
  --auto-lifecycle       Mark trip departed at start and completed at end
  --password PASS        Login password (default: demo1234)
  --base-url URL         API base URL (default: http://localhost:8000)
  --linked               Enable linked journey mode (simulate two buses)
  --second-trip-id       Second trip ID for linked mode
  --second-driver        Second driver username for linked mode
  --delay-minutes MIN    Simulate delay for first bus in linked mode (default: 0)
  --test-missed          Test missed connection scenario (first bus delayed beyond buffer)
  --test-transfer        Test transfer geofence breach (simulates Bus A approaching transfer station)
  --test-breakdown       Test bus breakdown and automatic reassignment (triggers handle_bus_cancellation)
"""
import argparse
import math
import os
import sys
import time
import threading
import queue

import requests
from django.db import models


def parse_args():
    parser = argparse.ArgumentParser(description='Simulate a bus moving along a trip route.')
    parser.add_argument('trip_id', nargs='?', help='Trip UUID to simulate (not required for --test-transfer)')
    parser.add_argument('driver_username', nargs='?', help='Driver username assigned to the trip (not required for --test-transfer)')
    parser.add_argument('--linked', action='store_true', help='Enable linked journey mode')
    parser.add_argument('--second-trip-id', help='Second trip ID for linked mode')
    parser.add_argument('--second-driver', help='Second driver username for linked mode')
    parser.add_argument('--conductor', default='conductor_wanjiku', help='Conductor for lifecycle calls')
    parser.add_argument('--password', default='demo1234', help='Login password')
    parser.add_argument('--base-url', default='http://localhost:8000', help='API base URL')
    parser.add_argument('--interval', type=float, default=3.0, help='Seconds between GPS pings')
    parser.add_argument('--steps-per-leg', type=int, default=25, help='Points between each stop')
    parser.add_argument('--pause-at-stops', type=float, default=5.0, help='Seconds to pause at each stop')
    parser.add_argument(
        '--auto-lifecycle',
        action='store_true',
        help='Depart trip at start and complete it when the route finishes',
    )
    parser.add_argument('--delay-minutes', type=float, default=0.0, help='Simulate delay for first bus in linked mode')
    parser.add_argument(
        '--test-missed',
        action='store_true',
        help='Test missed connection scenario (first bus delayed beyond buffer)',
    )
    parser.add_argument(
        '--test-transfer',
        action='store_true',
        help='Test transfer geofence breach (simulates Bus A approaching transfer station)',
    )
    parser.add_argument(
        '--test-breakdown',
        action='store_true',
        help='Test bus breakdown and automatic reassignment (triggers handle_bus_cancellation)',
    )
    parser.add_argument(
        '--loop',
        action='store_true',
        help='Run the simulation in a continuous loop, resetting the trip status to active after reaching final stop',
    )
    return parser.parse_args()


def get_token(base_url, username, password):
    res = requests.post(
        f'{base_url}/api/auth/token/',
        json={'username': username, 'password': password},
        timeout=10,
    )
    if res.status_code != 200:
        detail = res.json().get('detail', res.text) if res.content else res.status_code
        raise RuntimeError(f'Login failed for {username}: {detail}')
    return res.json()['access']


def post_position(base_url, token, vehicle_id, trip_id, lat, lng, speed):
    res = requests.post(
        f'{base_url}/api/telemetry/position/',
        json={
            'vehicle_id': vehicle_id,
            'trip_id': trip_id,
            'latitude': lat,
            'longitude': lng,
            'speed_kmh': round(speed, 1),
        },
        headers={'Authorization': f'Bearer {token}'},
        timeout=10,
    )
    return res


def depart_trip(base_url, token, trip_id):
    res = requests.post(
        f'{base_url}/api/bookings/trips/{trip_id}/depart/',
        headers={'Authorization': f'Bearer {token}'},
        timeout=10,
    )
    return res


def complete_trip(base_url, token, trip_id):
    res = requests.post(
        f'{base_url}/api/bookings/trips/{trip_id}/complete/',
        headers={'Authorization': f'Bearer {token}'},
        timeout=10,
    )
    return res


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def interpolate(start, end, steps):
    for i in range(steps):
        t = i / steps
        yield (
            start[0] + (end[0] - start[0]) * t,
            start[1] + (end[1] - start[1]) * t,
        )


def load_route_stops(trip):
    stops = list(trip.route.stops.order_by('sequence'))
    if len(stops) < 2:
        raise RuntimeError(
            f'Route "{trip.route.name}" needs at least 2 stops for simulation '
            f'(found {len(stops)}). Re-run seed_demo.py.'
        )
    waypoints = []
    for stop in stops:
        waypoints.append({
            'name': stop.name,
            'lat': stop.location.y,
            'lng': stop.location.x,
        })
    return waypoints


def simulate_transfer_geofence_breach(args):
    """
    Simulate Bus A breaching the transfer geofence for LINK_LEG_1 -> LINK_LEG_2 transfers.
    
    This mode:
    1. Scans for active LINK_LEG_1 bookings where linked LINK_LEG_2 is in PENDING_TRANSFER
    2. Identifies the pending_transfer_stop for that journey
    3. Simulates Bus A driving incrementally closer (5km -> 3.5km -> 1.5km breach)
    4. Prints descriptive logs showing distance and status on each tick
    """
    import django
    sys.path.insert(0, '/app')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

    from domains.booking.models import Booking
    from django.contrib.gis.geos import Point

    base_url = args.base_url.rstrip('/')

    print('═' * 60)
    print('🎯 Transfer Geofence Breach Simulation')
    print('═' * 60)
    print()

    # Scan for active LINK_LEG_1 bookings with PENDING_TRANSFER Leg 2
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

    if not active_leg1_bookings.exists():
        print('✗ No active LINK_LEG_1 bookings found.')
        print('  Create a linked journey booking first to test this mode.')
        return

    # Find bookings where Leg 2 is in PENDING_TRANSFER state
    target_booking = None
    for leg1_booking in active_leg1_bookings:
        leg2_booking = leg1_booking.linked_booking
        if leg2_booking and leg2_booking.booking_type == Booking.BookingType.LINK_LEG_2:
            if leg2_booking.status == 'pending_transfer':
                target_booking = leg1_booking
                break

    if not target_booking:
        print('✗ No LINK_LEG_1 bookings with PENDING_TRANSFER Leg 2 found.')
        print('  Ensure Leg 2 is in pending_transfer state to test this mode.')
        return

    leg2_booking = target_booking.linked_booking
    transfer_station = target_booking.pending_transfer_stop

    if not transfer_station:
        print('✗ No pending_transfer_stop found for booking.')
        return

    print(f'✓ Found target booking:')
    print(f'   Leg 1: {target_booking.trip.route.name} (Trip {target_booking.trip.id[:8]}...)')
    print(f'   Leg 1 Status: {target_booking.status}')
    print(f'   Leg 2: {leg2_booking.trip.route.name} (Trip {leg2_booking.trip.id[:8]}...)')
    print(f'   Leg 2 Status: {leg2_booking.status}')
    print(f'   Transfer Station: {transfer_station.name}')
    print(f'   Transfer Trigger Distance: {leg2_booking.transfer_trigger_km} km')
    print()

    # Get Bus A details
    leg1_trip = target_booking.trip
    vehicle_id = str(leg1_trip.vehicle_id)
    driver_username = leg1_trip.driver.username if leg1_trip.driver else 'driver_kamau'

    try:
        driver_token = get_token(base_url, driver_username, args.password)
        print(f'✓ Authenticated as driver: {driver_username}')
    except Exception as e:
        print(f'✗ Authentication failed: {e}')
        return

    # Get transfer station coordinates
    transfer_lat = transfer_station.location.y
    transfer_lng = transfer_station.location.x

    # Calculate starting position (5km away from transfer station)
    # Start directly south of the transfer station for simplicity
    start_km = 5.0
    start_lat = transfer_lat - (start_km / 111.32)  # Approximate km to degrees
    start_lng = transfer_lng

    # Distance steps: 5km -> 3.5km -> 2.0km -> 1.5km (breach) -> 1.0km -> 0.5km
    distance_steps = [5.0, 3.5, 2.0, 1.5, 1.0, 0.5]
    trigger_km = leg2_booking.transfer_trigger_km

    print()
    print('═' * 60)
    print('📍 Starting geofence breach simulation')
    print('═' * 60)
    print(f'   Transfer Station: ({transfer_lat:.4f}, {transfer_lng:.4f})')
    print(f'   Trigger Threshold: {trigger_km} km')
    print(f'   Distance Steps: {distance_steps}')
    print('═' * 60)
    print()

    step = 0
    failed_pings = 0
    breach_detected = False

    for target_distance in distance_steps:
        # Calculate position at this distance
        current_lat = transfer_lat - (target_distance / 111.32)
        current_lng = transfer_lng

        # Calculate actual distance using haversine
        actual_distance = haversine_km(current_lat, current_lng, transfer_lat, transfer_lng)

        # Post position
        speed = 40.0  # Constant speed for simulation
        res = post_position(base_url, driver_token, vehicle_id, str(leg1_trip.id), current_lat, current_lng, speed)
        step += 1

        if res.status_code == 201:
            status_icon = '✓'
        else:
            failed_pings += 1
            status_icon = '✗'

        # Check if we've breached the threshold
        is_breached = actual_distance <= trigger_km
        if is_breached and not breach_detected:
            breach_detected = True
            breach_icon = '🚨'
        else:
            breach_icon = ''

        # Refresh booking status from DB
        target_booking.refresh_from_db()
        leg2_booking.refresh_from_db()

        # Print descriptive log
        print(f'{status_icon} Step {step}: Distance to transfer: {actual_distance:.2f} km')
        print(f'   Position: ({current_lat:.4f}, {current_lng:.4f})')
        print(f'   Leg 1 Status: {target_booking.status}')
        print(f'   Leg 2 Status: {leg2_booking.status}')
        print(f'   Threshold: {trigger_km} km {breach_icon} {"BREACHED!" if breach_detected else ""}')
        print()

        if is_breached:
            print('🎯 Geofence breach detected!')
            print('   monitor_transfer_proximity task should now:')
            print('   - Transition Leg 2 to CONFIRMED')
            print('   - Decrement seat from Bus B')
            print('   - Trigger WebSocket broadcast')
            print()

        time.sleep(args.interval * 2)  # Longer pause between steps for visibility

    print('═' * 60)
    print('🏁 Simulation complete')
    print('═' * 60)
    print()
    print('Final Status:')
    print(f'   Leg 1: {target_booking.status}')
    print(f'   Leg 2: {leg2_booking.status}')
    print()

    if leg2_booking.status == 'confirmed':
        print('✅ SUCCESS: Leg 2 was confirmed by monitor_transfer_proximity task!')
    else:
        print('⚠ Leg 2 was not confirmed. Check:')
        print('  - Celery worker is running monitor_transfer_proximity')
        print('  - Bus B has available seats')
        print('  - GPS data is being processed correctly')

    if failed_pings:
        print(f'\n⚠ {failed_pings} position ping(s) failed')


def simulate_breakdown(args):
    """
    Simulate a bus breakdown and trigger automatic reassignment.
    
    This mode:
    1. Targets an active trip with multiple CONFIRMED or RETURN_INWARD bookings
    2. Programmatically triggers handle_bus_cancellation service
    3. Prints detailed telemetry of the reassignment process
    4. Shows affected passengers, available bus search, re-mapping, and WebSocket payloads
    """
    import django
    sys.path.insert(0, '/app')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

    from domains.booking.models import Booking
    from domains.booking.services import BusCancellationService
    from domains.routing.models import Trip

    print('═' * 60)
    print('🔧 Bus Breakdown & Automatic Reassignment Simulation')
    print('═' * 60)
    print()

    # If trip_id provided, use it; otherwise find a suitable target
    if args.trip_id:
        try:
            target_trip = Trip.objects.get(id=args.trip_id)
            print(f'✓ Using specified trip: {target_trip.id[:8]}...')
        except Trip.DoesNotExist:
            print(f'✗ Trip {args.trip_id} not found.')
            return
    else:
        # Find a trip with multiple CONFIRMED or RETURN_INWARD bookings
        print('🔍 Scanning for active trips with multiple bookings...')
        
        # Query trips with confirmed bookings
        trips_with_bookings = Trip.objects.filter(
            status__in=['active', 'scheduled'],
            bookings__status__in=['confirmed', 'held'],
            bookings__booking_type__in=[
                Booking.BookingType.RETURN_INWARD,
                Booking.BookingType.SINGLE
            ]
        ).annotate(
            booking_count=models.Count('bookings')
        ).filter(
            booking_count__gte=2  # At least 2 bookings for meaningful test
        ).select_related('route', 'vehicle').distinct()

        if not trips_with_bookings.exists():
            print('✗ No active trips with multiple bookings found.')
            print('  Create some bookings first to test this mode.')
            return

        target_trip = trips_with_bookings.first()
        print(f'✓ Found target trip: {target_trip.id[:8]}...')

    print()
    print('═' * 60)
    print('📋 Target Trip Details')
    print('═' * 60)
    print(f'   Trip ID: {target_trip.id}')
    print(f'   Route: {target_trip.route.name}')
    print(f'   Vehicle: {target_trip.vehicle.plate_number}')
    print(f'   Status: {target_trip.status}')
    print(f'   Departure Time: {target_trip.departure_time}')
    print()

    # Get affected bookings before cancellation
    affected_bookings = Booking.objects.filter(
        trip=target_trip,
        status__in=['confirmed', 'held'],
        booking_type__in=[
            Booking.BookingType.RETURN_INWARD,
            Booking.BookingType.SINGLE
        ]
    ).select_related('commuter', 'trip__route', 'trip__vehicle')

    print('═' * 60)
    print('👥 Affected Passengers (Before Cancellation)')
    print('═' * 60)
    print(f'   Total affected bookings: {affected_bookings.count()}')
    print()

    for booking in affected_bookings:
        commuter_name = booking.commuter.username if booking.commuter else 'Walk-up'
        print(f'   - {commuter_name} ({booking.booking_type})')
        print(f'     Booking ID: {booking.id[:8]}...')
        print(f'     Fare: KES {booking.fare_paid or "N/A"}')
        print()

    # Store original seat counts for comparison
    original_available_seats = target_trip.available_seats
    print(f'   Original available seats on bus: {original_available_seats}')
    print()

    # Confirm before proceeding
    print('⚠ WARNING: This will cancel the trip and trigger automatic reassignment!')
    response = input('   Proceed? (yes/no): ')
    if response.lower() != 'yes':
        print('   Simulation cancelled by user.')
        return

    print()
    print('═' * 60)
    print('🚨 Triggering Bus Cancellation')
    print('═' * 60)
    print(f'   Calling BusCancellationService.handle_bus_cancellation({target_trip.id})')
    print()

    # Trigger the cancellation service
    try:
        results = BusCancellationService.handle_bus_cancellation(
            target_trip.id,
            reason='simulated_breakdown'
        )
    except Exception as e:
        print(f'✗ Error during cancellation: {e}')
        import traceback
        traceback.print_exc()
        return

    print()
    print('═' * 60)
    print('📊 Reassignment Results')
    print('═' * 60)
    print(f'   Reassigned successfully: {results.get("reassigned_count", 0)}')
    print(f'   Pending manual reroute: {results.get("manual_reroute_count", 0)}')
    print(f'   Failed: {results.get("failed_count", 0)}')
    print()

    # Show detailed booking processing results
    if 'bookings_processed' in results:
        print('═' * 60)
        print('📝 Booking Processing Details')
        print('═' * 60)
        
        for result in results['bookings_processed']:
            booking_id = result.get('booking_id', 'N/A')
            status = result.get('status', 'unknown')
            new_trip_id = result.get('new_trip_id')
            
            print(f'   Booking {booking_id[:8]}...: {status.upper()}')
            
            if status == 'reassigned' and new_trip_id:
                print(f'      → Reassigned to trip: {new_trip_id[:8]}...')
                
                # Get new trip details
                try:
                    new_trip = Trip.objects.get(id=new_trip_id)
                    print(f'      → New vehicle: {new_trip.vehicle.plate_number}')
                    print(f'      → New departure: {new_trip.departure_time}')
                    
                    # Show seat inventory change
                    print(f'      → Available seats after reassignment: {new_trip.available_seats}')
                except Trip.DoesNotExist:
                    print(f'      → (Could not fetch new trip details)')
            
            elif status == 'pending_manual_reroute':
                print(f'      → Flagged for manual intervention')
            
            elif status == 'failed':
                error = result.get('error', 'Unknown error')
                print(f'      → Error: {error}')
            
            print()

    # Show WebSocket payload structure
    print('═' * 60)
    print('📡 WebSocket Notification Payload Structure')
    print('═' * 60)
    print('   For each successfully reassigned booking, the following payload')
    print('   is sent via WebSocket to the affected commuter:')
    print()
    print('   {')
    print('     "type": "booking.reassigned",')
    print('     "booking_id": "<UUID>",')
    print('     "original_trip_id": "<UUID>",')
    print('     "new_trip_id": "<UUID>",')
    print('     "new_departure_time": "<HH:MM AM/PM>",')
    print('     "new_vehicle_plate": "<Plate Number>",')
    print('     "new_route_name": "<Route Name>",')
    print('     "message": "Your evening return bus has changed...",')
    print('     "reassignment_id": "<UUID>",')
    print('     "timestamp": "<ISO 8601 timestamp>"')
    print('   }')
    print()

    # Show admin alert structure for manual reroutes
    if results.get('manual_reroute_count', 0) > 0:
        print('═' * 60)
        print('🚨 Admin Alert Payload Structure (Manual Reroute)')
        print('═' * 60)
        print('   For bookings requiring manual intervention, this payload is')
        print('   sent to the admin_alerts channel:')
        print()
        print('   {')
        print('     "type": "admin.manual_reroute_required",')
        print('     "booking_id": "<UUID>",')
        print('     "commuter_id": "<UUID>",')
        print('     "commuter_name": "<Username>",')
        print('     "cancelled_trip_id": "<UUID>",')
        print('     "route_name": "<Route Name>",')
        print('     "original_departure": "<ISO 8601 timestamp>",')
        print('     "message": "Manual rerouting required...",')
        print('     "priority": "critical",')
        print('     "timestamp": "<ISO 8601 timestamp>"')
        print('   }')
        print()

    # Show final state
    print('═' * 60)
    print('🏁 Final State')
    print('═' * 60)
    target_trip.refresh_from_db()
    print(f'   Trip status: {target_trip.status}')
    print(f'   Original vehicle: {target_trip.vehicle.plate_number}')
    print()

    # Show BookingReassignment records created
    from domains.booking.models import BookingReassignment
    reassignments = BookingReassignment.objects.filter(
        original_trip=target_trip
    ).select_related('booking', 'new_trip')

    if reassignments.exists():
        print(f'   BookingReassignment records created: {reassignments.count()}')
        for reassignment in reassignments:
            print(f'   - {reassignment.booking.id[:8]}... → {reassignment.status}')
            if reassignment.new_trip:
                print(f'     New trip: {reassignment.new_trip.id[:8]}...')
    else:
        print('   No BookingReassignment records found')

    print()
    print('✅ Simulation complete!')


def simulate_single_trip(trip_id, driver_username, args, message_queue):
    """Simulate a single trip and send status updates to message queue."""
    import django
    sys.path.insert(0, '/app')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

    from domains.routing.models import Trip

    base_url = args.base_url.rstrip('/')

    try:
        trip = Trip.all_objects.select_related('route', 'vehicle', 'driver').get(id=trip_id)
    except Trip.DoesNotExist:
        message_queue.put(f'✗ Trip not found: {trip_id}')
        return

    vehicle_id = str(trip.vehicle_id)
    waypoints = load_route_stops(trip)

    message_queue.put(f'🚌 Starting simulation for {trip.route.name} (Trip {trip_id[:8]}...)')
    message_queue.put(f'   Vehicle: {trip.vehicle.plate_number}')
    message_queue.put(f'   Driver: {driver_username}')
    message_queue.put(f'   Stops: {len(waypoints)}')

    try:
        driver_token = get_token(base_url, driver_username, args.password)
        message_queue.put(f'✓ Authenticated as driver: {driver_username}')
    except Exception as e:
        message_queue.put(f'✗ Authentication failed: {e}')
        return

    loop_count = 0
    while True:
        if loop_count > 0:
            message_queue.put(f'🔄 Resetting trip status to active and starting from first stop...')
            try:
                trip.status = 'active'
                trip.save(update_fields=['status'])
            except Exception as e:
                message_queue.put(f'✗ Failed to reset trip status: {e}')
            
        step = 0
        failed_pings = 0
        delay_applied = False

        try:
            for segment in range(len(waypoints) - 1):
                start = waypoints[segment]
                end = waypoints[segment + 1]
                leg_km = haversine_km(start['lat'], start['lng'], end['lat'], end['lng'])
                leg_minutes = (args.steps_per_leg * args.interval) / 60
                avg_speed = (leg_km / leg_minutes * 60) if leg_minutes else 50

                message_queue.put(f'📍 {start["name"]} → {end["name"]}  (~{leg_km:.1f} km)')

                # Apply delay if specified and not yet applied
                if args.delay_minutes > 0 and not delay_applied and segment == 0:
                    delay_seconds = args.delay_minutes * 60
                    message_queue.put(f'⏸ Simulating {args.delay_minutes} minute delay...')
                    time.sleep(delay_seconds)
                    delay_applied = True
                    message_queue.put(f'▶ Resuming after delay')

                for lat, lng in interpolate(
                    (start['lat'], start['lng']),
                    (end['lat'], end['lng']),
                    args.steps_per_leg,
                ):
                    speed = max(20, min(80, avg_speed + (step % 7) - 3))
                    res = post_position(base_url, driver_token, vehicle_id, trip_id, lat, lng, speed)
                    step += 1

                    if res.status_code == 201:
                        status_icon = '✓'
                    else:
                        failed_pings += 1
                        status_icon = '✗'

                    message_queue.put(
                        f'{status_icon} {trip.route.name[:15]:15} ({lat:.4f}, {lng:.4f}) '
                        f'{speed:.0f} km/h  ping {step}'
                    )
                    time.sleep(args.interval)

                message_queue.put(f'✅ Arrived at {end["name"]}')

                if args.pause_at_stops > 0 and segment < len(waypoints) - 2:
                    message_queue.put(f'   Pausing {args.pause_at_stops:.0f}s at stop...')
                    time.sleep(args.pause_at_stops)

            message_queue.put(f'🏁 {trip.route.name} complete')

            if args.auto_lifecycle:
                conductor_token = get_token(base_url, args.conductor, args.password)
                res = complete_trip(base_url, conductor_token, trip_id)
                if res.status_code == 200:
                    data = res.json()
                    message_queue.put(
                        f'✓ Trip completed — {data.get("passengers_boarded", 0)} boarded, '
                        f'KES {data.get("total_revenue", 0)} revenue'
                    )

        except Exception as e:
            message_queue.put(f'✗ Simulation error: {e}')

        if failed_pings:
            message_queue.put(f'⚠ {failed_pings} position ping(s) failed')

        if not args.loop:
            break
        loop_count += 1

    message_queue.put(f'DONE:{trip_id}')


def main():
    args = parse_args()

    # Check if transfer geofence breach test mode
    if args.test_transfer:
        simulate_transfer_geofence_breach(args)
        return

    # Check if breakdown test mode
    if args.test_breakdown:
        simulate_breakdown(args)
        return

    # Validate required arguments for non-test modes
    if not args.trip_id or not args.driver_username:
        print('✗ trip_id and driver_username are required (unless using --test-transfer or --test-breakdown)')
        print('  Usage: docker compose exec backend python scripts/simulate_gps.py <trip_id> <driver_username>')
        sys.exit(1)

    # Check if linked mode
    if args.linked:
        if not args.second_trip_id or not args.second_driver:
            print('✗ Linked mode requires: --linked --second-trip-id <id> --second-driver <username>')
            sys.exit(1)

        print('═' * 60)
        print('🔗 Linked Journey Simulation')
        print('═' * 60)
        print(f'Bus 1: Trip {args.trip_id[:15]}... (Driver: {args.driver_username})')
        print(f'Bus 2: Trip {args.second_trip_id[:15]}... (Driver: {args.second_driver})')
        if args.test_missed:
            print('⚠ Testing missed connection scenario (Bus 1 will be delayed)')
        print('═' * 60)
        print()

        # Set delay for missed connection test
        if args.test_missed:
            args.delay_minutes = 10  # 10 minute delay to trigger missed connection

        # Create message queue for thread communication
        msg_queue = queue.Queue()

        # Start both simulations in parallel threads
        thread1 = threading.Thread(
            target=simulate_single_trip,
            args=(args.trip_id, args.driver_username, args, msg_queue)
        )
        thread2 = threading.Thread(
            target=simulate_single_trip,
            args=(args.second_trip_id, args.second_driver, args, msg_queue)
        )

        thread1.start()
        thread2.start()

        # Monitor and display messages
        completed = 0
        try:
            while completed < 2:
                try:
                    msg = msg_queue.get(timeout=1)
                    if msg.startswith('DONE:'):
                        completed += 1
                        print(f'\n✓ Trip completed ({completed}/2)')
                    else:
                        print(msg)
                except queue.Empty:
                    continue
        except KeyboardInterrupt:
            print('\n\n⏹ Simulation stopped by user.')
            sys.exit(0)

        print('\n🎉 Both simulations complete!')
        print('Check the backend logs for missed connection events if testing that scenario.')
        return

    # Single trip mode (original functionality)
    trip_id = args.trip_id
    driver_username = args.driver_username

    import django
    sys.path.insert(0, '/app')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

    from domains.routing.models import Trip

    base_url = args.base_url.rstrip('/')

    try:
        trip = Trip.all_objects.select_related('route', 'vehicle', 'driver').get(id=trip_id)
    except Trip.DoesNotExist:
        print(f'✗ Trip not found: {trip_id}')
        print('  Run: docker compose exec backend python scripts/seed_demo.py')
        sys.exit(1)

    if trip.driver and trip.driver.username != driver_username:
        print(
            f'⚠ Warning: trip driver is "{trip.driver.username}", '
            f'not "{driver_username}". Telemetry may be rejected.'
        )

    if trip.status == 'completed':
        if args.loop:
            trip.status = 'active'
            trip.save(update_fields=['status'])
            print(f'✓ Reset completed trip status to active for looping.')
        else:
            print(f'✗ Trip is already completed. Pick an active trip (e.g. from seed_demo.py).')
            sys.exit(1)

    if trip.status == 'cancelled':
        print('✗ Trip is cancelled.')
        sys.exit(1)

    vehicle_id = str(trip.vehicle_id)
    waypoints = load_route_stops(trip)

    print('═' * 60)
    print(f'🚌 GPS Simulation — {trip.route.name}')
    print(f'   Vehicle:   {trip.vehicle.plate_number}')
    print(f'   Trip ID:   {trip_id}')
    print(f'   Status:    {trip.status}')
    print(f'   Stops:     {len(waypoints)}')
    print(f'   Interval:  {args.interval}s')
    print(f'   Lifecycle: {"auto depart → complete" if args.auto_lifecycle else "manual"}')
    if args.loop:
        print('   Looping:   enabled (continuous routing)')
    print('═' * 60)
    print()
    print('Open the commuter tracking page for this trip to watch live.')
    print('Press Ctrl+C to stop early.')
    print()

    driver_token = get_token(base_url, driver_username, args.password)
    token_refresh_at = time.time() + 240
    print(f'✓ Authenticated as driver: {driver_username}')

    conductor_token = None
    if args.auto_lifecycle:
        conductor_token = get_token(base_url, args.conductor, args.password)
        print(f'✓ Authenticated as conductor: {args.conductor}')

        # On-demand model: trips are always active, no separate 'departed' state
        # Skip depart step for on-demand model
        print('• On-demand model: trip is already active — continuing simulation')
    print()

    loop_count = 0
    while True:
        if loop_count > 0:
            print('\n\n🔄 Resetting trip status to active and starting from first stop...')
            try:
                trip.status = 'active'
                trip.save(update_fields=['status'])
            except Exception as e:
                print(f'\n✗ Failed to reset trip status: {e}')
            
        step = 0
        failed_pings = 0

        try:
            for segment in range(len(waypoints) - 1):
                start = waypoints[segment]
                end = waypoints[segment + 1]
                leg_km = haversine_km(start['lat'], start['lng'], end['lat'], end['lng'])
                leg_minutes = (args.steps_per_leg * args.interval) / 60
                avg_speed = (leg_km / leg_minutes * 60) if leg_minutes else 50

                print(f'📍 {start["name"]} → {end["name"]}  (~{leg_km:.1f} km)')

                for lat, lng in interpolate(
                    (start['lat'], start['lng']),
                    (end['lat'], end['lng']),
                    args.steps_per_leg,
                ):
                    if time.time() > token_refresh_at:
                        driver_token = get_token(base_url, driver_username, args.password)
                        token_refresh_at = time.time() + 240
                        print('\n↻ Driver token refreshed')

                    speed = max(20, min(80, avg_speed + (step % 7) - 3))
                    res = post_position(base_url, driver_token, vehicle_id, trip_id, lat, lng, speed)
                    step += 1

                    if res.status_code == 201:
                        status_icon = '✓'
                    else:
                        failed_pings += 1
                        status_icon = '✗'
                        if failed_pings <= 3:
                            detail = res.json().get('detail', res.text) if res.content else res.status_code
                            print(f'\n✗ Position rejected: {detail}')

                    print(
                        f'\r{status_icon} ({lat:.4f}, {lng:.4f}) '
                        f'{speed:.0f} km/h  ping {step}',
                        end='',
                        flush=True,
                    )
                    time.sleep(args.interval)

                print(f'\n✅ Arrived at {end["name"]}')

                if args.pause_at_stops > 0 and segment < len(waypoints) - 2:
                    print(f'   Pausing {args.pause_at_stops:.0f}s at stop...')
                    time.sleep(args.pause_at_stops)
                print()

            print('🏁 Route complete — arrived at final stop.')

            if args.auto_lifecycle and conductor_token:
                res = complete_trip(base_url, conductor_token, trip_id)
                if res.status_code == 200:
                    data = res.json()
                    print(
                        f'✓ Trip completed — {data.get("passengers_boarded", 0)} boarded, '
                        f'KES {data.get("total_revenue", 0)} revenue'
                    )
                else:
                    detail = res.json().get('detail', res.text)
                    print(f'⚠ Could not complete trip: {detail}')
                    print('  (Trip must be in "active" status)')

        except KeyboardInterrupt:
            print('\n\n⏹ Simulation stopped by user.')
            if failed_pings:
                print(f'   {failed_pings} position ping(s) fixed during the run.')
            sys.exit(0)

        if failed_pings:
            print(f'\n⚠ {failed_pings} position ping(s) failed during the run.')

        if not args.loop:
            break
        loop_count += 1
    print('\nDone.')


if __name__ == '__main__':
    main()
