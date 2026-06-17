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