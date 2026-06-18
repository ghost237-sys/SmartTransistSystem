from django.contrib.gis.geos import Point
from rest_framework import serializers

from .models import VehiclePosition


class PositionUpdateSerializer(serializers.Serializer):
    """
    Input shape for a driver's GPS ping. Not a ModelSerializer since the
    incoming shape (flat lat/lng) differs from the model's PointField —
    same lat/lng-to-Point conversion pattern as StopSerializer in routing.
    """
    vehicle_id = serializers.UUIDField()
    trip_id = serializers.UUIDField(required=False, allow_null=True)
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    speed_kmh = serializers.FloatField(required=False, allow_null=True)