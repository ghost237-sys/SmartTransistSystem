from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.permissions import IsFleetOwnerOrSuperAdmin

from .models import Route, Stop, Trip
from .serializers import RouteSerializer, StopSerializer, TripSerializer


from .eta import estimate_arrival
from .serializers import SeatAvailabilitySerializer

from domains.tracking.redis_client import get_vehicle_position

from rest_framework.permissions import IsAuthenticated
from domains.accounts.permissions import IsFleetOwnerOrSuperAdmin, IsConductor, IsDriver



class RouteViewSet(viewsets.ModelViewSet):
    serializer_class = RouteSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        return Route.objects.all()

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class StopViewSet(viewsets.ModelViewSet):
    serializer_class = StopSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        # Stop has no tenant field of its own — scoped indirectly through its route.
        return Stop.objects.filter(route__tenant=self.request.user.tenant)


class TripViewSet(viewsets.ModelViewSet):
    serializer_class = TripSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        return Trip.objects.all()

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class ListStopsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        stops = Stop.objects.all().order_by('name')
        serializer = StopSerializer(stops, many=True)
        return Response(serializer.data)



class StopSeatAvailabilityView(APIView):
    def get(self, request, stop_id):
        stop = Stop.objects.filter(id=stop_id).first()
        if stop is None:
            return Response({'detail': 'Stop not found.'}, status=404)

        active_trips = Trip.all_objects.filter(
            route=stop.route, status='scheduled'
        )

        results = []
        for trip in active_trips:
            opening = trip.seats_opening_at(stop)
            if opening <= 0:
                continue

            position = get_vehicle_position(str(trip.vehicle_id))
            eta_data = estimate_arrival(trip, stop)

            results.append({
                'trip_id': trip.id,
                'seats_opening': opening,
                'vehicle_latitude': position['latitude'] if position else None,
                'vehicle_longitude': position['longitude'] if position else None,
                'distance_km': eta_data['distance_km'] if eta_data else None,
                'eta_minutes': eta_data['eta_minutes'] if eta_data else None,
            })

        serializer = SeatAvailabilitySerializer(results, many=True)
        return Response(serializer.data)


from rest_framework.permissions import IsAuthenticated

class PublicTripListView(APIView):
    """
    Read-only trip listing for commuters — returns scheduled trips
    with available seat counts. No tenant restriction since commuters
    need to see all operators' trips.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        trips = Trip.all_objects.filter(
            status='scheduled'
        ).select_related('route', 'vehicle').order_by('departure_time')
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)

class PublicTripDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, trip_id):
        trip = Trip.all_objects.filter(id=trip_id).select_related('route', 'vehicle').first()
        if trip is None:
            return Response({'detail': 'Trip not found.'}, status=404)
        serializer = TripSerializer(trip)
        return Response(serializer.data)



class ConductorTripListView(APIView):
    """
    Returns trips assigned to the authenticated conductor,
    filtered to active (scheduled/departed) trips only.
    """
    permission_classes = [IsConductor]

    def get(self, request):
        trips = Trip.all_objects.filter(
            conductor=request.user,
            status__in=['scheduled', 'departed']
        ).select_related('route').order_by('departure_time')
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)


class DriverTripListView(APIView):
    """
    Returns trips assigned to the authenticated driver,
    filtered to active (scheduled/departed) trips only.
    """
    permission_classes = [IsDriver]

    def get(self, request):
        trips = Trip.all_objects.filter(
            driver=request.user,
            status__in=['scheduled', 'departed']
        ).select_related('route', 'vehicle').order_by('departure_time')
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)


class DriverTripDetailView(APIView):
    permission_classes = [IsDriver]

    def get(self, request, trip_id):
        trip = Trip.all_objects.filter(
            id=trip_id, driver=request.user
        ).select_related('route', 'vehicle').first()
        if trip is None:
            return Response({'detail': 'Trip not found.'}, status=404)
        serializer = TripSerializer(trip)
        return Response(serializer.data)

class TripStopsView(APIView):
    """
    Returns the stops for a specific trip's route.
    Used by the commuter booking flow to select alighting stop.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, trip_id):
        trip = Trip.all_objects.filter(id=trip_id).select_related('route').first()
        if trip is None:
            return Response({'detail': 'Trip not found.'}, status=404)
        stops = trip.route.stops.all().order_by('sequence')
        serializer = StopSerializer(stops, many=True)
        return Response(serializer.data)