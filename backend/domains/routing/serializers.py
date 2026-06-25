from django.contrib.gis.geos import LineString, Point
from rest_framework import serializers

from .models import Route, Stop, Trip


class StopSerializer(serializers.ModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = Stop
        fields = ['id', 'name', 'sequence', 'latitude', 'longitude']

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None


class RouteSerializer(serializers.ModelSerializer):
    stops = StopSerializer(many=True, read_only=True)
    path_coordinates = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField()),
        write_only=True,
        help_text='List of [lng, lat] pairs describing the route path.'
    )

    class Meta:
        model = Route
        fields = [
            'id', 'name', 'distance_km', 'estimated_duration_minutes',
            'is_active', 'created_at', 'stops', 'path_coordinates'
        ]
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        coords = validated_data.pop('path_coordinates')
        validated_data['path'] = LineString(coords, srid=4326)
        return super().create(validated_data)


class TripSerializer(serializers.ModelSerializer):
    available_seats = serializers.ReadOnlyField()
    route_name = serializers.CharField(source='route.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate_number', read_only=True)

    class Meta:
        model = Trip
        fields = [
            'id', 'route', 'route_name', 'vehicle', 'vehicle_plate',
            'driver', 'conductor', 'departure_time',
            'total_seats', 'fare', 'status', 'created_at', 'available_seats'
        ]
        read_only_fields = ['id', 'created_at', 'available_seats', 'route_name', 'vehicle_plate']

class SeatAvailabilitySerializer(serializers.Serializer):
    trip_id = serializers.UUIDField()
    seats_opening = serializers.IntegerField()
    vehicle_latitude = serializers.FloatField(allow_null=True)
    vehicle_longitude = serializers.FloatField(allow_null=True)
    distance_km = serializers.FloatField(allow_null=True)
    eta_minutes = serializers.FloatField(allow_null=True)