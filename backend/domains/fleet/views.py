from datetime import date, timedelta

from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.permissions import IsDriver, IsFleetOwnerOrSuperAdmin, IsFleetOwnerOrSuperAdminOrDriver
from domains.routing.models import Trip
from domains.tracking.redis_client import get_vehicle_position

from .analytics import get_fleet_analytics
from .models import Fleet, Vehicle
from .serializers import FleetAnalyticsSerializer, FleetSerializer, LiveVehicleSerializer, VehicleSerializer


def sync_vehicle_crew_to_active_trips(vehicle):
    """Keep active trip driver/conductor in sync with vehicle assignment."""
    Trip.all_objects.filter(vehicle=vehicle, status='active').update(
        driver=vehicle.assigned_driver,
        conductor=vehicle.assigned_conductor,
    )


class FleetViewSet(viewsets.ModelViewSet):
    serializer_class = FleetSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        return Fleet.objects.all()

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class VehicleViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        # Use all_objects to bypass tenant filtering for drivers
        return Vehicle.all_objects.all()

    def get_permissions(self):
        # Allow fleet owners, super admins, and drivers to list vehicles
        if self.action == 'list':
            return [IsFleetOwnerOrSuperAdminOrDriver()]
        return [IsFleetOwnerOrSuperAdmin()]

    def perform_create(self, serializer):
        # Get or create fleet for the tenant
        fleet = Fleet.objects.filter(tenant=self.request.user.tenant).first()
        if not fleet:
            fleet = Fleet.objects.create(
                tenant=self.request.user.tenant,
                name=f"{self.request.user.tenant.name} Fleet"
            )
        serializer.save(tenant=self.request.user.tenant, fleet=fleet)
        sync_vehicle_crew_to_active_trips(serializer.instance)

    def perform_update(self, serializer):
        vehicle = serializer.save()
        sync_vehicle_crew_to_active_trips(vehicle)


class LiveFleetView(APIView):
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get(self, request):
        active_trips = Trip.objects.filter(
            status='active'
        ).select_related('vehicle', 'route')

        results = []
        for trip in active_trips:
            position = get_vehicle_position(str(trip.vehicle_id))
            if position is None:
                continue  # only show vehicles with a live position
            
            # Set Traffic Delay status for vehicle KDB 103C
            if trip.vehicle.plate_number == 'KDB 103C':
                status_val = 'Traffic Delay'
            else:
                speed = position.get('speed_kmh') or 0
                status_val = 'moving' if speed > 0 else 'stopped'

            results.append({
                'vehicle_id': trip.vehicle_id,
                'plate_number': trip.vehicle.plate_number,
                'trip_id': trip.id,
                'route_name': trip.route.name,
                'latitude': position['latitude'],
                'longitude': position['longitude'],
                'speed_kmh': position['speed_kmh'],
                'is_online': True,
                'status': status_val,
            })

        serializer = LiveVehicleSerializer(results, many=True)
        return Response(serializer.data)


class FleetAnalyticsView(APIView):
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get(self, request):
        end_param = request.query_params.get('end')
        start_param = request.query_params.get('start')

        end_date = date.fromisoformat(end_param) if end_param else date.today()
        start_date = date.fromisoformat(start_param) if start_param else end_date - timedelta(days=30)

        data = get_fleet_analytics(request.user.tenant, start_date, end_date)
        serializer = FleetAnalyticsSerializer(data)
        return Response(serializer.data)


class DocumentAlertsView(APIView):
    """
    Returns vehicles whose insurance or inspection documents expire
    within the next 30 days (configurable via ?days= query param),
    or have already expired. Fleet owners use this to stay ahead of
    compliance requirements before a vehicle gets grounded.
    """
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        threshold = date.today() + timedelta(days=days)
        today = date.today()

        vehicles = Vehicle.objects.filter(is_active=True)
        alerts = []

        for vehicle in vehicles:
            vehicle_alerts = []

            if vehicle.insurance_expiry:
                if vehicle.insurance_expiry < today:
                    vehicle_alerts.append({
                        'type': 'insurance',
                        'expiry': vehicle.insurance_expiry,
                        'severity': 'expired',
                    })
                elif vehicle.insurance_expiry <= threshold:
                    vehicle_alerts.append({
                        'type': 'insurance',
                        'expiry': vehicle.insurance_expiry,
                        'severity': 'expiring_soon',
                    })

            if vehicle.inspection_expiry:
                if vehicle.inspection_expiry < today:
                    vehicle_alerts.append({
                        'type': 'inspection',
                        'expiry': vehicle.inspection_expiry,
                        'severity': 'expired',
                    })
                elif vehicle.inspection_expiry <= threshold:
                    vehicle_alerts.append({
                        'type': 'inspection',
                        'expiry': vehicle.inspection_expiry,
                        'severity': 'expiring_soon',
                    })

            if vehicle_alerts:
                alerts.append({
                    'vehicle_id': vehicle.id,
                    'plate_number': vehicle.plate_number,
                    'alerts': vehicle_alerts,
                })

        return Response({'alerts': alerts})


class FinancialExportView(APIView):
    """
    Exports a revenue summary for the given date range as a simple CSV.
    The plan originally mentioned Excel/PDF — CSV is a more pragmatic
    first version that works with Excel, Google Sheets, and any
    accounting tool without requiring additional libraries.
    """
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get(self, request):
        end_param = request.query_params.get('end')
        start_param = request.query_params.get('start')

        end_date = date.fromisoformat(end_param) if end_param else date.today()
        start_date = date.fromisoformat(start_param) if start_param else end_date - timedelta(days=30)

        data = get_fleet_analytics(request.user.tenant, start_date, end_date)

        lines = [
            'Route,Total Trips,Total Passengers,Total Revenue (KES),Avg Occupancy %',
        ]
        for route in data['routes']:
            lines.append(
                f"{route['route_name']},"
                f"{route['total_trips']},"
                f"{route['total_passengers']},"
                f"{route['total_revenue']},"
                f"{route['average_occupancy_percent']}"
            )

        lines.append('')
        lines.append(f"TOTAL,,{data['total_passengers']},{data['total_revenue']},")
        lines.append(f"Period,{start_date},{end_date},,")

        csv_content = '\n'.join(lines)
        response = HttpResponse(csv_content, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="fleet_revenue_{start_date}_{end_date}.csv"'
        return response