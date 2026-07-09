import uuid
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from domains.accounts.models import User
from domains.fleet.models import Vehicle, Fleet
from domains.routing.models import Route
from domains.tenants.models import Tenant
from domains.stage_queue.models import Stage, QueueEntry


class Command(BaseCommand):
    help = 'Seed demo data for stage queue system'

    def handle(self, *args, **options):
        self.stdout.write('Seeding stage queue demo data...')

        # Get or create a tenant
        tenant, _ = Tenant.objects.get_or_create(
            name='Demo Transit Company',
            defaults={'slug': 'demo-transit-company'}
        )

        # Create a fleet
        fleet, _ = Fleet.objects.get_or_create(
            name='Demo Fleet',
            defaults={'tenant': tenant}
        )

        # Create a route
        from django.contrib.gis.geos import LineString
        route, _ = Route.objects.get_or_create(
            name='Thika - CBD',
            defaults={
                'tenant': tenant,
                'path': LineString((37.1, -1.0), (36.8, -1.3), srid=4326),  # Simple line from Thika to Nairobi
                'distance_km': 45,
                'estimated_duration_minutes': 60
            }
        )

        # Create stage
        stage, created = Stage.objects.get_or_create(
            name='Thika Town Stage',
            defaults={
                'tenant': tenant,
                'route': route,
                'loading_bay_capacity': 2
            }
        )
        if created:
            self.stdout.write(f'Created stage: {stage.name}')
        else:
            self.stdout.write(f'Stage already exists: {stage.name}')

        # Create vehicles with fleet codes
        vehicle_data = [
            {'fleet_code': 'TH-001', 'plate_number': 'KDA 123A', 'capacity': 14},
            {'fleet_code': 'TH-002', 'plate_number': 'KDA 456B', 'capacity': 14},
            {'fleet_code': 'TH-003', 'plate_number': 'KDA 789C', 'capacity': 14},
            {'fleet_code': 'TH-004', 'plate_number': 'KDA 012D', 'capacity': 14},
            {'fleet_code': 'TH-005', 'plate_number': 'KDA 345E', 'capacity': 14},
        ]

        vehicles = []
        for v_data in vehicle_data:
            vehicle, created = Vehicle.objects.get_or_create(
                fleet_code=v_data['fleet_code'],
                defaults={
                    'tenant': tenant,
                    'fleet': fleet,
                    'plate_number': v_data['plate_number'],
                    'vehicle_type': 'matatu',
                    'capacity': v_data['capacity'],
                    'is_active': True
                }
            )
            vehicles.append(vehicle)
            if created:
                self.stdout.write(f'Created vehicle: {vehicle.fleet_code}')
            else:
                self.stdout.write(f'Vehicle already exists: {vehicle.fleet_code}')

        # Create drivers
        driver_data = [
            {'username': 'driver1', 'phone': '+254711111111'},
            {'username': 'driver2', 'phone': '+254722222222'},
            {'username': 'driver3', 'phone': '+254733333333'},
            {'username': 'driver4', 'phone': '+254744444444'},
            {'username': 'driver5', 'phone': '+254755555555'},
        ]

        drivers = []
        for d_data in driver_data:
            driver, created = User.objects.get_or_create(
                username=d_data['username'],
                defaults={
                    'role': 'driver',
                    'tenant': tenant,
                    'phone_number': d_data['phone'],
                    'is_active': True
                }
            )
            if created:
                driver.set_password('password123')
                driver.save()
                self.stdout.write(f'Created driver: {driver.username}')
            else:
                self.stdout.write(f'Driver already exists: {driver.username}')
            drivers.append(driver)

        # Create stage manager
        stage_manager, created = User.objects.get_or_create(
            username='stage_manager',
            defaults={
                'role': 'stage_manager',
                'tenant': tenant,
                'phone_number': '+254700000000',
                'is_active': True
            }
        )
        if created:
            stage_manager.set_password('password123')
            stage_manager.save()
            self.stdout.write(f'Created stage manager: {stage_manager.username}')
        else:
            self.stdout.write(f'Stage manager already exists: {stage_manager.username}')

        # Clear existing queue entries for this stage
        QueueEntry.objects.filter(stage=stage).delete()
        self.stdout.write('Cleared existing queue entries')

        # Create realistic queue with different statuses
        now = timezone.now()
        
        # Queue entry 1: Already departed (for history)
        QueueEntry.objects.create(
            stage=stage,
            vehicle=vehicles[0],
            driver=drivers[0],
            route=route,
            tenant=tenant,
            status='departed',
            confirmed=True,
            arrived_at=now - timedelta(minutes=30),
            confirmed_at=now - timedelta(minutes=29),
            called_up_at=now - timedelta(minutes=28),
            loading_started_at=now - timedelta(minutes=28),
            departed_at=now - timedelta(minutes=15)
        )

        # Queue entry 2: In loading bay (called_up)
        QueueEntry.objects.create(
            stage=stage,
            vehicle=vehicles[1],
            driver=drivers[1],
            route=route,
            tenant=tenant,
            status='called_up',
            confirmed=True,
            arrived_at=now - timedelta(minutes=20),
            confirmed_at=now - timedelta(minutes=19),
            called_up_at=now - timedelta(minutes=10),
            time_cap_minutes=15
        )

        # Queue entry 3: In holding, confirmed
        QueueEntry.objects.create(
            stage=stage,
            vehicle=vehicles[2],
            driver=drivers[2],
            route=route,
            tenant=tenant,
            status='holding',
            confirmed=True,
            arrived_at=now - timedelta(minutes=15),
            confirmed_at=now - timedelta(minutes=14),
            time_cap_minutes=15
        )

        # Queue entry 4: In holding, confirmed
        QueueEntry.objects.create(
            stage=stage,
            vehicle=vehicles[3],
            driver=drivers[3],
            route=route,
            tenant=tenant,
            status='holding',
            confirmed=True,
            arrived_at=now - timedelta(minutes=10),
            confirmed_at=now - timedelta(minutes=9),
            time_cap_minutes=15
        )

        # Queue entry 5: In holding, NOT confirmed (just arrived)
        QueueEntry.objects.create(
            stage=stage,
            vehicle=vehicles[4],
            driver=drivers[4],
            route=route,
            tenant=tenant,
            status='holding',
            confirmed=False,
            arrived_at=now - timedelta(minutes=2),
            time_cap_minutes=15
        )

        self.stdout.write(self.style.SUCCESS('Created 5 queue entries with realistic statuses'))
        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully!'))
        self.stdout.write('\nDemo credentials:')
        self.stdout.write('  Stage Manager: stage_manager / password123')
        self.stdout.write('  Drivers: driver1-5 / password123')
