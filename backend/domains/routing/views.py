from rest_framework import viewsets

from domains.accounts.permissions import IsFleetOwnerOrSuperAdmin

from .models import Route, Stop, Trip
from .serializers import RouteSerializer, StopSerializer, TripSerializer


from rest_framework.response import Response
from rest_framework.views import APIView

from .eta import estimate_arrival
from .serializers import SeatAvailabilitySerializer

from domains.tracking.redis_client import get_vehicle_position



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