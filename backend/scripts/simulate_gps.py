"""
GPS simulation — moves a bus along the trip's route stops and broadcasts live positions.

Run inside Docker:
  docker compose exec backend python scripts/simulate_gps.py <trip_id> <driver_username>

Full demo (depart → drive all stops → complete):
  docker compose exec backend python scripts/simulate_gps.py <trip_id> driver_kamau \\
    --conductor conductor_wanjiku --auto-lifecycle

Options:
  --interval SECONDS     Seconds between position pings (default: 3)
  --steps-per-leg N      Interpolation points between each stop (default: 25)
  --pause-at-stops SEC   Pause at each stop before continuing (default: 5)
  --conductor USER       Conductor username for depart/complete (default: conductor_wanjiku)
  --auto-lifecycle       Mark trip departed at start and completed at end
  --password PASS        Login password (default: demo1234)
  --base-url URL         API base URL (default: http://localhost:8000)
"""
import argparse
import math
import os
import sys
import time

import requests


def parse_args():
    parser = argparse.ArgumentParser(description='Simulate a bus moving along a trip route.')
    parser.add_argument('trip_id', help='Trip UUID to simulate')
    parser.add_argument('driver_username', help='Driver username assigned to the trip')
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


def main():
    args = parse_args()

    import django
    sys.path.insert(0, '/app')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

    from domains.routing.models import Trip

    base_url = args.base_url.rstrip('/')

    try:
        trip = Trip.all_objects.select_related('route', 'vehicle', 'driver').get(id=args.trip_id)
    except Trip.DoesNotExist:
        print(f'✗ Trip not found: {args.trip_id}')
        print('  Run: docker compose exec backend python scripts/seed_demo.py')
        sys.exit(1)

    if trip.driver and trip.driver.username != args.driver_username:
        print(
            f'⚠ Warning: trip driver is "{trip.driver.username}", '
            f'not "{args.driver_username}". Telemetry may be rejected.'
        )

    if trip.status == 'completed':
        print(f'✗ Trip is already completed. Pick a scheduled/departed trip (e.g. from seed_demo.py).')
        sys.exit(1)

    if trip.status == 'cancelled':
        print('✗ Trip is cancelled.')
        sys.exit(1)

    vehicle_id = str(trip.vehicle_id)
    waypoints = load_route_stops(trip)

    print('═' * 60)
    print(f'🚌 GPS Simulation — {trip.route.name}')
    print(f'   Vehicle:   {trip.vehicle.plate_number}')
    print(f'   Trip ID:   {args.trip_id}')
    print(f'   Status:    {trip.status}')
    print(f'   Stops:     {len(waypoints)}')
    print(f'   Interval:  {args.interval}s')
    print(f'   Lifecycle: {"auto depart → complete" if args.auto_lifecycle else "manual"}')
    print('═' * 60)
    print()
    print('Open the commuter tracking page for this trip to watch live.')
    print('Press Ctrl+C to stop early.')
    print()

    driver_token = get_token(base_url, args.driver_username, args.password)
    token_refresh_at = time.time() + 240
    print(f'✓ Authenticated as driver: {args.driver_username}')

    conductor_token = None
    if args.auto_lifecycle:
        conductor_token = get_token(base_url, args.conductor, args.password)
        print(f'✓ Authenticated as conductor: {args.conductor}')

        if trip.status == 'scheduled':
            res = depart_trip(base_url, conductor_token, args.trip_id)
            if res.status_code == 200:
                print('✓ Trip marked as departed')
                trip.refresh_from_db()
            else:
                detail = res.json().get('detail', res.text)
                print(f'✗ Could not depart trip: {detail}')
                sys.exit(1)
        elif trip.status == 'departed':
            print('• Trip already departed — continuing simulation')
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
                    driver_token = get_token(base_url, args.driver_username, args.password)
                    token_refresh_at = time.time() + 240
                    print('\n↻ Driver token refreshed')

                speed = max(20, min(80, avg_speed + (step % 7) - 3))
                res = post_position(base_url, driver_token, vehicle_id, args.trip_id, lat, lng, speed)
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
            res = complete_trip(base_url, conductor_token, args.trip_id)
            if res.status_code == 200:
                data = res.json()
                print(
                    f'✓ Trip completed — {data.get("passengers_boarded", 0)} boarded, '
                    f'KES {data.get("total_revenue", 0)} revenue'
                )
            else:
                detail = res.json().get('detail', res.text)
                print(f'⚠ Could not complete trip: {detail}')
                print('  (Trip may need to be in "departed" status)')

    except KeyboardInterrupt:
        print('\n\n⏹ Simulation stopped by user.')
        if failed_pings:
            print(f'   {failed_pings} position ping(s) failed during the run.')
        sys.exit(0)

    if failed_pings:
        print(f'\n⚠ {failed_pings} position ping(s) failed during the run.')
    print('\nDone.')


if __name__ == '__main__':
    main()
