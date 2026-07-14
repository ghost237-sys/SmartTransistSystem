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
from domains.routing.models import Route, Stop, Trip, TransferStation, LinkedRoute
from domains.booking.models import Booking, LinkedBooking
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
print('🧹 Wiping existing database data database-wide...')

from domains.stage_queue.models import QueueEntry
from domains.passes.models import CommuterPass, PassUsage, CreditTransaction
from domains.booking.models import Booking
from domains.payments.models import Payment
from domains.parcels.models import Parcel, ParcelScanEvent
from domains.routing.models import Trip, Stop, Route
from domains.fleet.models import Vehicle, Fleet
from domains.tenants.models import Tenant
from domains.stage_queue.models import Stage

# Delete transaction/dynamic data database-wide to avoid constraint errors
QueueEntry.objects.all().delete()
Booking.objects.all().delete()
Payment.objects.all().delete()
PassUsage.objects.all().delete()
CreditTransaction.objects.all().delete()
CommuterPass.objects.all().delete()
ParcelScanEvent.objects.all().delete()
Parcel.objects.all().delete()

# Wipe stages, active trips, routes, vehicles, fleets, and tenants
Stage.objects.all().delete()
Trip.objects.all().delete()
Stop.objects.all().delete()
Route.objects.all().delete()
Vehicle.objects.all().delete()
Fleet.objects.all().delete()
Tenant.objects.all().delete()

demo_usernames = [
    'admin', 'supermetro_owner',
    'driver_th047', 'driver_th112', 'driver_ng018', 'driver_th203', 'driver_ki034',
    'conductor_th047', 'conductor_th112', 'conductor_ng018', 'conductor_th203', 'conductor_ki034',
    'commuter_alice', 'commuter_bob', 'commuter_carol', 'investor_commuter', 'commuter_dennis',
]
User.objects.filter(username__in=demo_usernames).delete()

# 2. Tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='supermetro',
    defaults={'name': 'Supermetro'}
)
print(f'✓ Tenant: {tenant.name}')

# 3. Users
def fleet_staff_username(role, fleet_code):
    """e.g. driver_th047 / conductor_ng018 from windshield code TH-047."""
    slug = fleet_code.lower().replace('-', '')
    return f'{role}_{slug}'


def get_or_create_user(username, role, password='demo1234', tenant=None, first_name='', last_name=''):
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'role': role,
            'tenant': tenant,
            'phone_number': '254712345678',
            'password': make_password(password),
            'first_name': first_name,
            'last_name': last_name,
        }
    )
    if not created:
        user.role = role
        user.tenant = tenant
        user.phone_number = '254712345678'
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        user.save()
    return user


def get_or_create_fleet_crew(fleet_code, tenant, driver_names, conductor_names):
    d_first, d_last = driver_names
    c_first, c_last = conductor_names
    driver = get_or_create_user(
        fleet_staff_username('driver', fleet_code),
        User.Role.DRIVER,
        tenant=tenant,
        first_name=d_first,
        last_name=d_last,
    )
    conductor = get_or_create_user(
        fleet_staff_username('conductor', fleet_code),
        User.Role.CONDUCTOR,
        tenant=tenant,
        first_name=c_first,
        last_name=c_last,
    )
    return driver, conductor


super_admin = get_or_create_user('admin', User.Role.SUPER_ADMIN)
fleet_owner = get_or_create_user('supermetro_owner', User.Role.FLEET_OWNER, tenant=tenant)
commuter1   = get_or_create_user('commuter_alice', User.Role.COMMUTER, first_name='Alice', last_name='Mwangi')
commuter2   = get_or_create_user('commuter_bob', User.Role.COMMUTER, first_name='Bob', last_name='Ochieng')
commuter3   = get_or_create_user('commuter_carol', User.Role.COMMUTER, first_name='Carol', last_name='Wambui')
commuter4   = get_or_create_user('investor_commuter', User.Role.COMMUTER, first_name='Investor', last_name='Commuter')
commuter5   = get_or_create_user('commuter_dennis', User.Role.COMMUTER, first_name='Dennis', last_name='Karanja')

super_admin.is_superuser = True
super_admin.is_staff = True
super_admin.save()

print('✓ Users: fleet owner + 4 commuters (crew created per bus below)')

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

# Windshield fleet codes for investor demo
fleet_codes = {
    vehicle1: 'TH-047',
    vehicle2: 'TH-112',
    vehicle3: 'NG-018',
    vehicle4: 'TH-203',
    vehicle5: 'KI-034',
}
for vehicle, code in fleet_codes.items():
    vehicle.fleet_code = code
    vehicle.save(update_fields=['fleet_code'])

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
            (36.9450, -1.1780),
            (36.9281, -1.2092),
            (36.9120, -1.2145),
            (36.8985, -1.2175),
            (36.8914, -1.2219),
            (36.8845, -1.2255),
            (36.8780, -1.2275),
            (36.8670, -1.2470),
            (36.8450, -1.2790),
            (36.8219, -1.2921),
        ], srid=4326),
        'distance_km': 47,
        'estimated_duration_minutes': 60,
        'is_active': True,
    }
)

# All alighting points along Thika Superhighway — stages and informal stops
thika_stop_defs = [
    ('Thika Town Stage', 37.0693, -1.0332),
    ('Kenyatta University', 37.0146, -1.0935),
    ('Ruiru Stage', 36.9616, -1.1469),
    ('Mwiki', 36.9450, -1.1780),
    ('Githurai 45', 36.9281, -1.2092),
    ('Kahawa Sukari', 36.9120, -1.2145),
    ('Kasarani', 36.8985, -1.2175),
    ('Roysambu', 36.8914, -1.2219),
    ('KCA University', 36.8845, -1.2255),
    ('Alsops', 36.8780, -1.2275),
    ('Allsops / Garden City', 36.8670, -1.2470),
    ('Pangani', 36.8450, -1.2790),
    ('Nairobi CBD', 36.8219, -1.2921),
]
thika_stops = []
for seq, (name, lng, lat) in enumerate(thika_stop_defs):
    stop, _ = Stop.objects.update_or_create(
        route=route_nm, sequence=seq,
        defaults={'name': name, 'location': Point(lng, lat, srid=4326)},
    )
    thika_stops.append(stop)

stop_thika = thika_stops[0]
stop_githurai = thika_stops[4]
stop_roysambu = thika_stops[7]
stop_kca = thika_stops[8]
stop_alsops = thika_stops[9]
stop_cbd = thika_stops[-1]

print(f'✓ Route: {route_nm.name} with {route_nm.stops.count()} stops')

# Create reverse route: Nairobi - Thika
route_nt, _ = Route.objects.get_or_create(
    tenant=tenant,
    name='Nairobi - Thika',
    defaults={
        'path': LineString([
            (36.8219, -1.2921),  # Nairobi CBD
            (36.8450, -1.2790),  # Pangani
            (36.8670, -1.2470),  # Allsops / Garden City
            (36.8780, -1.2275),  # Alsops
            (36.8845, -1.2255),  # KCA University
            (36.8914, -1.2219),  # Roysambu
            (36.8985, -1.2175),  # Kasarani
            (36.9120, -1.2145),  # Kahawa Sukari
            (36.9281, -1.2092),  # Githurai 45
            (36.9450, -1.1780),  # Mwiki
            (36.9616, -1.1469),  # Ruiru Stage
            (37.0146, -1.0935),  # Kenyatta University
            (37.0693, -1.0332),  # Thika Town Stage
        ], srid=4326),
        'distance_km': 47,
        'estimated_duration_minutes': 60,
        'is_active': True,
    }
)

# Reverse stops for Nairobi - Thika route
nairobi_thika_stop_defs = [
    ('Nairobi CBD', 36.8219, -1.2921),
    ('Pangani', 36.8450, -1.2790),
    ('Allsops / Garden City', 36.8670, -1.2470),
    ('Alsops', 36.8780, -1.2275),
    ('KCA University', 36.8845, -1.2255),
    ('Roysambu', 36.8914, -1.2219),
    ('Kasarani', 36.8985, -1.2175),
    ('Kahawa Sukari', 36.9120, -1.2145),
    ('Githurai 45', 36.9281, -1.2092),
    ('Mwiki', 36.9450, -1.1780),
    ('Ruiru Stage', 36.9616, -1.1469),
    ('Kenyatta University', 37.0146, -1.0935),
    ('Thika Town Stage', 37.0693, -1.0332),
]
nairobi_thika_stops = []
for seq, (name, lng, lat) in enumerate(nairobi_thika_stop_defs):
    stop, _ = Stop.objects.update_or_create(
        route=route_nt, sequence=seq,
        defaults={'name': name, 'location': Point(lng, lat, srid=4326)},
    )
    nairobi_thika_stops.append(stop)

stop_nairobi_cbd = nairobi_thika_stops[0]
stop_nairobi_githurai = nairobi_thika_stops[8]
stop_nairobi_thika = nairobi_thika_stops[-1]

print(f'✓ Route: {route_nt.name} with {route_nt.stops.count()} stops')

route_ngong, _ = Route.objects.get_or_create(
    tenant=tenant,
    name='Ngong - Nairobi',
    defaults={
        'path': LineString([
            (36.6568, -1.3621),
            (36.6850, -1.3450),
            (36.7200, -1.3200),
            (36.7550, -1.3100),
            (36.7800, -1.3000),
            (36.8050, -1.2950),
            (36.8219, -1.2921),
        ], srid=4326),
        'distance_km': 28,
        'estimated_duration_minutes': 45,
        'is_active': True,
    }
)
ngong_stop_defs = [
    ('Ngong Stage', 36.6568, -1.3621),
    ('Ongata Rongai', 36.6850, -1.3450),
    ('Karen / Hardy', 36.7200, -1.3200),
    ('Bomas of Kenya', 36.7550, -1.3100),
    ('Lavington', 36.7800, -1.3000),
    ('Kenyatta Market', 36.8050, -1.2950),
    ('Nairobi CBD', 36.8219, -1.2921),
]
ngong_stops = []
for seq, (name, lng, lat) in enumerate(ngong_stop_defs):
    stop, _ = Stop.objects.update_or_create(
        route=route_ngong, sequence=seq,
        defaults={'name': name, 'location': Point(lng, lat, srid=4326)},
    )
    ngong_stops.append(stop)
stop_ngong_karen = ngong_stops[2]
stop_ngong_cbd = ngong_stops[-1]
stop_ngong_stage = ngong_stops[0]

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

route_kikuyu, _ = Route.objects.get_or_create(
    tenant=tenant,
    name='Kikuyu - Nairobi',
    defaults={
        'path': LineString([
            (36.6620, -1.2540),
            (36.6800, -1.2600),
            (36.7000, -1.2650),
            (36.7300, -1.2750),
            (36.7500, -1.2800),
            (36.7850, -1.2850),
            (36.8219, -1.2921),
        ], srid=4326),
        'distance_km': 22,
        'estimated_duration_minutes': 40,
        'is_active': True,
    }
)
kikuyu_stop_defs = [
    ('Kikuyu Stage', 36.6620, -1.2540),
    ('Uthiru', 36.6800, -1.2600),
    ('Regen', 36.7000, -1.2650),
    ('Kangemi', 36.7300, -1.2750),
    ('Westlands', 36.7500, -1.2800),
    ('Parklands', 36.7850, -1.2850),
    ('Nairobi CBD', 36.8219, -1.2921),
]
kikuyu_stops = []
for seq, (name, lng, lat) in enumerate(kikuyu_stop_defs):
    stop, _ = Stop.objects.update_or_create(
        route=route_kikuyu, sequence=seq,
        defaults={'name': name, 'location': Point(lng, lat, srid=4326)},
    )
    kikuyu_stops.append(stop)
stop_kikuyu = kikuyu_stops[0]
stop_kikuyu_cbd = kikuyu_stops[-1]

print(f'✓ Routes: {Route.objects.filter(tenant=tenant).count()} active lines')

# Crew roster — one driver + conductor per windshield fleet code
FLEET_CREW_DEFS = [
    ('TH-047', vehicle1, route_nm, ('James', 'Kamau'), ('Wanjiku', 'Njeri')),
    ('TH-112', vehicle2, route_nm, ('Peter', 'Otieno'), ('Mary', 'Akinyi')),
    ('NG-018', vehicle3, route_ngong, ('David', 'Mutua'), ('Lucy', 'Chebet')),
    ('TH-203', vehicle4, route_nm, ('Samuel', 'Kariuki'), ('Grace', 'Wanjiru')),
    ('KI-034', vehicle5, route_kikuyu, ('Joseph', 'Mbugua'), ('Anne', 'Nyambura')),
]

fleet_crew = []
for code, vehicle, route, driver_names, conductor_names in FLEET_CREW_DEFS:
    v_driver, v_conductor = get_or_create_fleet_crew(code, tenant, driver_names, conductor_names)
    vehicle.assigned_driver = v_driver
    vehicle.assigned_conductor = v_conductor
    vehicle.assigned_route = route
    vehicle.save(update_fields=['assigned_driver', 'assigned_conductor', 'assigned_route'])
    fleet_crew.append((code, vehicle, v_driver, v_conductor))
    print(f'  ✓ {code} ({vehicle.plate_number}): {v_driver.username} + {v_conductor.username} → {route.name}')

print(f'✓ Vehicle crew linked: {len(fleet_crew)} buses')

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
    tenant, analytics_schedules,
    fleet_crew[0][2], fleet_crew[0][3],  # TH-047 crew for sample history
)
print(f'✓ Analytics history: {historical_trips} completed trips this month')

# 7. Live demo trips — one active service per assigned bus (TH-203 spare, no live trip)
now = timezone.now()

active_trip_defs = [
    (vehicle1, route_nm, Decimal('150')),
    (vehicle2, route_nm, Decimal('150')),
    (vehicle3, route_ngong, Decimal('120')),
    (vehicle5, route_kikuyu, Decimal('100')),
]

live_trips = []
for vehicle, route, fare in active_trip_defs:
    trip = Trip.objects.create(
        tenant=tenant,
        route=route,
        vehicle=vehicle,
        driver=vehicle.assigned_driver,
        conductor=vehicle.assigned_conductor,
        departure_time=now,
        total_seats=vehicle.capacity,
        fare=fare,
        status='active',
    )
    live_trips.append(trip)

# Create return trips on Nairobi - Thika route for return bookings
return_trip_defs = [
    (vehicle1, route_nt, Decimal('150')),
    (vehicle2, route_nt, Decimal('150')),
]

return_trips = []
for vehicle, route, fare in return_trip_defs:
    trip = Trip.objects.create(
        tenant=tenant,
        route=route,
        vehicle=vehicle,
        driver=vehicle.assigned_driver,
        conductor=vehicle.assigned_conductor,
        departure_time=now + timedelta(hours=2),
        total_seats=vehicle.capacity,
        fare=fare,
        status='active',
    )
    return_trips.append(trip)

trip1, trip2, trip3, trip4 = live_trips

active_count = Trip.objects.filter(tenant=tenant, status='active').count()
print(f'✓ Demo trips: {Trip.objects.filter(tenant=tenant).count()} total ({active_count} active, {historical_trips} completed)')

# 8. Multi-mode bookings with distribution: 60% SINGLE, 20% RETURN, 20% LINK
print('✓ Bookings: generating multi-mode demo bookings...')

def create_single_booking(tenant, trip, commuter, boarding_stop, alighting_stop):
    """Create a single trip booking."""
    booking = Booking.objects.create(
        tenant=tenant,
        trip=trip,
        commuter=commuter,
        booking_type=Booking.BookingType.SINGLE,
        status='confirmed',
        fare_paid=trip.fare,
        boarding_stop=boarding_stop,
        alighting_stop=alighting_stop,
        confirmed_at=timezone.now(),
    )
    booking.generate_ticket_codes()
    booking.save()
    return booking

def create_return_booking(tenant, outbound_trip, return_trip, commuter, outbound_boarding, outbound_alighting, return_boarding, return_alighting):
    """Create an immediate return trip with RETURN_OUTWARD and RETURN_INWARD bookings."""
    # Create outbound booking
    outbound_booking = Booking.objects.create(
        tenant=tenant,
        trip=outbound_trip,
        commuter=commuter,
        booking_type=Booking.BookingType.RETURN_OUTWARD,
        status='confirmed',
        fare_paid=outbound_trip.fare,
        boarding_stop=outbound_boarding,
        alighting_stop=outbound_alighting,
        confirmed_at=timezone.now(),
    )
    outbound_booking.generate_ticket_codes()
    outbound_booking.save()
    
    # Create return booking
    return_booking = Booking.objects.create(
        tenant=tenant,
        trip=return_trip,
        commuter=commuter,
        booking_type=Booking.BookingType.RETURN_INWARD,
        status='confirmed',
        fare_paid=return_trip.fare,
        boarding_stop=return_boarding,
        alighting_stop=return_alighting,
        confirmed_at=timezone.now(),
        linked_booking=outbound_booking,
    )
    return_booking.generate_ticket_codes()
    return_booking.save()
    
    # Link them together
    outbound_booking.linked_booking = return_booking
    outbound_booking.save()
    
    return outbound_booking, return_booking

def create_link_booking(tenant, first_trip, second_trip, commuter, first_boarding, first_alighting, second_boarding, second_alighting, transfer_station):
    """Create a linked trip with LINK_LEG_1 and LINK_LEG_2 bookings."""
    # Create first leg booking
    first_leg = Booking.objects.create(
        tenant=tenant,
        trip=first_trip,
        commuter=commuter,
        booking_type=Booking.BookingType.LINK_LEG_1,
        status='confirmed',
        fare_paid=first_trip.fare,
        boarding_stop=first_boarding,
        alighting_stop=first_alighting,
        confirmed_at=timezone.now(),
        pending_transfer_stop=transfer_station,
    )
    first_leg.generate_ticket_codes()
    first_leg.save()
    
    # Create second leg booking (pending transfer)
    second_leg = Booking.objects.create(
        tenant=tenant,
        trip=second_trip,
        commuter=commuter,
        booking_type=Booking.BookingType.LINK_LEG_2,
        status='pending_transfer',
        fare_paid=second_trip.fare,
        boarding_stop=second_boarding,
        alighting_stop=second_alighting,
        confirmed_at=None,
        linked_booking=first_leg,
        pending_transfer_stop=transfer_station,
    )
    second_leg.save()
    
    # Link them together
    first_leg.linked_booking = second_leg
    first_leg.save()
    
    # Create LinkedBooking record
    linked_booking = LinkedBooking.objects.create(
        first_leg_booking=first_leg,
        second_leg_booking=second_leg,
        transfer_station=transfer_station,
        status='active',
    )
    
    return first_leg, second_leg, linked_booking

# Use the return_trips created earlier for return bookings
additional_trips = return_trips

# Create transfer station for link trips
transfer_station, _ = TransferStation.objects.get_or_create(
    name='Githurai Transfer Hub',
    defaults={
        'location': Point(36.9450, -1.1780, srid=4326),
        'buffer_minutes': 5,
        'is_active': True,
    }
)

# Create linked route for link trips
linked_route, _ = LinkedRoute.objects.get_or_create(
    first_route=route_nm,
    second_route=route_eastleigh,
    transfer_station=transfer_station,
    defaults={
        'first_route_stop': stop_githurai,
        'second_route_stop': stop_alsops,
        'is_active': True,
    }
)

# Create CBD Transfer Hub
transfer_station_cbd, _ = TransferStation.objects.get_or_create(
    name='Nairobi CBD Transfer Hub',
    defaults={
        'location': Point(36.8219, -1.2921, srid=4326),
        'buffer_minutes': 10,
        'is_active': True,
    }
)

# Resolve CBD stops
stop_eastleigh_cbd = Stop.objects.get(route=route_eastleigh, name='Nairobi CBD')

# Link 1: Kikuyu -> Nairobi -> Thika
LinkedRoute.objects.get_or_create(
    first_route=route_kikuyu,
    second_route=route_nt,
    transfer_station=transfer_station_cbd,
    defaults={
        'first_route_stop': stop_kikuyu_cbd,
        'second_route_stop': stop_nairobi_cbd,
        'is_active': True,
    }
)

# Link 2: Ngong -> Nairobi -> Thika
LinkedRoute.objects.get_or_create(
    first_route=route_ngong,
    second_route=route_nt,
    transfer_station=transfer_station_cbd,
    defaults={
        'first_route_stop': stop_ngong_cbd,
        'second_route_stop': stop_nairobi_cbd,
        'is_active': True,
    }
)

# Link 3: Eastleigh -> Nairobi -> Thika
LinkedRoute.objects.get_or_create(
    first_route=route_eastleigh,
    second_route=route_nt,
    transfer_station=transfer_station_cbd,
    defaults={
        'first_route_stop': stop_eastleigh_cbd,
        'second_route_stop': stop_nairobi_cbd,
        'is_active': True,
    }
)

# Create second leg trips for link bookings
link_second_trips = []
for vehicle in [vehicle2, vehicle3]:
    link_trip = Trip.objects.create(
        tenant=tenant,
        route=route_eastleigh,
        vehicle=vehicle,
        driver=vehicle.assigned_driver,
        conductor=vehicle.assigned_conductor,
        departure_time=now + timedelta(hours=1, minutes=30),
        total_seats=vehicle.capacity,
        fare=Decimal('80'),
        status='active',
    )
    link_second_trips.append(link_trip)

# Generate bookings with distribution: 60% SINGLE, 20% RETURN, 20% LINK
commuters = [commuter1, commuter2, commuter3]
total_bookings = 30  # Total bookings to generate
single_count = int(total_bookings * 0.6)  # 18
return_count = int(total_bookings * 0.2)  # 6
link_count = int(total_bookings * 0.2)  # 6

booking_counter = 0

# Generate SINGLE bookings (60%)
for i in range(single_count):
    commuter = commuters[i % len(commuters)]
    trip = live_trips[i % len(live_trips)]
    boarding_stop = trip.route.stops.first()
    alighting_stop = trip.route.stops.last()
    
    create_single_booking(tenant, trip, commuter, boarding_stop, alighting_stop)
    booking_counter += 1

# Generate RETURN bookings (20%)
for i in range(return_count):
    commuter = commuters[i % len(commuters)]
    outbound_trip = live_trips[i % len(live_trips)]
    return_trip = additional_trips[i % len(additional_trips)]
    
    outbound_boarding = outbound_trip.route.stops.first()
    outbound_alighting = outbound_trip.route.stops.last()
    return_boarding = outbound_alighting  # Return from where they alighted
    return_alighting = outbound_boarding  # Return to where they started
    
    create_return_booking(
        tenant, outbound_trip, return_trip, commuter,
        outbound_boarding, outbound_alighting, return_boarding, return_alighting
    )
    booking_counter += 2  # Two bookings per return trip

# Generate LINK bookings (20%)
for i in range(link_count):
    commuter = commuters[i % len(commuters)]
    first_trip = live_trips[i % len(live_trips)]
    second_trip = link_second_trips[i % len(link_second_trips)]
    
    first_boarding = first_trip.route.stops.first()
    first_alighting = stop_githurai  # Transfer at Githurai
    second_boarding = stop_alsops  # Board at Allsops
    second_alighting = stop_cbd  # Final destination
    
    # Use the transfer station for pending_transfer_stop
    create_link_booking(
        tenant, first_trip, second_trip, commuter,
        first_boarding, first_alighting, second_boarding, second_alighting,
        transfer_station  # Use the transfer station
    )
    booking_counter += 2  # Two bookings per link trip

print(f'✓ Bookings: {booking_counter} total ({single_count} single, {return_count*2} return legs, {link_count*2} link legs)')

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
        scanned_by=vehicle2.assigned_conductor,
        vehicle=vehicle2,
        notes='Loaded at Thika Town terminal',
    )

print(f'✓ Parcel: {parcel.tracking_code} ({parcel.status})')

# 10. Demo commuter locations (each user starts at a different stop)
def assign_demo_location(user, stop, route_name):
    user.demo_latitude = stop.location.y
    user.demo_longitude = stop.location.x
    user.demo_location_label = f'{stop.name} · {route_name}'
    user.save(update_fields=['demo_latitude', 'demo_longitude', 'demo_location_label'])

assign_demo_location(commuter1, stop_thika, route_nm.name)
assign_demo_location(commuter2, stop_ngong_karen, route_ngong.name)
assign_demo_location(commuter3, stop_kikuyu, route_kikuyu.name)
assign_demo_location(commuter4, stop_thika, route_nm.name)
assign_demo_location(commuter5, stop_ngong_stage, route_ngong.name)

print('✓ Demo commuter locations:')
print(f'  commuter_alice   → {commuter1.demo_location_label} (all Thika Rd stops available as destinations)')
print(f'  commuter_bob     → {commuter2.demo_location_label}')
print(f'  commuter_carol   → {commuter3.demo_location_label}')
print(f'  commuter_dennis  → {commuter5.demo_location_label}')

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
print('  Fleet Owner:   supermetro_owner')
print('  Commuters:     commuter_alice · commuter_bob · commuter_carol')
print()
print('CREW BY FLEET CODE (driver / conductor):')
for code, vehicle, v_driver, v_conductor in fleet_crew:
    active = ' · LIVE' if vehicle.id in {t.vehicle_id for t in live_trips} else ' · spare'
    print(f'  {code} ({vehicle.plate_number}){active}')
    print(f'    Driver:    {v_driver.username} ({v_driver.first_name} {v_driver.last_name})')
    print(f'    Conductor: {v_conductor.username} ({v_conductor.first_name} {v_conductor.last_name})')
print()
print('END-TO-END COMMUTER DEMO:')
print('  1. Log in as commuter_alice (starts @ Thika Town)')
print('  2. Find ride → pick a bus (e.g. TH-047) → choose alighting stop → pay (mock M-Pesa)')
print('  3. Log in as conductor_th047 → Manifest → see confirmed booking → Scan ticket to board')
print('  4. Log in as driver_th047 → Manifest → same passenger list updates live')
print()
print('PARCEL TRACKING:')
print(f'  Code: {parcel.tracking_code}')
print()
print('COMMUTER START LOCATIONS (re-login after seed for JWT demo location):')
print('  commuter_alice @ Thika Town      → Thika Rd buses (TH-047, TH-112)')
print('  commuter_bob   @ Karen / Hardy   → Ngong route bus NG-018')
print('  commuter_carol @ Kikuyu Stage    → Kikuyu route bus KI-034')
print()
print('GPS SIMULATION (optional — live movement during demo):')
print(f'  docker compose exec backend python scripts/simulate_gps.py {trip1.id} driver_th047')
print(f'  docker compose exec backend python scripts/simulate_gps.py {trip3.id} driver_ng018')
print('═' * 55)

# Auto-setup GPS so find-ride works immediately after seed
print()
print('Setting up demo GPS positions...')
from domains.tracking.redis_client import set_vehicle_position

ROUTE_POSITIONS = {
    'Thika - Nairobi': [(-1.2219, 36.8914, 32), (-1.1469, 36.9616, 38)],
    'Ngong - Nairobi': [(-1.3350, 36.6900, 28)],
    'Kikuyu - Nairobi': [(-1.2580, 36.6800, 30)],
}
route_counters = {}
for trip in live_trips:
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
    print(f'  ✓ {trip.vehicle.fleet_code} GPS set ({lat:.4f}, {lng:.4f})')
print('✓ GPS ready for find-ride (valid 1 hour)')