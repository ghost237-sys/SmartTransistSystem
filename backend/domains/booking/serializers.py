from rest_framework import serializers

from .models import Booking




class BookingSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(write_only=True)

    class Meta:
        model = Booking
        fields = ['id', 'trip', 'status', 'fare_paid', 'created_at', 'confirmed_at', 'phone_number']
        read_only_fields = ['id', 'status', 'fare_paid', 'created_at', 'confirmed_at']


class TicketVerificationSerializer(serializers.Serializer):
    qr_code_token = serializers.CharField(required=False, allow_blank=True)
    short_code = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if not data.get('qr_code_token') and not data.get('short_code'):
            raise serializers.ValidationError('Provide either qr_code_token or short_code.')
        return data


class CashPaymentSerializer(serializers.Serializer):
    trip_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=8, decimal_places=2)
    commuter_phone = serializers.CharField(required=False, allow_blank=True)

class ManifestEntrySerializer(serializers.Serializer):
    booking_id = serializers.UUIDField(source='id')
    commuter = serializers.SerializerMethodField()
    status = serializers.CharField()
    fare_paid = serializers.DecimalField(max_digits=8, decimal_places=2, allow_null=True)
    boarding_stop = serializers.SerializerMethodField()
    alighting_stop = serializers.SerializerMethodField()

    def get_commuter(self, obj):
        return obj.commuter.username if obj.commuter else 'Cash walk-up'

    def get_boarding_stop(self, obj):
        return obj.boarding_stop.name if obj.boarding_stop else 'Route origin'

    def get_alighting_stop(self, obj):
        return obj.alighting_stop.name if obj.alighting_stop else 'Route end'


