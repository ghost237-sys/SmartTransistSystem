from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.permissions import IsDriver

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
            trip_id=data.get('trip_id'),
            location=Point(data['longitude'], data['latitude'], srid=4326),
            speed_kmh=data.get('speed_kmh'),
            recorded_at=now,
        )

        if data.get('trip_id'):
            broadcast_position_update(
                trip_id=str(data['trip_id']),
                vehicle_id=str(data['vehicle_id']),
                latitude=data['latitude'],
                longitude=data['longitude'],
                speed_kmh=data.get('speed_kmh'),
                recorded_at=now.isoformat(),
            )

        return Response({'detail': 'Position recorded.'}, status=status.HTTP_201_CREATED)