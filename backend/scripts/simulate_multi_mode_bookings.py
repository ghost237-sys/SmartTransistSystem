"""
Multi-mode booking simulation script — tests all three booking modes:
1. Single trip (Mode 1)
2. Return trip - immediate (Mode 2a) and open (Mode 2b)
3. Linked trip with transfer bay (Mode 3)

Run with:
  docker compose exec backend python scripts/simulate_multi_mode_bookings.py

Requirements:
- Run seed_demo.py first to populate demo data
- Ensure backend services are running
"""
import os
import django
import sys
import requests
import time
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from domains.tenants.models import Tenant
from domains.accounts.models import User
from domains.fleet.models import Fleet, Vehicle
from domains.routing.models import Route, Stop, Trip
from domains.booking.models import Booking, LinkedBooking, OpenReturnCredit


class MultiModeBookingSimulator:
    def __init__(self, base_url='http://localhost:8000'):
        self.base_url = base_url.rstrip('/')
        self.commuter_token = None
        self.results = []

    def get_token(self, username, password='demo1234'):
        """Get authentication token"""
        res = requests.post(
            f'{self.base_url}/api/auth/token/',
            json={'username': username, 'password': password},
            timeout=10,
        )
        if res.status_code != 200:
            raise RuntimeError(f'Login failed for {username}: {res.text}')
        return res.json()['access']

    def setup_demo_data(self):
        """Setup demo data for simulation"""
        print('═' * 60)
        print('🔧 Setting up demo data...')
        print('═' * 60)
        
        try:
            tenant = Tenant.objects.first()
            if not tenant:
                raise RuntimeError('No tenant found. Run seed_demo.py first.')
            
            # Get existing commuter from seed
            commuter = User.objects.filter(username='commuter_alice', role=User.Role.COMMUTER).first()
            if not commuter:
                raise RuntimeError('Commuter not found. Run seed_demo.py first.')
            
            # Get routes and vehicles directly
            routes = Route.objects.filter(tenant=tenant)
            if routes.count() < 1:
                raise RuntimeError(f'Need at least 1 route. Found {routes.count()}. Run seed_demo.py first.')
            
            vehicles = Vehicle.objects.filter(tenant=tenant)
            if vehicles.count() < 2:
                raise RuntimeError(f'Need at least 2 vehicles. Found {vehicles.count()}. Run seed_demo.py first.')
            
            routes_list = list(routes[:1])
            
            # Create a second route for testing if only one exists
            if routes.count() == 1:
                print('📝 Creating second test route for simulation...')
                original_route = routes_list[0]
                
                # Clone the route with different name
                second_route = Route.objects.create(
                    tenant=tenant,
                    name=f'{original_route.name} (Return)',
                    path=original_route.path,
                    distance_km=original_route.distance_km,
                    estimated_duration_minutes=original_route.estimated_duration_minutes,
                    max_pickup_distance_km=original_route.max_pickup_distance_km,
                    is_active=True,
                )
                
                # Clone stops in reverse order
                original_stops = list(original_route.stops.order_by('sequence'))
                for i, stop in enumerate(reversed(original_stops)):
                    from domains.routing.models import Stop
                    new_stop = Stop.objects.create(
                        route=second_route,
                        name=stop.name,
                        location=stop.location,
                        sequence=i,
                    )
                
                routes_list.append(second_route)
                print(f'✓ Created second route: {second_route.name}')
            else:
                routes_list = list(routes[:2])
            
            vehicles_list = list(vehicles[:2])
            
            # Get drivers and conductors from existing users
            drivers = User.objects.filter(tenant=tenant, role=User.Role.DRIVER)
            conductors = User.objects.filter(tenant=tenant, role=User.Role.CONDUCTOR)
            
            # Create crew if not enough exist
            if drivers.count() < 2:
                print('📝 Creating additional drivers for simulation...')
                for i in range(2 - drivers.count()):
                    driver = User.objects.create(
                        tenant=tenant,
                        username=f'sim_driver_{i+1}',
                        email=f'driver{i+1}@sim.com',
                        first_name=f'Sim',
                        last_name=f'Driver {i+1}',
                        role=User.Role.DRIVER,
                        phone_number=f'+25471100000{i}',
                        password='demo1234',
                    )
                    print(f'✓ Created driver: {driver.username}')
            
            if conductors.count() < 2:
                print('📝 Creating additional conductors for simulation...')
                for i in range(2 - conductors.count()):
                    conductor = User.objects.create(
                        tenant=tenant,
                        username=f'sim_conductor_{i+1}',
                        email=f'conductor{i+1}@sim.com',
                        first_name=f'Sim',
                        last_name=f'Conductor {i+1}',
                        role=User.Role.CONDUCTOR,
                        phone_number=f'+25471200000{i}',
                        password='demo1234',
                    )
                    print(f'✓ Created conductor: {conductor.username}')
            
            # Refresh queries after creating users
            drivers = User.objects.filter(tenant=tenant, role=User.Role.DRIVER)
            conductors = User.objects.filter(tenant=tenant, role=User.Role.CONDUCTOR)
            
            drivers_list = list(drivers[:2])
            conductors_list = list(conductors[:2])
            
            # Create new active trips for simulation
            now = timezone.now()
            single_trip = Trip.objects.create(
                tenant=tenant,
                route=routes_list[0],
                vehicle=vehicles_list[0],
                driver=drivers_list[0],
                conductor=conductors_list[0],
                departure_time=now + timedelta(minutes=5),
                fare=Decimal('50.00'),
                status='active',
                total_seats=vehicles_list[0].capacity,
            )
            
            outbound_trip = Trip.objects.create(
                tenant=tenant,
                route=routes_list[0],
                vehicle=vehicles_list[0],
                driver=drivers_list[0],
                conductor=conductors_list[0],
                departure_time=now + timedelta(minutes=10),
                fare=Decimal('50.00'),
                status='active',
                total_seats=vehicles_list[0].capacity,
            )
            
            return_trip = Trip.objects.create(
                tenant=tenant,
                route=routes_list[1],
                vehicle=vehicles_list[1],
                driver=drivers_list[1],
                conductor=conductors_list[1],
                departure_time=now + timedelta(hours=6),
                fare=Decimal('60.00'),
                status='active',
                total_seats=vehicles_list[1].capacity,
            )
            
            first_leg_trip = Trip.objects.create(
                tenant=tenant,
                route=routes_list[0],
                vehicle=vehicles_list[0],
                driver=drivers_list[0],
                conductor=conductors_list[0],
                departure_time=now + timedelta(minutes=15),
                fare=Decimal('50.00'),
                status='active',
                total_seats=vehicles_list[0].capacity,
            )
            
            second_leg_trip = Trip.objects.create(
                tenant=tenant,
                route=routes_list[1],
                vehicle=vehicles_list[1],
                driver=drivers_list[1],
                conductor=conductors_list[1],
                departure_time=now + timedelta(minutes=45),
                fare=Decimal('60.00'),
                status='active',
                total_seats=vehicles_list[1].capacity,
            )
            
            # Get transfer station (use CBD as common transfer point)
            transfer_station = None
            for route in routes_list:
                cbd_stop = route.stops.filter(name__icontains='cbd').first()
                if cbd_stop:
                    transfer_station = cbd_stop
                    break
            
            if not transfer_station:
                # Fallback to middle stop of first route
                stops_list = list(routes_list[0].stops.order_by('sequence'))
                if len(stops_list) >= 2:
                    transfer_station = stops_list[len(stops_list) // 2]
                elif len(stops_list) == 1:
                    transfer_station = stops_list[0]
                else:
                    # Create a fallback transfer station
                    print('📝 Creating fallback transfer station...')
                    from domains.routing.models import Stop
                    from django.contrib.gis.geos import Point
                    # Use the midpoint of the route path
                    if routes_list[0].path:
                        midpoint = routes_list[0].path.interpolate(0.5)
                        transfer_station = Stop.objects.create(
                            route=routes_list[0],
                            name='Transfer Station',
                            location=midpoint,
                            sequence=0,
                        )
                    else:
                        # Fallback to a default point
                        transfer_station = Stop.objects.create(
                            route=routes_list[0],
                            name='Transfer Station',
                            location=Point(-1.286389, 36.817223),  # Nairobi CBD coordinates
                            sequence=0,
                        )
                    print(f'✓ Created transfer station: {transfer_station.name}')
            
            print(f'✓ Demo data setup complete')
            print(f'  Commuter: {commuter.username}')
            print(f'  Routes: {routes_list[0].name}, {routes_list[1].name}')
            print(f'  Transfer station: {transfer_station.name if transfer_station else "N/A"}')
            print(f'  Single trip: {single_trip.route.name} (KES {single_trip.fare})')
            print(f'  Outbound trip: {outbound_trip.route.name} (KES {outbound_trip.fare})')
            print(f'  Return trip: {return_trip.route.name} (KES {return_trip.fare})')
            print()
            
            return {
                'tenant': tenant,
                'commuter': commuter,
                'routes': routes_list,
                'vehicles': vehicles_list,
                'transfer_station': transfer_station,
                'single_trip': single_trip,
                'outbound_trip': outbound_trip,
                'return_trip': return_trip,
                'first_leg_trip': first_leg_trip,
                'second_leg_trip': second_leg_trip,
            }
            
        except Exception as e:
            print(f'✗ Setup failed: {e}')
            raise

    def test_single_trip(self, data):
        """Test Mode 1: Single trip booking"""
        print('═' * 60)
        print('🎫 MODE 1: Single Trip Booking')
        print('═' * 60)
        
        try:
            self.commuter_token = self.get_token(data['commuter'].username)
            print(f'✓ Authenticated as commuter: {data["commuter"].username}')
            
            trip = data['single_trip']
            boarding_stop = trip.route.stops.first()
            alighting_stop = trip.route.stops.last()
            
            payload = {
                'trip_mode': 'single',
                'trip_id': str(trip.id),
                'phone_number': '+254700000000',
                'payment_method': 'mpesa',
                'boarding_stop_id': str(boarding_stop.id) if boarding_stop else None,
                'alighting_stop_id': str(alighting_stop.id) if alighting_stop else None,
            }
            
            print(f'📝 Booking single trip: {trip.route.name}')
            print(f'   Fare: KES {trip.fare}')
            
            res = requests.post(
                f'{self.base_url}/api/bookings/multi-mode/',
                json=payload,
                headers={'Authorization': f'Bearer {self.commuter_token}'},
                timeout=10,
            )
            
            if res.status_code == 201:
                result = res.json()
                print(f'✓ Single trip booking successful')
                print(f'   Booking ID: {result.get("booking_id")}')
                print(f'   Status: {result.get("status")}')
                print(f'   Message: {result.get("message")}')
                self.results.append(('Single Trip', 'SUCCESS', result.get('booking_id')))
            else:
                print(f'✗ Single trip booking failed: {res.text}')
                self.results.append(('Single Trip', 'FAILED', None))
            
        except Exception as e:
            print(f'✗ Single trip test error: {e}')
            self.results.append(('Single Trip', 'ERROR', str(e)))
        
        print()

    def test_return_immediate(self, data):
        """Test Mode 2a: Return trip - immediate booking"""
        print('═' * 60)
        print('🎫 MODE 2a: Return Trip - Immediate Booking')
        print('═' * 60)
        
        try:
            outbound_trip = data['outbound_trip']
            return_trip = data['return_trip']
            
            outbound_boarding = outbound_trip.route.stops.first()
            outbound_alighting = outbound_trip.route.stops.last()
            return_boarding = return_trip.route.stops.first()
            return_alighting = return_trip.route.stops.last()
            
            payload = {
                'trip_mode': 'return_immediate',
                'outbound_trip_id': str(outbound_trip.id),
                'return_trip_id': str(return_trip.id),
                'phone_number': '+254700000000',
                'payment_method': 'mpesa',
                'outbound_boarding_stop_id': str(outbound_boarding.id) if outbound_boarding else None,
                'outbound_alighting_stop_id': str(outbound_alighting.id) if outbound_alighting else None,
                'return_boarding_stop_id': str(return_boarding.id) if return_boarding else None,
                'return_alighting_stop_id': str(return_alighting.id) if return_alighting else None,
            }
            
            total_fare = outbound_trip.fare + return_trip.fare
            print(f'📝 Booking return trip (both legs)')
            print(f'   Outbound: {outbound_trip.route.name} (KES {outbound_trip.fare})')
            print(f'   Return: {return_trip.route.name} (KES {return_trip.fare})')
            print(f'   Total fare: KES {total_fare}')
            
            res = requests.post(
                f'{self.base_url}/api/bookings/multi-mode/',
                json=payload,
                headers={'Authorization': f'Bearer {self.commuter_token}'},
                timeout=10,
            )
            
            if res.status_code == 201:
                result = res.json()
                print(f'✓ Return immediate booking successful')
                print(f'   Two-way booking ID: {result.get("two_way_booking_id")}')
                print(f'   Outbound booking ID: {result.get("outbound_booking_id")}')
                print(f'   Return booking ID: {result.get("return_booking_id")}')
                print(f'   Status: {result.get("status")}')
                self.results.append(('Return Immediate', 'SUCCESS', result.get('two_way_booking_id')))
            else:
                print(f'✗ Return immediate booking failed: {res.text}')
                self.results.append(('Return Immediate', 'FAILED', None))
            
        except Exception as e:
            print(f'✗ Return immediate test error: {e}')
            self.results.append(('Return Immediate', 'ERROR', str(e)))
        
        print()

    def test_return_open(self, data):
        """Test Mode 2b: Return trip - open return credit"""
        print('═' * 60)
        print('🎫 MODE 2b: Return Trip - Open Return Credit')
        print('═' * 60)
        
        try:
            outbound_trip = data['outbound_trip']
            
            outbound_boarding = outbound_trip.route.stops.first()
            outbound_alighting = outbound_trip.route.stops.last()
            
            payload = {
                'trip_mode': 'return_open',
                'outbound_trip_id': str(outbound_trip.id),
                'phone_number': '+254700000000',
                'payment_method': 'mpesa',
                'return_window_hours': 24,
                'outbound_boarding_stop_id': str(outbound_boarding.id) if outbound_boarding else None,
                'outbound_alighting_stop_id': str(outbound_alighting.id) if outbound_alighting else None,
            }
            
            print(f'📝 Booking outbound trip with open return')
            print(f'   Outbound: {outbound_trip.route.name} (KES {outbound_trip.fare})')
            print(f'   Return window: 24 hours')
            
            res = requests.post(
                f'{self.base_url}/api/bookings/multi-mode/',
                json=payload,
                headers={'Authorization': f'Bearer {self.commuter_token}'},
                timeout=10,
            )
            
            if res.status_code == 201:
                result = res.json()
                print(f'✓ Open return booking successful')
                print(f'   Booking ID: {result.get("booking_id")}')
                print(f'   Credit ID: {result.get("credit_id")}')
                print(f'   Credit amount: KES {result.get("credit_amount")}')
                print(f'   Valid until: {result.get("valid_until")}')
                self.results.append(('Return Open', 'SUCCESS', result.get('credit_id')))
                
                # Test credit redemption
                credit_id = result.get('credit_id')
                print(f'\n🔄 Testing credit redemption...')
                
                return_trip = data['return_trip']
                return_boarding = return_trip.route.stops.first()
                return_alighting = return_trip.route.stops.last()
                
                redeem_payload = {
                    'credit_id': credit_id,
                    'return_trip_id': str(return_trip.id),
                    'return_boarding_stop_id': str(return_boarding.id) if return_boarding else None,
                    'return_alighting_stop_id': str(return_alighting.id) if return_alighting else None,
                }
                
                redeem_res = requests.post(
                    f'{self.base_url}/api/bookings/redeem-return/',
                    json=redeem_payload,
                    headers={'Authorization': f'Bearer {self.commuter_token}'},
                    timeout=10,
                )
                
                if redeem_res.status_code == 201:
                    redeem_result = redeem_res.json()
                    print(f'✓ Credit redemption successful')
                    print(f'   Return booking ID: {redeem_result.get("booking_id")}')
                    print(f'   Fare paid: KES {redeem_result.get("fare_paid")}')
                else:
                    print(f'✗ Credit redemption failed: {redeem_res.text}')
                    
            else:
                print(f'✗ Open return booking failed: {res.text}')
                self.results.append(('Return Open', 'FAILED', None))
            
        except Exception as e:
            print(f'✗ Return open test error: {e}')
            self.results.append(('Return Open', 'ERROR', str(e)))
        
        print()

    def test_linked_trip(self, data):
        """Test Mode 3: Linked trip with transfer bay"""
        print('═' * 60)
        print('🎫 MODE 3: Linked Trip with Transfer Bay')
        print('═' * 60)
        
        try:
            first_leg = data['first_leg_trip']
            second_leg = data['second_leg_trip']
            transfer_station = data['transfer_station']
            
            first_boarding = first_leg.route.stops.first()
            first_alighting = transfer_station
            second_boarding = transfer_station
            second_alighting = second_leg.route.stops.last()
            
            payload = {
                'trip_mode': 'linked',
                'first_leg_trip_id': str(first_leg.id),
                'second_leg_trip_id': str(second_leg.id),
                'transfer_station_id': str(transfer_station.id) if transfer_station else None,
                'phone_number': '+254700000000',
                'payment_method': 'mpesa',
                'first_leg_boarding_stop_id': str(first_boarding.id) if first_boarding else None,
                'first_leg_alighting_stop_id': str(first_alighting.id) if first_alighting else None,
                'second_leg_boarding_stop_id': str(second_boarding.id) if second_boarding else None,
                'second_leg_alighting_stop_id': str(second_alighting.id) if second_alighting else None,
            }
            
            print(f'📝 Booking linked trip with transfer')
            print(f'   First leg: {first_leg.route.name} (KES {first_leg.fare})')
            print(f'   Transfer at: {transfer_station.name if transfer_station else "N/A"}')
            print(f'   Second leg: {second_leg.route.name} (KES {second_leg.fare})')
            print(f'   Second leg status: pending_transfer (will auto-book via GPS monitoring)')
            
            res = requests.post(
                f'{self.base_url}/api/bookings/multi-mode/',
                json=payload,
                headers={'Authorization': f'Bearer {self.commuter_token}'},
                timeout=10,
            )
            
            if res.status_code == 201:
                result = res.json()
                print(f'✓ Linked trip booking successful')
                print(f'   First leg booking ID: {result.get("booking_id")}')
                print(f'   Linked booking ID: {result.get("linked_booking_id")}')
                print(f'   First leg status: {result.get("status")}')
                print(f'   Second leg status: {result.get("second_leg_status")}')
                print(f'   Message: {result.get("message")}')
                self.results.append(('Linked Trip', 'SUCCESS', result.get('linked_booking_id')))
                
                # Check linked booking in database
                linked_booking = LinkedBooking.objects.filter(id=result.get('linked_booking_id')).first()
                if linked_booking:
                    print(f'\n📊 Linked booking details:')
                    print(f'   Status: {linked_booking.status}')
                    print(f'   First leg: {linked_booking.first_leg_booking.status}')
                    print(f'   Second leg: {linked_booking.second_leg_booking.status}')
                    
            else:
                print(f'✗ Linked trip booking failed: {res.text}')
                self.results.append(('Linked Trip', 'FAILED', None))
            
        except Exception as e:
            print(f'✗ Linked trip test error: {e}')
            self.results.append(('Linked Trip', 'ERROR', str(e)))
        
        print()

    def print_summary(self):
        """Print simulation summary"""
        print('═' * 60)
        print('📊 SIMULATION SUMMARY')
        print('═' * 60)
        
        for mode, status, details in self.results:
            icon = '✓' if status == 'SUCCESS' else '✗'
            print(f'{icon} {mode:20} {status:10} {str(details)[:30] if details else "N/A"}')
        
        print()
        success_count = sum(1 for _, status, _ in self.results if status == 'SUCCESS')
        print(f'Total: {success_count}/{len(self.results)} tests passed')
        print()

    def run_all_tests(self):
        """Run all booking mode simulations"""
        print('🚀 Multi-Mode Booking Simulation')
        print('=' * 60)
        print()
        
        try:
            # Setup demo data
            data = self.setup_demo_data()
            
            # Run all tests
            self.test_single_trip(data)
            self.test_return_immediate(data)
            self.test_return_open(data)
            self.test_linked_trip(data)
            
            # Print summary
            self.print_summary()
            
            print('💡 Next steps:')
            print('  1. Use simulate_gps.py to simulate GPS for the trips')
            print('  2. Monitor the transfer bay task for linked trip auto-booking')
            print('  3. Check booking statuses via API or admin panel')
            print()
            
        except Exception as e:
            print(f'✗ Simulation failed: {e}')
            import traceback
            traceback.print_exc()


def main():
    simulator = MultiModeBookingSimulator()
    simulator.run_all_tests()


if __name__ == '__main__':
    main()
