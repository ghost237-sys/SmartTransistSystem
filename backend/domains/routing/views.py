from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.permissions import IsFleetOwnerOrSuperAdmin

from .models import Route, Stop, Trip, TransferStation, LinkedRoute
from .serializers import (
    RouteSerializer, StopSerializer, TripSerializer,
    TransferStationSerializer, LinkedRouteSerializer, LinkedJourneySerializer
)


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
        stops = Stop.objects.select_related('route').order_by('route__name', 'sequence')
        serializer = StopSerializer(stops, many=True)
        return Response(serializer.data)



class StopSeatAvailabilityView(APIView):
    def get(self, request, stop_id):
        stop = Stop.objects.filter(id=stop_id).first()
        if stop is None:
            return Response({'detail': 'Stop not found.'}, status=404)

        active_trips = Trip.all_objects.filter(
            route=stop.route, status='active'
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
    Read-only trip listing for commuters — returns active on-demand trips
    with available seat counts. No tenant restriction since commuters
    need to see all operators' trips.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        trips = Trip.all_objects.filter(
            status='active'
        ).select_related('route', 'vehicle').order_by('-created_at')
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
    filtered to active trips only.
    """
    permission_classes = [IsConductor]

    def get(self, request):
        trips = Trip.all_objects.filter(
            conductor=request.user,
            status='active'
        ).select_related('route').order_by('-created_at')
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)


class DriverTripListView(APIView):
    """
    Returns trips assigned to the authenticated driver,
    filtered to active trips only.
    """
    permission_classes = [IsDriver]

    def get(self, request):
        trips = Trip.all_objects.filter(
            driver=request.user,
            status='active'
        ).select_related('route', 'vehicle').order_by('-created_at')
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


from django.contrib.gis.geos import Point
from django.contrib.gis.measure import Distance
from domains.tracking.redis_client import get_vehicle_position
from domains.routing.eta import estimate_arrival
from domains.routing.geo import (
    COMMUTER_ROUTE_RADIUS_KM,
    nearest_stop_to_point,
)


class NearbyRoutesView(APIView):
    """
    Routes whose stops pass near the commuter's location.
    Used to limit destination search to lines that actually serve their area.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')

        if not lat or not lng:
            return Response({'detail': 'lat and lng are required.'}, status=400)

        try:
            commuter_point = Point(float(lng), float(lat), srid=4326)
        except (ValueError, TypeError):
            return Response({'detail': 'Invalid lat/lng.'}, status=400)

        from .models import Route
        routes = Route.objects.filter(is_active=True).prefetch_related('stops')

        results = []
        for route in routes:
            stops = list(route.stops.all().order_by('sequence'))
            if not stops:
                continue

            nearest_stop, distance_km = nearest_stop_to_point(commuter_point, stops)
            if nearest_stop is None:
                continue

            radius = min(route.max_pickup_distance_km, COMMUTER_ROUTE_RADIUS_KM)
            if distance_km > radius:
                continue

            results.append({
                'route_id': route.id,
                'route_name': route.name,
                'nearest_stop_id': nearest_stop.id,
                'nearest_stop_name': nearest_stop.name,
                'nearest_stop_sequence': nearest_stop.sequence,
                'distance_km': distance_km,
                'stops': StopSerializer(stops, many=True).data,
            })

        results.sort(key=lambda r: r['distance_km'])
        return Response(results)


class FindRideView(APIView):
    """
    Core on-demand matching endpoint.
    Given a commuter's location and destination stop,
    returns all active buses on routes serving that destination,
    filtered to within max_pickup_distance_km, ordered by ETA
    to the commuter's nearest stop on that route.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        destination_stop_id = request.query_params.get('destination')

        if not lat or not lng:
            return Response(
                {'detail': 'lat and lng query parameters are required.'},
                status=400
            )

        try:
            commuter_point = Point(float(lng), float(lat), srid=4326)
        except (ValueError, TypeError):
            return Response({'detail': 'Invalid lat/lng values.'}, status=400)

        # Get destination stop if provided
        destination_stop = None
        if destination_stop_id:
            destination_stop = Stop.objects.filter(id=destination_stop_id).first()

        # Find all active trips
        active_trips = Trip.all_objects.filter(
            status='active'
        ).select_related('route', 'vehicle', 'driver', 'conductor')

        # If destination provided, filter to routes that serve it
        if destination_stop:
            active_trips = active_trips.filter(
                route=destination_stop.route
            )

        results = []
        for trip in active_trips:
            position = get_vehicle_position(str(trip.vehicle_id))
            if position is None:
                continue

            stops = list(trip.route.stops.all().order_by('sequence'))
            if not stops:
                continue

            nearest_stop, commuter_to_stop_km = nearest_stop_to_point(commuter_point, stops)
            if nearest_stop is None:
                continue

            # Commuter must be near this route (within urban corridor radius)
            route_radius = min(trip.route.max_pickup_distance_km, COMMUTER_ROUTE_RADIUS_KM)
            if commuter_to_stop_km > route_radius:
                continue

            # Destination must be ahead of the boarding stop along the route
            if destination_stop and nearest_stop.sequence >= destination_stop.sequence:
                continue

            eta_data = estimate_arrival(trip, nearest_stop)
            if eta_data is None:
                continue

            max_pickup_km = trip.route.max_pickup_distance_km
            if eta_data['eta_minutes'] > 60:
                continue
            if eta_data['distance_km'] > max_pickup_km:
                continue

            if trip.available_seats <= 0:
                continue

            results.append({
                'trip_id': trip.id,
                'route_name': trip.route.name,
                'fleet_code': trip.vehicle.fleet_code or trip.vehicle.plate_number,
                'vehicle_plate': trip.vehicle.plate_number,
                'available_seats': trip.available_seats,
                'fare': trip.fare,
                'pickup_stop_id': nearest_stop.id,
                'pickup_stop_name': nearest_stop.name,
                'commuter_distance_km': commuter_to_stop_km,
                'eta_minutes': eta_data['eta_minutes'],
                'distance_km': eta_data['distance_km'],
                'vehicle_latitude': position['latitude'],
                'vehicle_longitude': position['longitude'],
                'speed_kmh': position.get('speed_kmh'),
            })

        # Sort by ETA
        results.sort(key=lambda x: x['eta_minutes'])

        return Response(results)


class TransferStationViewSet(viewsets.ModelViewSet):
    serializer_class = TransferStationSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        return TransferStation.objects.all()

    def perform_create(self, serializer):
        serializer.save()


class LinkedRouteViewSet(viewsets.ModelViewSet):
    serializer_class = LinkedRouteSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        return LinkedRoute.objects.select_related(
            'first_route', 'second_route', 'transfer_station',
            'first_route_stop', 'second_route_stop'
        ).all()

    def perform_create(self, serializer):
        serializer.save()


class FindLinkedJourneyView(APIView):
    """
    Finds linked journeys that connect two routes via a transfer station.
    Returns unified journey cards that thread the two buses together.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng')
        final_destination_id = request.query_params.get('final_destination')

        if not lat or not lng:
            return Response(
                {'detail': 'lat and lng query parameters are required.'},
                status=400
            )

        if not final_destination_id:
            return Response(
                {'detail': 'final_destination query parameter is required.'},
                status=400
            )

        try:
            commuter_point = Point(float(lng), float(lat), srid=4326)
        except (ValueError, TypeError):
            return Response({'detail': 'Invalid lat/lng values.'}, status=400)

        # Get final destination stop
        final_destination = Stop.objects.filter(id=final_destination_id).first()
        if not final_destination:
            return Response({'detail': 'Final destination stop not found.'}, status=404)

        # Get all active linked routes
        linked_routes = LinkedRoute.objects.filter(is_active=True).select_related(
            'first_route', 'second_route', 'transfer_station',
            'first_route_stop', 'second_route_stop'
        )

        results = []

        for linked_route in linked_routes:
            # Check if second route serves the final destination
            if linked_route.second_route != final_destination.route:
                continue

            # Find active trips on first route
            first_trips = Trip.all_objects.filter(
                route=linked_route.first_route,
                status='active'
            ).select_related('route', 'vehicle', 'driver', 'conductor')

            # Find active trips on second route
            second_trips = Trip.all_objects.filter(
                route=linked_route.second_route,
                status='active'
            ).select_related('route', 'vehicle', 'driver', 'conductor')

            for first_trip in first_trips:
                # Check if first trip can pick up the commuter
                first_position = get_vehicle_position(str(first_trip.vehicle_id))
                if not first_position:
                    continue

                first_stops = list(first_trip.route.stops.all().order_by('sequence'))
                if not first_stops:
                    continue

                first_nearest_stop, commuter_to_first_stop_km = nearest_stop_to_point(
                    commuter_point, first_stops
                )
                if not first_nearest_stop:
                    continue

                first_route_radius = min(first_trip.route.max_pickup_distance_km, COMMUTER_ROUTE_RADIUS_KM)
                if commuter_to_first_stop_km > first_route_radius:
                    continue

                # Check if transfer stop is ahead of pickup stop
                if first_nearest_stop.sequence >= linked_route.first_route_stop.sequence:
                    continue

                first_eta_data = estimate_arrival(first_trip, linked_route.first_route_stop)
                if not first_eta_data:
                    continue

                if first_trip.available_seats <= 0:
                    continue

                # Now find compatible second trips
                for second_trip in second_trips:
                    if second_trip.available_seats <= 0:
                        continue

                    # Check if second trip departure is after first trip arrival at transfer
                    if not second_trip.departure_time:
                        continue

                    # Calculate arrival time at transfer station
                    from django.utils import timezone
                    arrival_at_transfer = timezone.now() + timezone.timedelta(
                        minutes=first_eta_data['eta_minutes']
                    )

                    # Calculate buffer time
                    time_until_second_departure = (second_trip.departure_time - arrival_at_transfer).total_seconds() / 60
                    buffer_minutes = linked_route.transfer_station.buffer_minutes

                    is_safe_transfer = time_until_second_departure >= buffer_minutes

                    # Only show if transfer is reasonably safe (within 2 hours)
                    if time_until_second_departure < 0 or time_until_second_departure > 120:
                        continue

                    # Get second trip position
                    second_position = get_vehicle_position(str(second_trip.vehicle_id))
                    if not second_position:
                        continue

                    # Get second trip ETA to final destination
                    second_eta_data = estimate_arrival(second_trip, final_destination)
                    if not second_eta_data:
                        continue

                    # Build unified journey result
                    results.append({
                        'linked_route_id': linked_route.id,
                        'first_leg': {
                            'trip_id': first_trip.id,
                            'route_name': first_trip.route.name,
                            'fleet_code': first_trip.vehicle.fleet_code or first_trip.vehicle.plate_number,
                            'vehicle_plate': first_trip.vehicle.plate_number,
                            'available_seats': first_trip.available_seats,
                            'fare': first_trip.fare,
                            'pickup_stop_id': first_nearest_stop.id,
                            'pickup_stop_name': first_nearest_stop.name,
                            'commuter_distance_km': commuter_to_first_stop_km,
                            'eta_minutes': first_eta_data['eta_minutes'],
                            'distance_km': first_eta_data['distance_km'],
                            'vehicle_latitude': first_position['latitude'],
                            'vehicle_longitude': first_position['longitude'],
                            'speed_kmh': first_position.get('speed_kmh'),
                            'transfer_stop_id': linked_route.first_route_stop.id,
                            'transfer_stop_name': linked_route.first_route_stop.name,
                        },
                        'second_leg': {
                            'trip_id': second_trip.id,
                            'route_name': second_trip.route.name,
                            'fleet_code': second_trip.vehicle.fleet_code or second_trip.vehicle.plate_number,
                            'vehicle_plate': second_trip.vehicle.plate_number,
                            'available_seats': second_trip.available_seats,
                            'fare': second_trip.fare,
                            'pickup_stop_id': linked_route.second_route_stop.id,
                            'pickup_stop_name': linked_route.second_route_stop.name,
                            'eta_minutes': second_eta_data['eta_minutes'],
                            'distance_km': second_eta_data['distance_km'],
                            'vehicle_latitude': second_position['latitude'],
                            'vehicle_longitude': second_position['longitude'],
                            'speed_kmh': second_position.get('speed_kmh'),
                            'departure_time': second_trip.departure_time.isoformat() if second_trip.departure_time else None,
                        },
                        'transfer_station_name': linked_route.transfer_station.name,
                        'total_fare': float(first_trip.fare) + float(second_trip.fare),
                        'total_duration_minutes': first_eta_data['eta_minutes'] + second_eta_data['eta_minutes'] + time_until_second_departure,
                        'transfer_buffer_minutes': round(time_until_second_departure, 1),
                        'is_safe_transfer': is_safe_transfer,
                    })

        # Sort by total duration
        results.sort(key=lambda x: x['total_duration_minutes'])

        serializer = LinkedJourneySerializer(results, many=True)
        return Response(serializer.data)