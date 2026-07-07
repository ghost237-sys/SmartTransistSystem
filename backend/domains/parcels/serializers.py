import secrets
import string
from rest_framework import serializers

from .models import Parcel, ParcelScanEvent
from .utils import generate_tracking_code, generate_qr_token


class ParcelScanEventSerializer(serializers.ModelSerializer):
    scanned_by = serializers.StringRelatedField()
    vehicle = serializers.StringRelatedField()

    class Meta:
        model = ParcelScanEvent
        fields = ['id', 'event_type', 'scanned_by', 'vehicle', 'notes', 'scanned_at']


class ParcelSerializer(serializers.ModelSerializer):
    scan_events = ParcelScanEventSerializer(many=True, read_only=True)
    origin_stop_name = serializers.CharField(source='origin_stop.name', read_only=True, allow_null=True)
    destination_stop_name = serializers.CharField(source='destination_stop.name', read_only=True, allow_null=True)

    class Meta:
        model = Parcel
        fields = [
            'id', 'tracking_code', 'qr_token',
            'sender_name', 'sender_phone',
            'recipient_name', 'recipient_phone',
            'trip', 'origin_stop', 'origin_stop_name',
            'destination_stop', 'destination_stop_name',
            'description', 'weight_kg', 'declared_value', 'fee',
            'status', 'created_at', 'updated_at', 'scan_events',
        ]
        read_only_fields = ['id', 'tracking_code', 'qr_token', 'status', 'created_at', 'updated_at']


class RegisterParcelSerializer(serializers.Serializer):
    sender_name      = serializers.CharField()
    sender_phone     = serializers.CharField()
    recipient_name   = serializers.CharField()
    recipient_phone  = serializers.CharField()
    trip_id          = serializers.UUIDField()
    origin_stop_id   = serializers.UUIDField(required=False, allow_null=True)
    destination_stop_id = serializers.UUIDField(required=False, allow_null=True)
    description      = serializers.CharField(required=False, allow_blank=True)
    weight_kg        = serializers.DecimalField(max_digits=6, decimal_places=2, required=False, allow_null=True)
    declared_value   = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True)
    fee              = serializers.DecimalField(max_digits=8, decimal_places=2, default=0)


class ScanParcelSerializer(serializers.Serializer):
    qr_token   = serializers.CharField()
    event_type = serializers.ChoiceField(choices=ParcelScanEvent.EventType.choices)
    vehicle_id = serializers.UUIDField(required=False, allow_null=True)
    notes      = serializers.CharField(required=False, allow_blank=True)