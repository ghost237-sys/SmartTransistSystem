from django.contrib.gis.geos import LineString, Point
from rest_framework import serializers

from .models import Route, Stop, Trip, TransferStation, LinkedRoute


class StopSerializer(serializers.ModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    route_id = serializers.UUIDField(source='route.id', read_only=True)
    route_name = serializers.CharField(source='route.name', read_only=True)

    class Meta:
        model = Stop
        fields = ['id', 'name', 'sequence', 'latitude', 'longitude', 'route_id', 'route_name']

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
    fleet_code = serializers.SerializerMethodField()

    def get_fleet_code(self, obj):
        return obj.vehicle.fleet_code or obj.vehicle.plate_number

    class Meta:
        model = Trip
        fields = [
            'id', 'route', 'route_name', 'vehicle', 'vehicle_plate', 'fleet_code',
            'driver', 'conductor', 'departure_time',
            'total_seats', 'fare', 'status', 'created_at', 'available_seats'
        ]
        read_only_fields = ['id', 'created_at', 'available_seats', 'route_name', 'vehicle_plate', 'fleet_code']

class SeatAvailabilitySerializer(serializers.Serializer):
    trip_id = serializers.UUIDField()
    seats_opening = serializers.IntegerField()
    vehicle_latitude = serializers.FloatField(allow_null=True)
    vehicle_longitude = serializers.FloatField(allow_null=True)
    distance_km = serializers.FloatField(allow_null=True)
    eta_minutes = serializers.FloatField(allow_null=True)


class FindRideResultSerializer(serializers.Serializer):
    trip_id = serializers.UUIDField()
    route_name = serializers.CharField()
    fleet_code = serializers.CharField()
    vehicle_plate = serializers.CharField()
    available_seats = serializers.IntegerField()
    fare = serializers.DecimalField(max_digits=8, decimal_places=2)
    pickup_stop_id = serializers.UUIDField()
    pickup_stop_name = serializers.CharField()
    eta_minutes = serializers.FloatField()
    distance_km = serializers.FloatField()
    vehicle_latitude = serializers.FloatField()
    vehicle_longitude = serializers.FloatField()
    speed_kmh = serializers.FloatField(allow_null=True)


class TransferStationSerializer(serializers.ModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = TransferStation
        fields = ['id', 'name', 'latitude', 'longitude', 'buffer_minutes', 'is_active', 'created_at']

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None


class LinkedRouteSerializer(serializers.ModelSerializer):
    first_route_name = serializers.CharField(source='first_route.name', read_only=True)
    second_route_name = serializers.CharField(source='second_route.name', read_only=True)
    transfer_station_name = serializers.CharField(source='transfer_station.name', read_only=True)
    first_route_stop_name = serializers.CharField(source='first_route_stop.name', read_only=True)
    second_route_stop_name = serializers.CharField(source='second_route_stop.name', read_only=True)

    class Meta:
        model = LinkedRoute
        fields = [
            'id', 'first_route', 'first_route_name', 'second_route', 'second_route_name',
            'transfer_station', 'transfer_station_name', 'first_route_stop',
            'first_route_stop_name', 'second_route_stop', 'second_route_stop_name',
            'is_active', 'created_at'
        ]


class LinkedJourneySerializer(serializers.Serializer):
    """
    Serializer for unified journey results that combine two legs.
    """
    linked_route_id = serializers.UUIDField()
    first_leg = FindRideResultSerializer()
    second_leg = FindRideResultSerializer()
    transfer_station_name = serializers.CharField()
    total_fare = serializers.DecimalField(max_digits=8, decimal_places=2)
    total_duration_minutes = serializers.FloatField()
    transfer_buffer_minutes = serializers.IntegerField()
    is_safe_transfer = serializers.BooleanField()