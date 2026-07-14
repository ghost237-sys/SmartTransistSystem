"""
Booking simulation script — test different booking types via Django shell.

Usage:
  docker compose exec backend python scripts/simulate_booking.py --type single
  docker compose exec backend python scripts/simulate_booking.py --type return
  docker compose exec backend python scripts/simulate_booking.py --type link
"""
import argparse
import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from domains.booking.models import Booking, LinkedBooking
from domains.routing.models import Trip, Route, Stop
from domains.accounts.models import User
from django.utils import timezone
from django.db import models
from datetime import timedelta

def parse_args():
    parser = argparse.ArgumentParser(description='Simulate booking creation via Django shell')
    parser.add_argument('--type', choices=['single', 'return', 'link', 'list'], default='list', help='Booking type')
    parser.add_argument('--username', default='commuter_alice', help='Commuter username')
    return parser.parse_args()

def list_bookings():
    """List all bookings in the system."""
    print('═' * 60)
    print('📋 Current Bookings')
    print('═' * 60)
    print()
    
    single = Booking.objects.filter(booking_type='single').count()
    return_out = Booking.objects.filter(booking_type='return_outward').count()
    return_in = Booking.objects.filter(booking_type='return_inward').count()
    link_1 = Booking.objects.filter(booking_type='link_leg_1').count()
    link_2 = Booking.objects.filter(booking_type='link_leg_2').count()
    
    print(f'SINGLE: {single}')
    print(f'RETURN_OUTWARD: {return_out}')
    print(f'RETURN_INWARD: {return_in}')
    print(f'LINK_LEG_1: {link_1}')
    print(f'LINK_LEG_2: {link_2}')
    print(f'Total: {single + return_out + return_in + link_1 + link_2}')
    print()
    
    # Show return bookings with their linked pairs
    print('═' * 60)
    print('🔄 Return Booking Pairs')
    print('═' * 60)
    print()
    
    return_bookings = Booking.objects.filter(
        booking_type='return_outward'
    ).select_related('linked_booking', 'trip__route', 'commuter')[:5]
    
    for booking in return_bookings:
        print(f'Commuter: {booking.commuter.username}')
        print(f'  Outbound: {booking.trip.route.name} (Trip {booking.trip.id[:8]}...)')
        print(f'  Status: {booking.status}')
        if booking.linked_booking:
            print(f'  Return: {booking.linked_booking.trip.route.name} (Trip {booking.linked_booking.trip.id[:8]}...)')
            print(f'  Return Status: {booking.linked_booking.status}')
        print()

def create_single_booking(username):
    """Create a single trip booking."""
    print('═' * 60)
    print('🎫 Creating SINGLE Booking')
    print('═' * 60)
    print()
    
    try:
        commuter = User.objects.get(username=username, role='commuter')
    except User.DoesNotExist:
        print(f'✗ User {username} not found')
        return
    
    # Get an active trip
    trip = Trip.objects.filter(status='active').select_related('route', 'vehicle').first()
    if not trip:
        print('✗ No active trips found')
        return
    
    print(f'Commuter: {commuter.username}')
    print(f'Trip: {trip.route.name} (Trip {trip.id[:8]}...)')
    print(f'Vehicle: {trip.vehicle.plate_number}')
    print(f'Fare: KES {trip.fare}')
    print()
    
    # Get stops
    stops = trip.route.stops.all()
    if len(stops) < 2:
        print('✗ Need at least 2 stops')
        return
    
    boarding_stop = stops.first()
    alighting_stop = stops.last()
    
    print(f'Boarding: {boarding_stop.name}')
    print(f'Alighting: {alighting_stop.name}')
    print()
    
    # Create booking
    booking = Booking.objects.create(
        tenant=commuter.tenant,
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
    
    print(f'✓ SINGLE booking created!')
    print(f'  Booking ID: {booking.id[:8]}...')
    print(f'  Short Code: {booking.short_code}')
    print(f'  Status: {booking.status}')

def create_return_booking(username):
    """Create a return trip booking."""
    print('═' * 60)
    print('🎫 Creating RETURN Booking')
    print('═' * 60)
    print()
    
    try:
        commuter = User.objects.get(username=username, role='commuter')
    except User.DoesNotExist:
        print(f'✗ User {username} not found')
        return
    
    # Find outbound route (Thika - Nairobi) and return route (Nairobi - Thika)
    outbound_route = Route.objects.filter(
        name='Thika - Nairobi',
        is_active=True
    ).annotate(
        trip_count=models.Count('trips', filter=models.Q(trips__status='active')),
        stop_count=models.Count('stops')
    ).first()
    
    return_route = Route.objects.filter(
        name='Nairobi - Thika',
        is_active=True
    ).annotate(
        trip_count=models.Count('trips', filter=models.Q(trips__status='active')),
        stop_count=models.Count('stops')
    ).first()
    
    if not outbound_route or outbound_route.trip_count < 1 or outbound_route.stop_count < 2:
        print('✗ No active Thika - Nairobi route with trips and stops found')
        return
    
    if not return_route or return_route.trip_count < 1 or return_route.stop_count < 2:
        print('✗ No active Nairobi - Thika route with trips and stops found')
        print('   Hint: Run seed_demo.py to create the reverse route')
        return
    
    # Get outbound trip from Thika - Nairobi route
    outbound_trip = Trip.objects.filter(
        route=outbound_route,
        status='active'
    ).select_related('vehicle').order_by('departure_time').first()
    
    # Get return trip from Nairobi - Thika route
    return_trip = Trip.objects.filter(
        route=return_route,
        status='active'
    ).select_related('vehicle').order_by('departure_time').first()
    
    if not outbound_trip:
        print('✗ No active outbound trip found')
        return
    
    if not return_trip:
        print('✗ No active return trip found')
        return
    
    print(f'Commuter: {commuter.username}')
    print(f'Outbound Route: {outbound_route.name}')
    print(f'Return Route: {return_route.name}')
    print(f'Outbound Trip: {str(outbound_trip.id)[:8]}... (Departure: {outbound_trip.departure_time})')
    print(f'Return Trip: {str(return_trip.id)[:8]}... (Departure: {return_trip.departure_time})')
    print(f'Total Fare: KES {outbound_trip.fare + return_trip.fare}')
    print()
    
    # Get stops for outbound route
    outbound_stops = outbound_route.stops.all()
    if len(outbound_stops) < 2:
        print('✗ Need at least 2 stops on outbound route')
        return
    
    # Get stops for return route
    return_stops = return_route.stops.all()
    if len(return_stops) < 2:
        print('✗ Need at least 2 stops on return route')
        return
    
    # Outbound: Thika → Nairobi
    outbound_boarding = outbound_stops.first()
    outbound_alighting = outbound_stops.last()
    
    # Return: Nairobi → Thika
    return_boarding = return_stops.first()  # Nairobi CBD
    return_alighting = return_stops.last()  # Thika Town
    
    print(f'Outbound: {outbound_boarding.name} → {outbound_alighting.name}')
    print(f'Return: {return_boarding.name} → {return_alighting.name}')
    print()
    
    # Create outbound booking (Thika → Nairobi)
    outbound_booking = Booking.objects.create(
        tenant=outbound_trip.tenant,
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
    
    # Create return booking (Nairobi → Thika)
    return_booking = Booking.objects.create(
        tenant=return_trip.tenant,
        trip=return_trip,
        commuter=commuter,
        booking_type=Booking.BookingType.RETURN_INWARD,
        status='confirmed',
        fare_paid=return_trip.fare,
        boarding_stop=return_boarding,  # Board at Nairobi CBD
        alighting_stop=return_alighting,  # Alight at Thika Town
        confirmed_at=timezone.now(),
        linked_booking=outbound_booking,
    )
    return_booking.generate_ticket_codes()
    return_booking.save()
    
    # Link them together
    outbound_booking.linked_booking = return_booking
    outbound_booking.save()
    
    print(f'✓ RETURN booking created!')
    print(f'  Outbound Booking ID: {str(outbound_booking.id)[:8]}...')
    print(f'  Outbound Short Code: {outbound_booking.short_code}')
    print(f'  Return Booking ID: {str(return_booking.id)[:8]}...')
    print(f'  Return Short Code: {return_booking.short_code}')
    print(f'  Total Fare: KES {outbound_booking.fare_paid + return_booking.fare_paid}')

def create_link_booking(username):
    """Create a linked trip booking."""
    print('═' * 60)
    print('🎫 Creating LINK Booking')
    print('═' * 60)
    print()
    
    print('✗ LINK bookings require transfer station setup')
    print('   Use seed_demo.py to create link bookings with transfer stations')
    print('   Current link bookings from seed:')
    
    link_bookings = Booking.objects.filter(
        booking_type='link_leg_1'
    ).select_related('linked_booking', 'trip__route')[:3]
    
    for booking in link_bookings:
        print(f'  - {booking.trip.route.name} → {booking.linked_booking.trip.route.name if booking.linked_booking else "None"}')

def main():
    args = parse_args()
    
    if args.type == 'list':
        list_bookings()
    elif args.type == 'single':
        create_single_booking(args.username)
    elif args.type == 'return':
        create_return_booking(args.username)
    elif args.type == 'link':
        create_link_booking(args.username)
    
    print()
    print('═' * 60)
    print('✅ Done!')
    print('═' * 60)

if __name__ == '__main__':
    main()
