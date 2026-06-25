"""
Demo seed script — run with:
  docker compose exec backend python scripts/seed_demo.py

Populates the database with realistic demo data for the investor presentation.
Wipes existing demo data first so it's safe to run multiple times.
"""
import os
import django
import sys

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import random
from datetime import datetime, time, timedelta, date
from decimal import Decimal

from django.utils import timezone
from django.contrib.auth.hashers import make_password

from domains.tenants.models import Tenant
from domains.accounts.models import User
from domains.fleet.models import Fleet, Vehicle
from domains.routing.models import Route, Stop, Trip
from domains.booking.models import Booking
from domains.parcels.models import Parcel, ParcelScanEvent
from domains.payments.models import Payment
from domains.parcels.utils import generate_tracking_code, generate_qr_token


def create_completed_trip(tenant, route, vehicle, driver, conductor, departure_dt, fare, passenger_count):
    """Create a completed trip with cash walk-up boarded passengers."""
    trip = Trip.objects.create(
        tenant=tenant,
        route=route,
        vehicle=vehicle,
        driver=driver,
        conductor=conductor,
        departure_time=departure_dt,
        total_seats=vehicle.capacity,
        fare=fare,
        status='completed',
    )
    bookings = [
        Booking(
            tenant=tenant,
            trip=trip,
            status='boarded',
            fare_paid=fare,
            boarded_at=departure_dt + timedelta(minutes=2 + i),
        )
        for i in range(passenger_count)
    ]
    Booking.objects.bulk_create(bookings)
    return trip


def seed_monthly_analytics(tenant, schedules, driver, conductor):
    """
    Backfill completed trips for the current calendar month so the owner
    dashboard shows realistic revenue, occupancy, and route breakdowns.
    """
    random.seed(42)
    today = timezone.localdate()
    month_start = today.replace(day=1)
    now = timezone.now()
    trips_created = 0

    day = month_start
    while day <= today:
        is_weekend = day.weekday() >= 5

        for schedule in schedules:
            if is_weekend:
                trips_today = random.randint(*schedule['weekend_trips'])
            else:
                trips_today = random.randint(*schedule['weekday_trips'])

            for _ in range(trips_today):
                hour = random.choice(schedule['hours'])
                minute = random.choice([0, 15, 30, 45])
                departure = timezone.make_aware(datetime.combine(day, time(hour, minute)))

                if departure >= now - timedelta(minutes=30):
                    continue

                vehicle = random.choice(schedule['vehicles'])
                occupancy = random.uniform(*schedule['occupancy'])
                passenger_count = max(
                    1,
                    min(int(vehicle.capacity * occupancy), vehicle.capacity),
                )

                create_completed_trip(
                    tenant=tenant,
                    route=schedule['route'],
                    vehicle=vehicle,
                    driver=driver,
                    conductor=conductor,
                    departure_dt=departure,
                    fare=schedule['fare'],
                    passenger_count=passenger_count,
                )
                trips_created += 1

        day += timedelta(days=1)

    return trips_created


print('🌱 Seeding demo data...')

# 1. Wipe old data first
try:
    existing_tenant = Tenant.objects.get(slug='supermetro')
    print('🧹 Wiping existing demo data for Supermetro...')

    ParcelScanEvent.objects.filter(parcel__tenant=existing_tenant).delete()
    Parcel.objects.filter(tenant=existing_tenant).delete()
    Payment.objects.filter(tenant=existing_tenant).delete()
    Booking.objects.filter(tenant=existing_tenant).delete()
    Trip.objects.filter(tenant=existing_tenant).delete()
    Stop.objects.filter(route__tenant=existing_tenant).delete()
    Route.objects.filter(tenant=existing_tenant).delete()
    Vehicle.objects.filter(tenant=existing_tenant).delete()
    Fleet.objects.filter(tenant=existing_tenant).delete()

    existing_tenant.delete()
except Tenant.DoesNotExist:
    ParcelScanEvent.objects.all().delete()
    Parcel.objects.all().delete()

demo_usernames = [
    'admin', 'supermetro_owner', 'driver_kamau',
    'conductor_wanjiku', 'commuter_alice', 'commuter_bob', 'commuter_carol'
]
User.objects.filter(username__in=demo_usernames).delete()

# 2. Tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='supermetro',
    defaults={'name': 'Supermetro'}
)
print(f'✓ Tenant: {tenant.name}')

# 3. Users
def get_or_create_user(username, role, password='demo1234', tenant=None):
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'role': role,
            'tenant': tenant,
            'phone_number': '254712345678',
            'password': make_password(password),
        }
    )
    if not created:
        user.role = role
        user.tenant = tenant
        user.phone_number = '254712345678'
        user.save()
    return user

super_admin = get_or_create_user('admin', User.Role.SUPER_ADMIN)
fleet_owner = get_or_create_user('supermetro_owner', User.Role.FLEET_OWNER, tenant=tenant)
driver      = get_or_create_user('driver_kamau', User.Role.DRIVER, tenant=tenant)
conductor   = get_or_create_user('conductor_wanjiku', User.Role.CONDUCTOR, tenant=tenant)
commuter1   = get_or_create_user('commuter_alice', User.Role.COMMUTER)
commuter2   = get_or_create_user('commuter_bob', User.Role.COMMUTER)
commuter3   = get_or_create_user('commuter_carol', User.Role.COMMUTER)

super_admin.is_superuser = True
super_admin.is_staff = True
super_admin.save()

print(f'✓ Users: {[u.username for u in [super_admin, fleet_owner, driver, conductor, commuter1, commuter2, commuter3]]}')

# 4. Fleet & Vehicles
fleet, _ = Fleet.objects.get_or_create(
    tenant=tenant,
    name='Supermetro Main Fleet'
)

vehicle1, _ = Vehicle.objects.get_or_create(
    plate_number='KDA 001A',
    defaults={
        'tenant': tenant,
        'fleet': fleet,
        'vehicle_type': Vehicle.VehicleType.BUS,
        'capacity': 49,
        'is_active': True,
        'insurance_expiry': date.today() + timedelta(days=180),
        'inspection_expiry': date.today() + timedelta(days=90),
    }
)

vehicle2, _ = Vehicle.objects.get_or_create(
    plate_number='KDA 002B',
    defaults={
        'tenant': tenant,
        'fleet': fleet,
        'vehicle_type': Vehicle.VehicleType.MATATU,
        'capacity': 14,
        'is_active': True,
        'insurance_expiry': date.today() + timedelta(days=12),
        'inspection_expiry': date.today() + timedelta(days=45),
    }
)

vehicle3, _ = Vehicle.objects.get_or_create(
    plate_number='KDB 103C',
    defaults={
        'tenant': tenant,
        'fleet': fleet,
        'vehicle_type': Vehicle.VehicleType.MATATU,
        'capacity': 14,
        'is_active': True,
        'insurance_expiry': date.today() + timedelta(days=60),
        'inspection_expiry': date.today() - timedelta(days=3),
    }
)

vehicle4, _ = Vehicle.objects.get_or_create(
    plate_number='KDB 204D',
    defaults={
        'tenant': tenant,
        'fleet': fleet,
        'vehicle_type': Vehicle.VehicleType.BUS,
        'capacity': 49,
        'is_active': True,
        'insurance_expiry': date.today() + timedelta(days=120),
        'inspection_expiry': date.today() + timedelta(days=75),
    }
)

vehicle5, _ = Vehicle.objects.get_or_create(
    plate_number='KDB 305E',
    defaults={
        'tenant': tenant,
        'fleet': fleet,
        'vehicle_type': Vehicle.VehicleType.SHUTTLE,
        'capacity': 25,
        'is_active': True,
        'insurance_expiry': date.today() + timedelta(days=200),
        'inspection_expiry': date.today() + timedelta(days=30),
    }
)

# Refresh compliance dates on re-runs (get_or_create skips defaults when row exists)
vehicle2.insurance_expiry = date.today() + timedelta(days=12)
vehicle2.inspection_expiry = date.today() + timedelta(days=45)
vehicle2.save(update_fields=['insurance_expiry', 'inspection_expiry'])
vehicle3.inspection_expiry = date.today() - timedelta(days=3)
vehicle3.save(update_fields=['inspection_expiry'])

print(f'✓ Vehicles: {Vehicle.objects.filter(tenant=tenant).count()} in fleet')

# 5. Routes & Stops — Thika Superhighway
from django.contrib.gis.geos import LineString, Point

route_nm, _ = Route.objects.get_or_create(
    tenant=tenant,
    name='Thika - Nairobi',
    defaults={
        'path': LineString([
            (37.0693, -1.0332),
            (37.0146, -1.0935),
            (36.9616, -1.1469),
            (36.9281, -1.2092),
            (36.8914, -1.2219),
            (36.8219, -1.2921),
        ], srid=4326),
        'distance_km': 47,
        'estimated_duration_minutes': 60,
        'is_active': True,
    }
)

stop_thika, _ = Stop.objects.get_or_create(
    route=route_nm, sequence=0,
    defaults={'name': 'Thika Town Stage', 'location': Point(37.0693, -1.0332, srid=4326)}
)
stop_ku, _ = Stop.objects.get_or_create(
    route=route_nm, sequence=1,
    defaults={'name': 'Kenyatta University', 'location': Point(37.0146, -1.0935, srid=4326)}
)
stop_ruiru, _ = Stop.objects.get_or_create(
    route=route_nm, sequence=2,
    defaults={'name': 'Ruiru Stage', 'location': Point(36.9616, -1.1469, srid=4326)}
)
stop_githurai, _ = Stop.objects.get_or_create(
    route=route_nm, sequence=3,
    defaults={'name': 'Githurai 45', 'location': Point(36.9281, -1.2092, srid=4326)}
)
stop_roysambu, _ = Stop.objects.get_or_create(
    route=route_nm, sequence=4,
    defaults={'name': 'Roysambu / TRM', 'location': Point(36.8914, -1.2219, srid=4326)}
)
stop_cbd, _ = Stop.objects.get_or_create(
    route=route_nm, sequence=5,
    defaults={'name': 'Nairobi CBD', 'location': Point(36.8219, -1.2921, srid=4326)}
)

print(f'✓ Route: {route_nm.name} with {route_nm.stops.count()} stops')

route_ngong, _ = Route.objects.get_or_create(
    tenant=tenant,
    name='Ngong - Nairobi',
    defaults={
        'path': LineString([
            (36.6568, -1.3621),
            (36.7200, -1.3200),
            (36.7800, -1.3000),
            (36.8219, -1.2921),
        ], srid=4326),
        'distance_km': 28,
        'estimated_duration_minutes': 45,
        'is_active': True,
    }
)
Stop.objects.get_or_create(
    route=route_ngong, sequence=0,
    defaults={'name': 'Ngong Stage', 'location': Point(36.6568, -1.3621, srid=4326)},
)
Stop.objects.get_or_create(
    route=route_ngong, sequence=1,
    defaults={'name': 'Karen / Hardy', 'location': Point(36.7200, -1.3200, srid=4326)},
)
Stop.objects.get_or_create(
    route=route_ngong, sequence=2,
    defaults={'name': 'Nairobi CBD', 'location': Point(36.8219, -1.2921, srid=4326)},
)

route_eastleigh, _ = Route.objects.get_or_create(
    tenant=tenant,
    name='Eastleigh - CBD',
    defaults={
        'path': LineString([
            (36.8476, -1.2747),
            (36.8350, -1.2830),
            (36.8219, -1.2921),
        ], srid=4326),
        'distance_km': 8,
        'estimated_duration_minutes': 25,
        'is_active': True,
    }
)
Stop.objects.get_or_create(
    route=route_eastleigh, sequence=0,
    defaults={'name': 'Eastleigh Stage', 'location': Point(36.8476, -1.2747, srid=4326)},
)
Stop.objects.get_or_create(
    route=route_eastleigh, sequence=1,
    defaults={'name': 'Muthurwa', 'location': Point(36.8350, -1.2830, srid=4326)},
)
Stop.objects.get_or_create(
    route=route_eastleigh, sequence=2,
    defaults={'name': 'Nairobi CBD', 'location': Point(36.8219, -1.2921, srid=4326)},
)

print(f'✓ Routes: {Route.objects.filter(tenant=tenant).count()} active lines')

# 6. Historical analytics (month-to-date completed trips)
analytics_schedules = [
    {
        'route': route_nm,
        'vehicles': [vehicle1, vehicle4],
        'fare': Decimal('150'),
        'hours': [6, 7, 8, 12, 17, 18, 19],
        'weekday_trips': (3, 5),
        'weekend_trips': (2, 3),
        'occupancy': (0.78, 0.97),
    },
    {
        'route': route_nm,
        'vehicles': [vehicle2, vehicle3],
        'fare': Decimal('150'),
        'hours': [6, 7, 17, 18, 19],
        'weekday_trips': (2, 4),
        'weekend_trips': (1, 2),
        'occupancy': (0.68, 0.95),
    },
    {
        'route': route_ngong,
        'vehicles': [vehicle2, vehicle3, vehicle5],
        'fare': Decimal('120'),
        'hours': [6, 7, 8, 17, 18],
        'weekday_trips': (2, 3),
        'weekend_trips': (1, 2),
        'occupancy': (0.58, 0.88),
    },
    {
        'route': route_eastleigh,
        'vehicles': [vehicle3, vehicle5],
        'fare': Decimal('80'),
        'hours': [7, 8, 9, 12, 16, 17, 18],
        'weekday_trips': (4, 6),
        'weekend_trips': (2, 3),
        'occupancy': (0.62, 0.93),
    },
]

historical_trips = seed_monthly_analytics(
    tenant, analytics_schedules, driver, conductor
)
print(f'✓ Analytics history: {historical_trips} completed trips this month')

# 7. Live demo trips (booking, GPS, conductor scan)
now = timezone.now()

trip1 = Trip.objects.create(
    tenant=tenant,
    route=route_nm,
    vehicle=vehicle1,
    driver=driver,
    conductor=conductor,
    departure_time=now.replace(hour=7, minute=0, second=0, microsecond=0) + timedelta(days=1),
    total_seats=vehicle1.capacity,
    fare=Decimal('150'),
    status='scheduled',
)

trip2 = Trip.objects.create(
    tenant=tenant,
    route=route_nm,
    vehicle=vehicle2,
    driver=driver,
    conductor=conductor,
    departure_time=now + timedelta(hours=1),
    total_seats=vehicle2.capacity,
    fare=Decimal('150'),
    status='scheduled',
)

print(f'✓ Demo trips: {Trip.objects.filter(tenant=tenant).count()} total ({historical_trips} completed)')

# 8. One confirmed booking on trip1 (conductor scan demo)
booking_demo, created = Booking.objects.get_or_create(
    tenant=tenant,
    trip=trip1,
    commuter=commuter1,
    defaults={
        'status': 'confirmed',
        'fare_paid': Decimal('150'),
        'confirmed_at': now,
        'alighting_stop': stop_cbd,
    }
)
if created:
    booking_demo.generate_ticket_codes()
    booking_demo.save()
    Payment.objects.get_or_create(
        tenant=tenant,
        booking=booking_demo,
        defaults={
            'amount': Decimal('150'),
            'phone_number': '254712345678',
            'checkout_request_id': f'DEMO-CONFIRMED-{booking_demo.id}',
            'status': 'success',
        }
    )
else:
    booking_demo.status = 'confirmed'
    booking_demo.fare_paid = Decimal('150')
    booking_demo.confirmed_at = now
    booking_demo.alighting_stop = stop_cbd
    if not booking_demo.short_code:
        booking_demo.generate_ticket_codes()
    booking_demo.save()

print(f'✓ Demo booking short code: {booking_demo.short_code}')
print(f'✓ Demo booking QR token:   {booking_demo.qr_code_token}')

# 9. Parcel in transit
parcel, created = Parcel.objects.get_or_create(
    tracking_code='KE-DEMO1',
    defaults={
        'tenant': tenant,
        'qr_token': generate_qr_token(),
        'sender_name': 'John Kamau',
        'sender_phone': '254712345678',
        'recipient_name': 'Mary Wanjiku',
        'recipient_phone': '254798765432',
        'trip': trip2,
        'origin_stop': stop_thika,
        'destination_stop': stop_cbd,
        'description': 'Electronics - Laptop',
        'weight_kg': 2.5,
        'declared_value': 85000,
        'fee': 500,
        'status': 'in_transit',
    }
)
if created:
    ParcelScanEvent.objects.create(
        parcel=parcel,
        event_type='loaded',
        scanned_by=conductor,
        vehicle=vehicle2,
        notes='Loaded at Thika Town terminal',
    )

print(f'✓ Parcel: {parcel.tracking_code} ({parcel.status})')

from domains.fleet.analytics import get_fleet_analytics

today = timezone.localdate()
month_start = today.replace(day=1)
analytics = get_fleet_analytics(tenant, month_start, today)

print()
print('═' * 55)
print('✅ Demo data ready!')
print()
print('ANALYTICS PREVIEW (month to date):')
print(f'  Revenue:     KES {analytics["total_revenue"]:,.0f}')
print(f'  Passengers:  {analytics["total_passengers"]:,}')
print(f'  Trips:       {analytics["total_trips"]}')
for route in sorted(analytics['routes'], key=lambda r: r['total_revenue'], reverse=True):
    print(
        f'  · {route["route_name"]}: KES {route["total_revenue"]:,.0f} · '
        f'{route["total_trips"]} trips · {route["average_occupancy_percent"]}% occupancy'
    )
print()
print('LOGIN CREDENTIALS (password: demo1234 for all):')
print('  Super Admin:   admin')
print('  Fleet Owner:   supermetro_owner')
print('  Driver:        driver_kamau')
print('  Conductor:     conductor_wanjiku')
print('  Commuter:      commuter_alice / commuter_bob / commuter_carol')
print()
print('DEMO BOOKING:')
print(f'  Short code:  {booking_demo.short_code}')
print(f'  QR token:    {booking_demo.qr_code_token}')
print()
print('PARCEL TRACKING:')
print(f'  Code: {parcel.tracking_code}')
print()
print('GPS SIMULATION (run in separate terminal):')
print(f'  docker compose exec backend python scripts/simulate_gps.py {trip2.id} driver_kamau --auto-lifecycle')
print()
print('  GPS only (no depart/complete):')
print(f'  docker compose exec backend python scripts/simulate_gps.py {trip2.id} driver_kamau')
print('═' * 55)