from rest_framework import serializers

from .models import Fleet, Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['id', 'fleet', 'plate_number', 'vehicle_type', 'capacity', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class FleetSerializer(serializers.ModelSerializer):
    vehicles = VehicleSerializer(many=True, read_only=True)

    class Meta:
        model = Fleet
        fields = ['id', 'name', 'created_at', 'vehicles']
        read_only_fields = ['id', 'created_at']


class LiveVehicleSerializer(serializers.Serializer):
    vehicle_id = serializers.UUIDField()
    plate_number = serializers.CharField()
    trip_id = serializers.UUIDField(allow_null=True)
    route_name = serializers.CharField(allow_null=True)
    latitude = serializers.FloatField(allow_null=True)
    longitude = serializers.FloatField(allow_null=True)
    speed_kmh = serializers.FloatField(allow_null=True)
    is_online = serializers.BooleanField()


class RouteAnalyticsSerializer(serializers.Serializer):
    route_id = serializers.UUIDField()
    route_name = serializers.CharField()
    total_trips = serializers.IntegerField()
    total_passengers = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_occupancy_percent = serializers.FloatField()


class FleetAnalyticsSerializer(serializers.Serializer):
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_passengers = serializers.IntegerField()
    total_trips = serializers.IntegerField()
    routes = RouteAnalyticsSerializer(many=True)