from rest_framework import serializers

from .models import Booking



class BookingSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(write_only=True)
    payment_method = serializers.CharField(write_only=True, required=False, default='mpesa')
    boarding_stop_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    alighting_stop_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'trip', 'status', 'fare_paid', 'created_at',
            'confirmed_at', 'phone_number', 'payment_method',
            'boarding_stop_id', 'alighting_stop_id',
        ]
        read_only_fields = ['id', 'status', 'fare_paid', 'created_at', 'confirmed_at']


class TripInfoSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    route_name = serializers.CharField(source='route.name')
    departure_time = serializers.DateTimeField()
    fare = serializers.DecimalField(max_digits=8, decimal_places=2)


class CommuterTicketSerializer(serializers.ModelSerializer):
    trip_details = serializers.SerializerMethodField()
    boarding_stop_name = serializers.SerializerMethodField()
    alighting_stop_name = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id', 'trip', 'trip_details', 'status', 'fare_paid', 'created_at',
            'confirmed_at', 'boarded_at', 'short_code', 'qr_code_token',
            'boarding_stop_name', 'alighting_stop_name',
        ]

    def get_trip_details(self, obj):
        trip = obj.trip
        vehicle = trip.vehicle
        return {
            'id': str(trip.id),
            'route_name': trip.route.name,
            'departure_time': trip.departure_time,
            'fare': trip.fare,
            'fleet_code': vehicle.fleet_code or vehicle.plate_number,
            'vehicle_plate': vehicle.plate_number,
            'vehicle_id': str(vehicle.id),
        }

    def get_boarding_stop_name(self, obj):
        if obj.boarding_stop:
            return obj.boarding_stop.name
        return 'Route origin'

    def get_alighting_stop_name(self, obj):
        if obj.alighting_stop:
            return obj.alighting_stop.name
        return 'Final stop'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.status not in ('confirmed', 'boarded'):
            data['short_code'] = None
            data['qr_code_token'] = None
        return data


class MyTicketSerializer(serializers.ModelSerializer):
    trip = TripInfoSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'trip', 'status', 'fare_paid', 'created_at',
            'confirmed_at', 'boarded_at', 'short_code',
        ]


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


