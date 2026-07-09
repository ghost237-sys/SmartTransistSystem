from django.conf import settings
from decouple import config
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.permissions import IsCommuter, IsConductorOrDriver, IsConductor
from domains.payments.mpesa import initiate_stk_push, mock_stk_push, normalize_phone_number
from domains.payments.models import Payment
from domains.routing.models import Trip
from domains.routing.serializers import TripSerializer

from .models import Booking
from .serializers import (
    BookingSerializer,
    CashPaymentSerializer,
    CommuterTicketSerializer,
    ManifestEntrySerializer,
    TicketVerificationSerializer,
)

from django.db.models import Sum


def confirm_booking_payment(booking, payment, receipt=None):
    """Mark a booking paid and issue boarding codes."""
    booking.status = 'confirmed'
    booking.fare_paid = payment.amount
    booking.confirmed_at = timezone.now()
    booking.generate_ticket_codes()
    booking.save()

    payment.status = 'success'
    if receipt:
        payment.mpesa_receipt_number = receipt
    payment.save()

    from domains.notifications.tasks import send_booking_confirmed_sms
    send_booking_confirmed_sms.delay(str(booking.id))


class CreateBookingView(APIView):
    permission_classes = [IsCommuter]

    def post(self, request):
        serializer = BookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        trip_id = serializer.validated_data['trip'].id
        phone_number = serializer.validated_data['phone_number']
        payment_method = serializer.validated_data.get('payment_method', 'mpesa')

        try:
            normalized_phone = normalize_phone_number(phone_number)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        use_mock_payment = config('MPESA_MOCK_PAYMENTS', default=settings.DEBUG, cast=bool)

        with transaction.atomic():
            try:
                trip = Trip.all_objects.select_for_update().get(id=trip_id)
            except Trip.DoesNotExist:
                return Response({'detail': 'Trip not found.'}, status=status.HTTP_404_NOT_FOUND)

            if trip.available_seats <= 0:
                return Response({'detail': 'No seats available on this trip.'}, status=status.HTTP_400_BAD_REQUEST)

            boarding_stop_id = serializer.validated_data.get('boarding_stop_id')
            alighting_stop_id = serializer.validated_data.get('alighting_stop_id')

            booking = Booking.objects.create(
                tenant=trip.tenant,
                trip=trip,
                commuter=request.user,
                status='held',
                boarding_stop_id=boarding_stop_id,
                alighting_stop_id=alighting_stop_id,
            )

        if use_mock_payment:
            stk_response = mock_stk_push(payment_method=payment_method)
        else:
            try:
                stk_response = initiate_stk_push(
                    phone_number=normalized_phone,
                    amount=trip.fare,
                    account_reference=str(booking.id)[:12],
                    transaction_desc=f'Seat booking for {trip.route.name}',
                )
            except Exception as e:
                booking.status = 'cancelled'
                booking.save()
                return Response(
                    {'detail': f'Payment initiation failed: {str(e)}'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        payment = Payment.objects.create(
            tenant=trip.tenant,
            booking=booking,
            amount=trip.fare,
            phone_number=normalized_phone,
            checkout_request_id=stk_response['CheckoutRequestID'],
            status='pending',
        )

        auto_confirm = use_mock_payment or (
            settings.DEBUG
            and config('MPESA_ENV', default='sandbox') == 'sandbox'
            and config('MPESA_AUTO_CONFIRM', default=True, cast=bool)
        )
        if auto_confirm:
            confirm_booking_payment(
                booking, payment,
                receipt=f'MOCK-{payment_method.upper()}-DEMO',
            )

        response_data = {
            'booking_id': booking.id,
            'status': booking.status,
            'payment_method': payment_method,
            'message': (
                'Booking confirmed. Show your ticket to the conductor when boarding.'
                if booking.status == 'confirmed'
                else 'STK push sent. Enter your M-Pesa PIN to confirm.'
            ),
        }
        if booking.status == 'confirmed':
            response_data['short_code'] = booking.short_code
            response_data['qr_code_token'] = booking.qr_code_token

        return Response(response_data, status=status.HTTP_201_CREATED)


class VerifyTicketView(APIView):
    """
    Conductor scans a QR code (or types the 6-digit backup code) to
    verify a passenger's ticket at boarding. Marks the booking as
    'boarded' on success.
    """
    permission_classes = [IsConductor]

    def post(self, request):
        serializer = TicketVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        lookup = {}
        if data.get('qr_code_token'):
            lookup['qr_code_token'] = data['qr_code_token']
        else:
            lookup['short_code'] = data['short_code']

        booking = Booking.all_objects.filter(**lookup).first()

        if booking is None:
            return Response({'valid': False, 'detail': 'Ticket not found.'}, status=status.HTTP_404_NOT_FOUND)

        if booking.trip.conductor_id != request.user.id:
            return Response(
                {'valid': False, 'detail': 'You are not assigned as conductor for this trip.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if booking.trip.status == 'completed':
            return Response(
                {'valid': False, 'detail': 'This trip has already been completed; manifest is locked.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.status == 'boarded':
            return Response(
                {'valid': False, 'detail': 'Ticket already used.', 'boarded_at': booking.boarded_at},
                status=status.HTTP_409_CONFLICT,
            )

        if booking.status != 'confirmed':
            return Response(
                {'valid': False, 'detail': f'Ticket is not valid for boarding (status: {booking.status}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        

        booking.status = 'boarded'
        booking.boarded_at = timezone.now()
        booking.save()

        return Response({
            'valid': True,
            'commuter': booking.commuter.username if booking.commuter else 'Cash walk-up',
            'trip': str(booking.trip_id),
            'boarding_stop': booking.boarding_stop.name if booking.boarding_stop else 'Route origin',
            'alighting_stop': booking.alighting_stop.name if booking.alighting_stop else 'Route end',
        })


class RecordCashPaymentView(APIView):
    """
    Conductor records a cash payment for a walk-up passenger with no
    app booking. Creates a Booking directly in 'boarded' status plus
    a Payment record for audit purposes.
    """
    permission_classes = [IsConductor]

    def post(self, request):
        serializer = CashPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        trip = Trip.all_objects.filter(id=data['trip_id'], conductor=request.user).first()
        if trip is None:
            return Response(
                {'detail': 'Trip not found or you are not assigned as conductor for it.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if trip.status == 'completed':
            return Response(
                {'detail': 'This trip has already been completed; manifest is locked.'},
                status=status.HTTP_400_BAD_REQUEST,
            )


        if data['amount'] != trip.fare:
            return Response(
                {'detail': f'Amount must match the trip fare of {trip.fare}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if trip.available_seats <= 0:
            return Response({'detail': 'No seats available on this trip.'}, status=status.HTTP_400_BAD_REQUEST)

        booking = Booking.objects.create(
            tenant=trip.tenant,
            trip=trip,
            commuter=None,
            status='boarded',
            fare_paid=data['amount'],
            confirmed_at=timezone.now(),
            boarded_at=timezone.now(),
        )
        booking.generate_ticket_codes()
        booking.save()

        Payment.objects.create(
            tenant=trip.tenant,
            booking=booking,
            amount=data['amount'],
            phone_number=data.get('commuter_phone', ''),
            checkout_request_id=f'CASH-{booking.id}',
            status='success',
        )

        return Response({
            'booking_id': booking.id,
            'detail': 'Cash payment recorded.',
        }, status=status.HTTP_201_CREATED)


class DepartTripView(APIView):
    """
    Marks the trip as having left its origin stage. Boarding and cash
    payments continue to work normally after this — passengers can still
    be picked up at stops along the route. This does NOT lock the
    manifest; only CompleteTripView does that.
    """
    permission_classes = [IsConductor]

    def post(self, request, trip_id):
        trip = Trip.all_objects.filter(id=trip_id, conductor=request.user).first()
        if trip is None:
            return Response(
                {'detail': 'Trip not found or you are not assigned as conductor for it.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # On-demand model: trips are always active, no separate 'departed' state
        # This endpoint is deprecated but kept for compatibility
        if trip.status != 'active':
            return Response(
                {'detail': f'Trip must be active to depart.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # No status change needed for on-demand model
        # trip.status = 'departed'  # Removed for on-demand model
        trip.save()

        # Notify confirmed-but-not-boarded passengers that the bus has left
        from domains.notifications.tasks import send_trip_departed_without_boarding_sms
        missed = trip.bookings.filter(status='confirmed')
        for booking in missed:
            send_trip_departed_without_boarding_sms.delay(str(booking.id))

        return Response({'trip_id': str(trip.id), 'status': trip.status})


class CompleteTripView(APIView):
    """
    Marks the trip as fully completed — the bus has reached its final
    stop, no more passengers will be picked up. THIS is the real
    manifest lock: VerifyTicketView and RecordCashPaymentView both check
    trip.status and reject changes once a trip is 'completed'. Also
    returns the final revenue summary.
    """
    permission_classes = [IsConductor]

    def post(self, request, trip_id):
        trip = Trip.all_objects.filter(id=trip_id, conductor=request.user).first()
        if trip is None:
            return Response(
                {'detail': 'Trip not found or you are not assigned as conductor for it.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if trip.status != 'active':
            return Response(
                {'detail': f'Trip cannot be completed from status "{trip.status}". It must be active.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        trip.status = 'completed'
        trip.save()

        boarded_bookings = trip.bookings.filter(status='boarded')
        total_revenue = boarded_bookings.aggregate(total=Sum('fare_paid'))['total'] or 0
        cash_count = boarded_bookings.filter(payments__checkout_request_id__startswith='CASH-').count()
        digital_count = boarded_bookings.count() - cash_count

        return Response({
            'trip_id': str(trip.id),
            'status': trip.status,
            'passengers_boarded': boarded_bookings.count(),
            'total_revenue': total_revenue,
            'digital_payments': digital_count,
            'cash_payments': cash_count,
        })


class MyTicketsView(APIView):
    permission_classes = [IsCommuter]

    def get(self, request):
        bookings = Booking.objects.filter(commuter=request.user).order_by('-created_at')
        serializer = CommuterTicketSerializer(bookings, many=True)
        return Response(serializer.data)


class BookingDetailView(APIView):
    permission_classes = [IsCommuter]

    def get(self, request, booking_id):
        booking = Booking.objects.filter(id=booking_id, commuter=request.user).first()
        if booking is None:
            return Response({'detail': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommuterTicketSerializer(booking)
        return Response(serializer.data)


class BookingPickupStatusView(APIView):
    """Live ETA and vehicle position for a confirmed booking's pickup stop."""
    permission_classes = [IsCommuter]

    def get(self, request, booking_id):
        booking = Booking.objects.filter(
            id=booking_id, commuter=request.user
        ).select_related('trip__vehicle', 'boarding_stop').first()
        if booking is None:
            return Response({'detail': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

        pickup_stop = booking.boarding_stop
        if pickup_stop is None:
            pickup_stop = booking.trip.route.stops.order_by('sequence').first()

        from domains.routing.eta import estimate_arrival
        from domains.tracking.redis_client import get_vehicle_position

        eta_data = estimate_arrival(booking.trip, pickup_stop) if pickup_stop else None
        position = get_vehicle_position(str(booking.trip.vehicle_id))

        return Response({
            'booking_id': str(booking.id),
            'trip_id': str(booking.trip_id),
            'status': booking.status,
            'fleet_code': booking.trip.vehicle.fleet_code or booking.trip.vehicle.plate_number,
            'vehicle_plate': booking.trip.vehicle.plate_number,
            'pickup_stop_id': str(pickup_stop.id) if pickup_stop else None,
            'pickup_stop_name': pickup_stop.name if pickup_stop else None,
            'pickup_latitude': pickup_stop.location.y if pickup_stop and pickup_stop.location else None,
            'pickup_longitude': pickup_stop.location.x if pickup_stop and pickup_stop.location else None,
            'eta_minutes': eta_data['eta_minutes'] if eta_data else None,
            'distance_km': eta_data['distance_km'] if eta_data else None,
            'vehicle_latitude': position['latitude'] if position else None,
            'vehicle_longitude': position['longitude'] if position else None,
            'speed_kmh': position.get('speed_kmh') if position else None,
        })


class ConductorTripsView(APIView):
    permission_classes = [IsConductor]

    def get(self, request):
        trips = Trip.all_objects.filter(conductor=request.user).order_by('-created_at')
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)


class TripManifestView(APIView):
    """
    Passenger list for conductor or driver on an active trip.
    Updates as bookings are confirmed and passengers board.
    """
    permission_classes = [IsConductorOrDriver]

    def get(self, request, trip_id):
        trip = Trip.all_objects.filter(id=trip_id).first()
        if trip is None:
            return Response(
                {'detail': 'Trip not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.user.role == 'conductor' and trip.conductor_id != request.user.id:
            return Response({'detail': 'You are not assigned as conductor for this trip.'}, status=403)
        if request.user.role == 'driver' and trip.driver_id != request.user.id:
            return Response({'detail': 'You are not assigned as driver for this trip.'}, status=403)

        bookings = trip.bookings.exclude(status__in=['expired', 'cancelled']).order_by('created_at')
        serializer = ManifestEntrySerializer(bookings, many=True)

        vehicle = trip.vehicle
        return Response({
            'trip_id': str(trip.id),
            'status': trip.status,
            'route_name': trip.route.name,
            'vehicle_plate': vehicle.plate_number,
            'fleet_code': vehicle.fleet_code or vehicle.plate_number,
            'manifest': serializer.data,
        })


class MyBookingsView(APIView):
    permission_classes = [IsCommuter]

    def get(self, request):
        bookings = Booking.all_objects.filter(
            commuter=request.user
        ).exclude(
            status='expired'
        ).order_by('-created_at')
        serializer = CommuterTicketSerializer(bookings, many=True)
        return Response(serializer.data)