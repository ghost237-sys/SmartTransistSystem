from rest_framework import serializers

from .models import QueueEntry, Stage


class StageSerializer(serializers.ModelSerializer):
    loading_bay_count = serializers.ReadOnlyField()
    loading_bay_available = serializers.ReadOnlyField()
    
    class Meta:
        model = Stage
        fields = [
            'id', 'name', 'route', 'loading_bay_capacity',
            'loading_bay_count', 'loading_bay_available', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class QueueEntrySerializer(serializers.ModelSerializer):
    vehicle_code = serializers.CharField(source='vehicle.fleet_code', read_only=True, allow_null=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate_number', read_only=True, allow_null=True)
    driver_name = serializers.SerializerMethodField()
    conductor_name = serializers.SerializerMethodField()
    stage_name = serializers.CharField(source='stage.name', read_only=True)
    queue_position = serializers.ReadOnlyField()
    position = serializers.IntegerField(required=False)
    
    class Meta:
        model = QueueEntry
        fields = [
            'id', 'stage', 'stage_name', 'vehicle', 'vehicle_code', 'vehicle_plate',
            'driver', 'driver_name', 'conductor', 'conductor_name', 'route', 'status', 'confirmed',
            'position', 'time_cap_minutes', 'arrived_at', 'confirmed_at', 'called_up_at',
            'loading_started_at', 'departed_at', 'time_cap_exceeded', 'queue_position', 'trip'
        ]
        read_only_fields = [
            'id', 'arrived_at', 'confirmed_at', 'called_up_at',
            'loading_started_at', 'departed_at', 'time_cap_exceeded', 'queue_position', 'trip'
        ]
    
    def get_driver_name(self, obj):
        return obj.driver.username if obj.driver else None
    
    def get_conductor_name(self, obj):
        return obj.conductor.username if obj.conductor else None


class CheckInSerializer(serializers.Serializer):
    stage_id = serializers.UUIDField()
    vehicle_id = serializers.UUIDField()


class ConfirmSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField()


class CallUpSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField()


class ArrivedAtLoadingBaySerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField()


class DepartSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField()


class QueueStatusSerializer(serializers.Serializer):
    stage_id = serializers.UUIDField()


class ReorderQueueSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField()
    new_position = serializers.IntegerField(min_value=1)


class MarkFullSerializer(serializers.Serializer):
    queue_entry_id = serializers.UUIDField()
