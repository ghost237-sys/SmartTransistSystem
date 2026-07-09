"""
Setup script for investor demo - simulates GPS positions for active vehicles

Run inside Docker:
  docker compose exec backend python scripts/setup_demo_gps.py
"""
import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from domains.tracking.redis_client import set_vehicle_position
from domains.routing.models import Trip, Stop
from datetime import datetime

# GPS positions per route — buses placed along the corridor so ETAs differ by commuter location
ROUTE_POSITIONS = {
    'Thika - Nairobi': [
        (-1.2219, 36.8914, 32),   # Roysambu / TRM
        (-1.1469, 36.9616, 38),   # Ruiru
    ],
    'Ngong - Nairobi': [
        (-1.3350, 36.6900, 28),   # Between Ngong & Karen
    ],
    'Kikuyu - Nairobi': [
        (-1.2580, 36.6800, 30),   # Near Kikuyu / Uthiru
    ],
    'Eastleigh - CBD': [
        (-1.2780, 36.8400, 22),   # Eastleigh corridor
    ],
}

print("🚀 Setting up GPS positions for investor demo...")

active_trips = Trip.objects.filter(status='active').select_related('vehicle', 'route').order_by('route__name')
print(f"Found {active_trips.count()} active trips")

route_counters = {}

for trip in active_trips:
    positions = ROUTE_POSITIONS.get(trip.route.name, [(-1.286389, 36.817223, 25)])
    idx = route_counters.get(trip.route.name, 0)
    lat, lng, speed = positions[idx % len(positions)]
    route_counters[trip.route.name] = idx + 1

    set_vehicle_position(
        vehicle_id=str(trip.vehicle_id),
        latitude=lat,
        longitude=lng,
        speed_kmh=speed,
        recorded_at=datetime.now().isoformat(),
        ttl_seconds=3600,
    )
    print(
        f"✓ {trip.vehicle.fleet_code or trip.vehicle.plate_number} "
        f"on {trip.route.name}: {lat:.4f}, {lng:.4f} ({speed} km/h)"
    )

print("\n📍 Demo commuters (re-seed to refresh locations):")
from domains.accounts.models import User
for u in User.objects.filter(username__startswith='commuter_').exclude(demo_location_label=''):
    print(f"  {u.username} @ {u.demo_location_label} ({u.demo_latitude:.4f}, {u.demo_longitude:.4f})")

print("\n✅ Demo GPS setup complete! (positions valid for 1 hour)")
print("\n⚠️  For live movement during demo, keep simulate_gps.py running:")
print("   docker compose exec backend python scripts/simulate_gps.py <trip_id> driver_kamau")
