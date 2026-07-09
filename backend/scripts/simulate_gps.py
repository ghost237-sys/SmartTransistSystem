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
"""
import argparse
import math
import os
import sys
import time
import threading
import queue

import requests


def parse_args():
    parser = argparse.ArgumentParser(description='Simulate a bus moving along a trip route.')
    parser.add_argument('trip_id', help='Trip UUID to simulate')
    parser.add_argument('driver_username', help='Driver username assigned to the trip')
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

    message_queue.put(f'DONE:{trip_id}')


def main():
    args = parse_args()

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
    print('\nDone.')


if __name__ == '__main__':
    main()
