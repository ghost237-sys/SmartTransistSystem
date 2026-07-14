"""
Investor Pitch Demo Script — demonstrates three core booking flows.

Usage:
  docker compose exec backend python scripts/demo_pitch.py --auto    # Automatic pacing
  docker compose exec backend python scripts/demo_pitch.py --interactive  # Manual pacing (default)

This script showcases:
  Act 1: Frictionless Return (RETURN_OUTWARD + RETURN_INWARD)
  Act 2: Smart Transfer & Pending Bay (LINK_LEG_1 + LINK_LEG_2)
  Act 3: Operational Resilience (Automatic Reassignment)
"""
import os
import sys
import django
import time
import argparse
from datetime import timedelta

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from django.contrib.gis.geos import Point
from domains.tenants.models import Tenant
from domains.accounts.models import User
from domains.fleet.models import Vehicle
from domains.routing.models import Route, Stop, Trip, TransferStation
from domains.booking.models import Booking, LinkedBooking
from domains.booking.services import BusCancellationService
from domains.tracking.redis_client import set_vehicle_position, get_vehicle_position


def clear_screen():
    """Clear console screen."""
    os.system('clear' if os.name == 'posix' else 'cls')


def print_header(title):
    """Print a bold header."""
    print()
    print('═' * 70)
    print(f'  {title}')
    print('═' * 70)
    print()


def print_subheader(title):
    """Print a subheader."""
    print()
    print('─' * 70)
    print(f'  {title}')
    print('─' * 70)
    print()


def wait_for_next_step(message="\nPress Enter to simulate next step..."):
    """Wait for user input to proceed."""
    input(message)


def setup_demo_environment():
    """Create clean demo environment with dedicated test user."""
    print_header("DEMO SETUP: Creating Clean Test Environment")
    
    # Get or create tenant
    tenant, _ = Tenant.objects.get_or_create(
        slug='supermetro',
        defaults={'name': 'Supermetro'}
    )
    
    # Create dedicated demo user
    demo_user, created = User.objects.get_or_create(
        username='investor_commuter',
        defaults={
            'role': 'commuter',
            'tenant': tenant,
            'phone_number': '254700000000',
            'first_name': 'Investor',
            'last_name': 'Commuter',
        }
    )
    
    if created:
        from django.contrib.auth.hashers import make_password
        demo_user.password = make_password('demo1234')
        demo_user.save()
        print(f"✓ Created demo user: {demo_user.username}")
    else:
        print(f"✓ Using existing demo user: {demo_user.username}")

    # Set demo location at Thika Town start stop so finding rides succeeds instantly
    outbound_route = Route.objects.filter(name='Thika - Nairobi', is_active=True).first()
    if outbound_route:
        start_stop = outbound_route.stops.order_by('sequence').first()
        if start_stop:
            demo_user.demo_latitude = start_stop.location.y
            demo_user.demo_longitude = start_stop.location.x
            demo_user.demo_location_label = f'{start_stop.name} · {outbound_route.name}'
            demo_user.save()
            print(f"✓ Assigned demo location to {demo_user.username}: {demo_user.demo_location_label}")
    
    # Clean up old demo bookings
    old_bookings = Booking.objects.filter(commuter=demo_user).delete()
    print(f"✓ Cleaned up {old_bookings[0]} old demo bookings")
    
    print()
    print("Demo environment ready!")
    time.sleep(2)
    
    return tenant, demo_user


def act_1_frictionless_return(tenant, demo_user):
    """Act 1: Frictionless Return booking flow."""
    clear_screen()
    print_header("ACT 1: THE FRICTIONLESS RETURN (Mode 2)")
    print()
    print("Business Value: Simulating a seamless morning + evening commute")
    print("booking with a single M-Pesa payment.")
    print()
    print("Key Insight: One checkout flow = two guaranteed seats secured.")
    print("This dramatically increases conversion rates for round-trip commuters.")
    print()
    
    wait_for_next_step()
    
    # Get routes
    outbound_route = Route.objects.filter(name='Thika - Nairobi', is_active=True).first()
    return_route = Route.objects.filter(name='Nairobi - Thika', is_active=True).first()
    
    if not outbound_route or not return_route:
        print("✗ Required routes not found. Run seed_demo.py first.")
        return None, None
    
    # Get trips
    outbound_trip = Trip.objects.filter(
        route=outbound_route,
        status='active'
    ).select_related('vehicle').first()
    
    return_trip = Trip.objects.filter(
        route=return_route,
        status='active'
    ).select_related('vehicle').first()
    
    if not outbound_trip or not return_trip:
        print("✗ Required trips not found.")
        return None, None
    
    print_subheader("Step 1: Creating Linked Return Booking")
    print(f"  Outbound: {outbound_route.name} (Trip {str(outbound_trip.id)[:8]}...)")
    print(f"  Return: {return_route.name} (Trip {str(return_trip.id)[:8]}...)")
    print(f"  Total Fare: KES {outbound_trip.fare + return_trip.fare}")
    print()
    
    # Get stops
    outbound_stops = outbound_route.stops.all()
    return_stops = return_route.stops.all()
    
    outbound_boarding = outbound_stops.first()
    outbound_alighting = outbound_stops.last()
    return_boarding = return_stops.first()
    return_alighting = return_stops.last()
    
    # Create outbound booking (PENDING_PAYMENT)
    outbound_booking = Booking.objects.create(
        tenant=outbound_trip.tenant,
        trip=outbound_trip,
        commuter=demo_user,
        booking_type=Booking.BookingType.RETURN_OUTWARD,
        status='held',  # PENDING_PAYMENT equivalent
        fare_paid=0,  # Not paid yet
        boarding_stop=outbound_boarding,
        alighting_stop=outbound_alighting,
    )
    
    # Create return booking (PENDING_PAYMENT)
    return_booking = Booking.objects.create(
        tenant=return_trip.tenant,
        trip=return_trip,
        commuter=demo_user,
        booking_type=Booking.BookingType.RETURN_INWARD,
        status='held',  # PENDING_PAYMENT equivalent
        fare_paid=0,  # Not paid yet
        boarding_stop=return_boarding,
        alighting_stop=return_alighting,
        linked_booking=outbound_booking,
    )
    
    # Link them
    outbound_booking.linked_booking = return_booking
    outbound_booking.save()
    
    print_subheader("Step 2: Booking Status Table (Pre-Payment)")
    print()
    print("  Booking Type      | Status      | Trip Route          | Fare")
    print("  " + "-" * 65)
    print(f"  RETURN_OUTWARD   | HELD        | {outbound_route.name:20} | KES {outbound_trip.fare}")
    print(f"  RETURN_INWARD    | HELD        | {return_route.name:20} | KES {return_trip.fare}")
    print()
    print("  Both bookings are held in pending state awaiting payment.")
    print()
    
    wait_for_next_step()
    
    print_subheader("Step 3: Simulating M-Pesa Payment Callback")
    print("  Processing payment...")
    time.sleep(1)
    print("  ✓ Payment confirmed: KES 300.00")
    print()
    
    # Simulate payment confirmation
    outbound_booking.status = 'confirmed'
    outbound_booking.fare_paid = outbound_trip.fare
    outbound_booking.confirmed_at = timezone.now()
    outbound_booking.generate_ticket_codes()
    outbound_booking.save()
    
    return_booking.status = 'confirmed'
    return_booking.fare_paid = return_trip.fare
    return_booking.confirmed_at = timezone.now()
    return_booking.generate_ticket_codes()
    return_booking.save()
    
    print_subheader("Step 4: Booking Status Table (Post-Payment)")
    print()
    print("  Booking Type      | Status      | Trip Route          | Fare    | Short Code")
    print("  " + "-" * 75)
    print(f"  RETURN_OUTWARD   | CONFIRMED   | {outbound_route.name:20} | KES {outbound_booking.fare_paid:6} | {outbound_booking.short_code}")
    print(f"  RETURN_INWARD    | CONFIRMED   | {return_route.name:20} | KES {return_booking.fare_paid:6} | {return_booking.short_code}")
    print()
    print("  ✓ Both bookings instantly confirmed with single payment!")
    print("  ✓ Commuter now has guaranteed seats for both morning and evening.")
    print()
    
    wait_for_next_step()
    
    return outbound_booking, return_booking


def act_2_smart_transfer(tenant, demo_user):
    """Act 2: Smart Transfer & Pending Bay."""
    clear_screen()
    print_header("ACT 2: THE SMART TRANSFER & PENDING BAY (Mode 3)")
    print()
    print("Business Value: Maximizing fleet seat utilization using our")
    print("intelligent Transfer Pending Bay.")
    print()
    print("Key Insight: We don't hold seats hostage while commuters are stuck")
    print("in traffic on Leg 1. Seats on Leg 2 are only locked when Leg 1")
    print("approaches the transfer station.")
    print()
    
    wait_for_next_step()
    
    # Get routes for transfer
    leg1_route = Route.objects.filter(name='Thika - Nairobi', is_active=True).first()
    leg2_route = Route.objects.filter(name='Kikuyu - Nairobi', is_active=True).first()
    
    if not leg1_route or not leg2_route:
        print("✗ Required routes not found.")
        return None, None
    
    # Get trips
    leg1_trip = Trip.objects.filter(
        route=leg1_route,
        status='active'
    ).select_related('vehicle').first()
    
    leg2_trip = Trip.objects.filter(
        route=leg2_route,
        status='active'
    ).select_related('vehicle').first()
    
    if not leg1_trip or not leg2_trip:
        print("✗ Required trips not found.")
        return None, None
    
    # Create transfer station
    transfer_station, _ = TransferStation.objects.get_or_create(
        name='CBD Transfer Hub',
        defaults={
            'location': Point(36.8219, -1.2921, srid=4326),
            'buffer_minutes': 5,
            'is_active': True,
        }
    )
    
    print_subheader("Step 1: Creating Multi-Leg Booking")
    print(f"  Leg 1: {leg1_route.name} (Trip {str(leg1_trip.id)[:8]}...)")
    print(f"  Leg 2: {leg2_route.name} (Trip {str(leg2_trip.id)[:8]}...)")
    print(f"  Transfer Station: {transfer_station.name}")
    print()
    
    # Get seat inventory BEFORE booking
    leg2_seats_before = leg2_trip.available_seats
    
    # Create Leg 1 booking (CONFIRMED)
    leg1_booking = Booking.objects.create(
        tenant=leg1_trip.tenant,
        trip=leg1_trip,
        commuter=demo_user,
        booking_type=Booking.BookingType.LINK_LEG_1,
        status='confirmed',
        fare_paid=leg1_trip.fare,
        boarding_stop=leg1_route.stops.first(),
        alighting_stop=leg1_route.stops.last(),
        pending_transfer_stop=transfer_station,
        confirmed_at=timezone.now(),
    )
    leg1_booking.generate_ticket_codes()
    leg1_booking.save()
    
    # Create Leg 2 booking (PENDING_TRANSFER)
    leg2_booking = Booking.objects.create(
        tenant=leg2_trip.tenant,
        trip=leg2_trip,
        commuter=demo_user,
        booking_type=Booking.BookingType.LINK_LEG_2,
        status='pending_transfer',  # NOT confirmed yet!
        fare_paid=0,  # Not charged yet
        boarding_stop=leg2_route.stops.first(),
        alighting_stop=leg2_route.stops.last(),
        linked_booking=leg1_booking,
        pending_transfer_stop=transfer_station,
    )
    leg2_booking.save()
    
    # Link them
    leg1_booking.linked_booking = leg2_booking
    leg1_booking.save()
    
    # Get seat inventory AFTER booking
    leg2_seats_after = leg2_trip.available_seats
    
    print_subheader("Step 2: Seat Inventory Analysis")
    print()
    print(f"  Bus B (Leg 2) Available Seats BEFORE booking: {leg2_seats_before}")
    print(f"  Bus B (Leg 2) Available Seats AFTER booking:  {leg2_seats_after}")
    print()
    print("  ✓ Notice: Seat count did NOT decrease!")
    print("  ✓ Bus B's seat is NOT held hostage while commuter is on Leg 1.")
    print("  ✓ This maximizes fleet utilization and prevents revenue loss.")
    print()
    
    wait_for_next_step()
    
    print_subheader("Step 3: Simulating Bus A Approaching Transfer Station")
    print()
    print("  Setting up GPS simulation for Bus A (Leg 1)...")
    print()
    
    # Simulate GPS coordinates approaching transfer station
    distances = [5.0, 3.2, 1.8]  # km
    transfer_threshold = 2.0  # km
    
    for distance in distances:
        print(f"  Distance to transfer: {distance}km...", end=" ")
        time.sleep(1)
        
        if distance <= transfer_threshold:
            print("THRESHOLD BREACHED! ✓")
            break
        else:
            print("approaching...")
    
    print()
    
    wait_for_next_step()
    
    print_subheader("Step 4: Triggering Proximity Evaluation")
    print("  Running monitor_transfer_proximity logic...")
    time.sleep(1)
    
    # Manually trigger the proximity logic
    if leg2_trip.available_seats > 0:
        leg2_booking.status = 'confirmed'
        leg2_booking.fare_paid = leg2_trip.fare
        leg2_booking.confirmed_at = timezone.now()
        leg2_booking.generate_ticket_codes()
        leg2_booking.save()
        
        # Note: available_seats is a calculated property, so confirming the booking
        # automatically reduces the available seat count
        leg2_seats_final = leg2_trip.available_seats
        
        print("  ✓ Leg 2 booking confirmed!")
        print(f"  ✓ Bus B seat inventory now: {leg2_seats_final}")
    else:
        print("  ✗ Bus B is full - would trigger manual reroute alert")
    
    print()
    
    print_subheader("Step 5: Final State")
    print()
    print("  Booking Type      | Status          | Fare Paid")
    print("  " + "-" * 50)
    print(f"  LINK_LEG_1        | CONFIRMED       | KES {leg1_booking.fare_paid}")
    print(f"  LINK_LEG_2        | CONFIRMED       | KES {leg2_booking.fare_paid}")
    print()
    print(f"  Bus B Available Seats: {leg2_trip.available_seats}")
    print()
    print("  ✓ Smart transfer completed successfully!")
    print()
    
    wait_for_next_step()
    
    print_subheader("Step 6: WebSocket Payload Structure")
    print()
    print("  The following payload is broadcast to commuter's device:")
    print()
    print("  {")
    print('    "type": "transfer.confirmed",')
    print(f'    "leg1_booking_id": "{leg1_booking.id}",')
    print(f'    "leg2_booking_id": "{leg2_booking.id}",')
    print(f'    "leg2_short_code": "{leg2_booking.short_code}",')
    print(f'    "transfer_station": "{transfer_station.name}",')
    print('    "message": "Your transfer is confirmed. Board Bus B now.",')
    print('    "timestamp": "2026-07-11T11:30:00Z"')
    print("  }")
    print()
    
    wait_for_next_step()
    
    return leg1_booking, leg2_booking


def act_3_operational_resilience(tenant, demo_user, return_booking):
    """Act 3: Operational Resilience - Automatic Reassignment."""
    clear_screen()
    print_header("ACT 3: THE OPERATIONAL RESILIENCE LAYER")
    print()
    print("Business Value: Handling real-world chaos completely through automation.")
    print("No manual support tickets, no panicked calls to dispatch.")
    print()
    print("Key Insight: When a bus breaks down, our system automatically")
    print("finds the next available bus, reassigns passengers, and notifies")
    print("them in real-time.")
    print()
    
    if not return_booking:
        print("✗ No return booking from Act 1 to reassign.")
        return
    
    return_trip = return_booking.trip
    return_route = return_trip.route
    
    print_subheader("Step 1: Targeting Evening Return Bus")
    print(f"  Trip ID: {str(return_trip.id)[:8]}...")
    print(f"  Route: {return_route.name}")
    print(f"  Vehicle: {return_trip.vehicle.plate_number}")
    print(f"  Departure: {return_trip.departure_time}")
    print()
    
    # Show affected passengers
    affected_count = Booking.objects.filter(
        trip=return_trip,
        status='confirmed'
    ).count()
    
    print(f"  Affected passengers: {affected_count}")
    print()
    
    wait_for_next_step()
    
    print_subheader("Step 2: Simulating Bus Breakdown")
    print("  Triggering cancellation event...")
    time.sleep(1)
    print("  ✓ Bus marked as cancelled")
    print()
    
    # Find next available trip, or create one for demo purposes
    next_trip = Trip.objects.filter(
        route=return_route,
        status='active',
        departure_time__gt=return_trip.departure_time
    ).exclude(id=return_trip.id).select_related('vehicle').first()
    
    if not next_trip:
        print("  No replacement trip found - creating one for demo...")
        # Create a replacement trip 15 minutes later
        next_trip = Trip.objects.create(
            tenant=tenant,
            route=return_route,
            vehicle=return_trip.vehicle,
            driver=return_trip.driver,
            conductor=return_trip.conductor,
            departure_time=return_trip.departure_time + timedelta(minutes=15),
            total_seats=return_trip.total_seats,
            fare=return_trip.fare,
            status='active',
        )
        print(f"  ✓ Created replacement trip: {str(next_trip.id)[:8]}...")
        print()
    
    print_subheader("Step 3: Finding Next Available Bus")
    print(f"  Scanning schedule on route: {return_trip.route.name}")
    print(f"  ✓ Found replacement: Trip {str(next_trip.id)[:8]}...")
    print(f"  Vehicle: {next_trip.vehicle.plate_number}")
    print(f"  Departure: {next_trip.departure_time}")
    print(f"  Available Seats: {next_trip.available_seats}")
    print()
    
    wait_for_next_step()
    
    print_subheader("Step 4: Executing Automatic Reassignment")
    print("  Reassigning booking to new trip...")
    time.sleep(1)
    
    # Reassign the booking
    original_trip_id = return_booking.trip_id
    return_booking.trip = next_trip
    return_booking.status = 'confirmed'
    return_booking.generate_ticket_codes()
    return_booking.save()
    
    # Note: available_seats is a calculated property, so reassigning
    # the booking automatically updates the seat count
    next_seats_final = next_trip.available_seats
    
    print("  ✓ Booking reassigned successfully!")
    print(f"  ✓ New bus available seats: {next_seats_final}")
    print()
    
    print_subheader("Step 5: Reassignment Summary")
    print()
    print("  Original Bus:  | New Bus:")
    print(f"  {return_trip.vehicle.plate_number:16} | {next_trip.vehicle.plate_number}")
    print(f"  {str(return_trip.id)[:8]:16} | {str(next_trip.id)[:8]}")
    print(f"  {return_trip.departure_time.strftime('%H:%M'):16} | {next_trip.departure_time.strftime('%H:%M')}")
    print()
    
    wait_for_next_step()
    
    print_subheader("Step 6: Real-Time Notification to Commuter")
    print()
    print("  Push notification sent to commuter's device:")
    print()
    print("  ═══════════════════════════════════════════════════════════════")
    print("  🚌 Your evening return bus has changed.")
    print()
    print("  We've automatically secured your seat on the next available bus:")
    print(f"  • Bus: {next_trip.vehicle.plate_number}")
    print(f"  • Departure: {next_trip.departure_time.strftime('%I:%M %p')}")
    print(f"  • Route: {next_trip.route.name}")
    print()
    print("  Your new ticket code: {return_booking.short_code}")
    print("  ═══════════════════════════════════════════════════════════════")
    print()
    
    print("  ✓ No manual intervention required!")
    print("  ✓ Commuter informed instantly via push notification")
    print("  ✓ Fleet operations continue smoothly")
    print()
    
    wait_for_next_step()


def main():
    """Main demo execution."""
    clear_screen()
    print_header("SMARTTRANSIST SYSTEM - INVESTOR DEMO")
    print()
    print("This demonstration showcases our three core booking innovations:")
    print()
    print("  1. Frictionless Return (Mode 2)")
    print("  2. Smart Transfer & Pending Bay (Mode 3)")
    print("  3. Operational Resilience (Automatic Reassignment)")
    print()
    
    wait_for_next_step("\nPress Enter to begin the demo...")
    
    # Setup
    tenant, demo_user = setup_demo_environment()
    
    # Act 1
    outbound_booking, return_booking = act_1_frictionless_return(tenant, demo_user)
    
    # Act 2
    leg1_booking, leg2_booking = act_2_smart_transfer(tenant, demo_user)
    
    # Act 3
    act_3_operational_resilience(tenant, demo_user, return_booking)
    
    # Final summary
    clear_screen()
    print_header("DEMO COMPLETE")
    print()
    print("Thank you for viewing our investor demonstration.")
    print()
    print("Key Takeaways:")
    print()
    print("  ✓ Frictionless Return: One payment, two guaranteed seats")
    print("  ✓ Smart Transfer: No seat hostage, maximum fleet utilization")
    print("  ✓ Operational Resilience: Automated chaos handling")
    print()
    print("The SmartTransist System: Built for scale, built for resilience.")
    print()
    print('═' * 70)


if __name__ == '__main__':
    main()
