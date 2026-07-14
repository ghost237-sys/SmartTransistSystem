from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta

from .models import Booking, TwoWayBooking, TransactionalVoucher, OpenReturnCredit, LinkedBooking



class BookingSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(write_only=True)
    payment_method = serializers.CharField(write_only=True, required=False, default='mpesa')
    boarding_stop_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    alighting_stop_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    use_pass = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Booking
        fields = [
            'id', 'trip', 'status', 'fare_paid', 'created_at',
            'confirmed_at', 'phone_number', 'payment_method',
            'boarding_stop_id', 'alighting_stop_id', 'use_pass',
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
    linked_booking_details = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id', 'trip', 'trip_details', 'status', 'fare_paid', 'created_at',
            'confirmed_at', 'boarded_at', 'short_code', 'qr_code_token',
            'boarding_stop_name', 'alighting_stop_name', 'booking_type',
            'linked_booking_details',
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

    def get_linked_booking_details(self, obj):
        if obj.linked_booking:
            linked = obj.linked_booking
            trip = linked.trip
            vehicle = trip.vehicle
            return {
                'id': str(linked.id),
                'booking_type': linked.booking_type,
                'status': linked.status,
                'fare_paid': linked.fare_paid,
                'short_code': linked.short_code if linked.status in ('confirmed', 'boarded') else None,
                'qr_code_token': linked.qr_code_token if linked.status in ('confirmed', 'boarded') else None,
                'boarding_stop_name': linked.boarding_stop.name if linked.boarding_stop else 'Route origin',
                'alighting_stop_name': linked.alighting_stop.name if linked.alighting_stop else 'Final stop',
                'trip_details': {
                    'id': str(trip.id),
                    'route_name': trip.route.name,
                    'departure_time': trip.departure_time,
                    'fare': trip.fare,
                    'fleet_code': vehicle.fleet_code or vehicle.plate_number,
                    'vehicle_plate': vehicle.plate_number,
                    'vehicle_id': str(vehicle.id),
                }
            }
        return None

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


class TwoWayBookingSerializer(serializers.ModelSerializer):
    """Serializer for creating and viewing two-way bookings."""
    outbound_trip_id = serializers.UUIDField(write_only=True)
    return_trip_id = serializers.UUIDField(write_only=True)
    outbound_boarding_stop_id = serializers.UUIDField(write_only=True)
    outbound_alighting_stop_id = serializers.UUIDField(write_only=True)
    return_boarding_stop_id = serializers.UUIDField(write_only=True)
    return_alighting_stop_id = serializers.UUIDField(write_only=True)
    payment_method = serializers.CharField(write_only=True, default='mpesa')

    class Meta:
        model = TwoWayBooking
        fields = [
            'id', 'commuter', 'status', 'total_fare', 'fare_paid',
            'outbound_trip_id', 'return_trip_id',
            'outbound_boarding_stop_id', 'outbound_alighting_stop_id',
            'return_boarding_stop_id', 'return_alighting_stop_id',
            'payment_method', 'connection_buffer_minutes',
            'created_at', 'confirmed_at',
        ]
        read_only_fields = ['id', 'status', 'fare_paid', 'created_at', 'confirmed_at']


class TwoWayBookingDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for viewing two-way booking with legs."""
    legs = serializers.SerializerMethodField()
    recovery_options = serializers.SerializerMethodField()

    class Meta:
        model = TwoWayBooking
        fields = [
            'id', 'commuter', 'status', 'total_fare', 'fare_paid',
            'connection_buffer_minutes', 'transfer_station',
            'recovery_option_chosen', 'recovery_trip',
            'voucher_amount', 'voucher_expires_at',
            'created_at', 'confirmed_at', 'first_leg_boarded_at', 'completed_at',
            'legs', 'recovery_options',
        ]

    def get_legs(self, obj):
        legs = obj.legs.all().order_by('leg_order')
        return CommuterTicketSerializer(legs, many=True).data

    def get_recovery_options(self, obj):
        """Get available recovery options if connection was missed."""
        if obj.status != TwoWayBooking.Status.MISSED_CONNECTION:
            return None

        from .services import ReRoutingService
        return_leg = obj.get_return_leg()
        if return_leg:
            alternatives = ReRoutingService.find_alternative_trips(
                return_leg,
                return_leg.boarding_stop,
                return_leg.alighting_stop
            )
            return TripInfoSerializer(alternatives, many=True).data
        return None


class RecoveryOptionSerializer(serializers.Serializer):
    """Serializer for choosing recovery option when connection is missed."""
    recovery_option = serializers.ChoiceField(choices=['re_route', 'refund'])
    alternative_trip_id = serializers.UUIDField(required=False, allow_null=True)


class TransactionalVoucherSerializer(serializers.ModelSerializer):
    """Serializer for transactional vouchers."""
    class Meta:
        model = TransactionalVoucher
        fields = [
            'id', 'amount', 'status', 'expires_at',
            'redeemed_at', 'created_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'redeemed_at']


class MultiModeBookingSerializer(serializers.Serializer):
    """
    Base serializer for multi-mode booking requests.
    Handles all four trip modes: single, return immediate, return open, linked.
    """
    trip_mode = serializers.ChoiceField(
        choices=[
            ('single', 'Single Trip'),
            ('return_immediate', 'Return Trip - Immediate'),
            ('return_open', 'Return Trip - Open'),
            ('linked', 'Linked Trip'),
        ]
    )
    phone_number = serializers.CharField(write_only=True)
    payment_method = serializers.CharField(write_only=True, required=False, default='mpesa')
    use_pass = serializers.BooleanField(write_only=True, required=False, default=False)
    
    # Single trip fields
    trip_id = serializers.UUIDField(required=False, allow_null=True)
    boarding_stop_id = serializers.UUIDField(required=False, allow_null=True)
    alighting_stop_id = serializers.UUIDField(required=False, allow_null=True)
    
    # Return trip fields
    outbound_trip_id = serializers.UUIDField(required=False, allow_null=True)
    outbound_boarding_stop_id = serializers.UUIDField(required=False, allow_null=True)
    outbound_alighting_stop_id = serializers.UUIDField(required=False, allow_null=True)
    return_trip_id = serializers.UUIDField(required=False, allow_null=True)
    return_boarding_stop_id = serializers.UUIDField(required=False, allow_null=True)
    return_alighting_stop_id = serializers.UUIDField(required=False, allow_null=True)
    
    # Open return specific fields
    return_window_hours = serializers.IntegerField(required=False, default=24, min_value=1, max_value=168)
    
    # Linked trip fields
    first_leg_trip_id = serializers.UUIDField(required=False, allow_null=True)
    first_leg_boarding_stop_id = serializers.UUIDField(required=False, allow_null=True)
    first_leg_alighting_stop_id = serializers.UUIDField(required=False, allow_null=True)
    second_leg_trip_id = serializers.UUIDField(required=False, allow_null=True)
    second_leg_boarding_stop_id = serializers.UUIDField(required=False, allow_null=True)
    second_leg_alighting_stop_id = serializers.UUIDField(required=False, allow_null=True)
    transfer_station_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, data):
        trip_mode = data.get('trip_mode')
        
        if trip_mode == 'single':
            if not data.get('trip_id'):
                raise serializers.ValidationError({'trip_id': 'Required for single trip mode.'})
        
        elif trip_mode == 'return_immediate':
            if not data.get('outbound_trip_id') or not data.get('return_trip_id'):
                raise serializers.ValidationError({
                    'outbound_trip_id': 'Required for return immediate mode.',
                    'return_trip_id': 'Required for return immediate mode.'
                })
        
        elif trip_mode == 'return_open':
            if not data.get('outbound_trip_id'):
                raise serializers.ValidationError({'outbound_trip_id': 'Required for return open mode.'})
        
        elif trip_mode == 'linked':
            if not all([
                data.get('first_leg_trip_id'),
                data.get('second_leg_trip_id'),
                data.get('transfer_station_id')
            ]):
                raise serializers.ValidationError({
                    'first_leg_trip_id': 'Required for linked mode.',
                    'second_leg_trip_id': 'Required for linked mode.',
                    'transfer_station_id': 'Required for linked mode.'
                })
        
        return data


class OpenReturnCreditSerializer(serializers.ModelSerializer):
    """Serializer for open return credits."""
    class Meta:
        model = OpenReturnCredit
        fields = [
            'id', 'credit_amount', 'status', 'valid_from', 'valid_until',
            'redeemed_at', 'created_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'redeemed_at']


class LinkedBookingSerializer(serializers.ModelSerializer):
    """Serializer for linked trip bookings."""
    first_leg_details = serializers.SerializerMethodField()
    second_leg_details = serializers.SerializerMethodField()

    class Meta:
        model = LinkedBooking
        fields = [
            'id', 'status', 'transfer_station', 'linked_route',
            'first_leg_details', 'second_leg_details',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']

    def get_first_leg_details(self, obj):
        return CommuterTicketSerializer(obj.first_leg_booking).data

    def get_second_leg_details(self, obj):
        return CommuterTicketSerializer(obj.second_leg_booking).data


class RedeemOpenReturnSerializer(serializers.Serializer):
    """Serializer for redeeming open return credit."""
    credit_id = serializers.UUIDField()
    return_trip_id = serializers.UUIDField()
    return_boarding_stop_id = serializers.UUIDField(required=False, allow_null=True)
    return_alighting_stop_id = serializers.UUIDField(required=False, allow_null=True)
