from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.permissions import IsDriver
from domains.routing.models import Trip

from .channels_utils import broadcast_position_update
from .models import VehiclePosition
from .redis_client import set_vehicle_position
from .serializers import PositionUpdateSerializer


class PositionUpdateView(APIView):
    permission_classes = [IsDriver]

    def post(self, request):
        serializer = PositionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        trip_id = data.get('trip_id')

        if trip_id:
            trip = Trip.all_objects.filter(id=trip_id, driver=request.user).first()
            if trip is None:
                return Response(
                    {'detail': 'You are not assigned as the driver for this trip.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if trip.status not in ('scheduled', 'departed'):
                return Response(
                    {'detail': f'Cannot report position for a trip with status "{trip.status}".'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if str(trip.vehicle_id) != str(data['vehicle_id']):
                return Response(
                    {'detail': 'Vehicle does not match the assigned trip.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        now = timezone.now()

        set_vehicle_position(
            vehicle_id=str(data['vehicle_id']),
            latitude=data['latitude'],
            longitude=data['longitude'],
            speed_kmh=data.get('speed_kmh'),
            recorded_at=now.isoformat(),
        )

        VehiclePosition.objects.create(
            vehicle_id=data['vehicle_id'],
            trip_id=trip_id,
            location=Point(data['longitude'], data['latitude'], srid=4326),
            speed_kmh=data.get('speed_kmh'),
            recorded_at=now,
        )

        if trip_id:
            broadcast_position_update(
                trip_id=str(trip_id),
                vehicle_id=str(data['vehicle_id']),
                latitude=data['latitude'],
                longitude=data['longitude'],
                speed_kmh=data.get('speed_kmh'),
                recorded_at=now.isoformat(),
            )

        return Response({'detail': 'Position recorded.'}, status=status.HTTP_201_CREATED)