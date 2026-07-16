from django.conf import settings
from decouple import config
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.permissions import IsCommuter, IsConductorOrDriver, IsConductor, IsFleetOwnerOrSuperAdmin
from domains.payments.mpesa import initiate_stk_push, mock_stk_push, normalize_phone_number
from domains.payments.models import Payment
from domains.routing.models import Trip
from domains.routing.serializers import TripSerializer

from .models import Booking, TwoWayBooking, LinkedBooking, OpenReturnCredit, BookingReassignment
from .serializers import (
    BookingSerializer,
    CashPaymentSerializer,
    CommuterTicketSerializer,
    ManifestEntrySerializer,
    TicketVerificationSerializer,
    MultiModeBookingSerializer,
    OpenReturnCreditSerializer,
    LinkedBookingSerializer,
    RedeemOpenReturnSerializer,
)

from django.db.models import Sum


def confirm_booking_payment(booking, payment, receipt=None):
    """Mark a booking paid and issue boarding codes. Handle different booking types."""
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

    # Handle linked bookings based on booking type
    if booking.linked_booking:
        linked_booking = booking.linked_booking
        
        # For return trips (RETURN_OUTWARD/RETURN_INWARD), confirm both legs
        if booking.booking_type == Booking.BookingType.RETURN_OUTWARD or booking.booking_type == Booking.BookingType.RETURN_INWARD:
            linked_fare = payment.amount - booking.trip.fare
            if linked_fare > 0:
                linked_booking.status = 'confirmed'
                linked_booking.fare_paid = linked_fare
                linked_booking.confirmed_at = timezone.now()
                linked_booking.generate_ticket_codes()
                linked_booking.save()
                send_booking_confirmed_sms.delay(str(linked_booking.id))
        
        # For linked trips (LINK_LEG_1/LINK_LEG_2), keep leg 2 in pending_transfer monitoring
        elif booking.booking_type == Booking.BookingType.LINK_LEG_1:
            # Leg 1 is confirmed, Leg 2 stays in pending_transfer monitoring
            # Leg 2 will be confirmed when passenger approaches transfer station
            pass  # No action needed - leg 2 remains in pending_transfer status


class CreateBookingView(APIView):
    permission_classes = [IsCommuter]

    def post(self, request):
        serializer = BookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        trip_id = serializer.validated_data['trip'].id
        phone_number = serializer.validated_data['phone_number']
        payment_method = serializer.validated_data.get('payment_method', 'mpesa')
        use_pass = serializer.validated_data.get('use_pass', False)

        # Handle pass-based payment
        if use_pass:
            from domains.passes.models import CommuterPass, PassUsage
            from domains.passes.serializers import UsePassSerializer
            
            try:
                pass_instance = CommuterPass.objects.get(
                    user=request.user,
                    status=CommuterPass.Status.ACTIVE
                )
            except CommuterPass.DoesNotExist:
                return Response(
                    {'detail': 'No active commuter pass found.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate pass can be used
            if not pass_instance.can_use_pass():
                return Response(
                    {'detail': 'Pass cannot be used. Check expiration or balance.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # For prepaid passes, check remaining trips
            if pass_instance.tier.tier_type in [CommuterPass.TierType.WEEKLY, CommuterPass.TierType.MONTHLY]:
                if pass_instance.trips_remaining <= 0:
                    return Response(
                        {'detail': 'No trips remaining on this pass.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # For post-paid, check credit limit
            if pass_instance.tier.tier_type == CommuterPass.TierType.POSTPAID:
                from decimal import Decimal
                trip = Trip.objects.get(id=trip_id)
                discounted_fare = trip.fare * (Decimal('1') - pass_instance.tier.discount_percent / Decimal('100'))
                if pass_instance.current_balance + discounted_fare > pass_instance.credit_limit:
                    return Response(
                        {'detail': 'Transaction would exceed credit limit.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        try:
            normalized_phone = normalize_phone_number(phone_number)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Update user's phone number if not set (progressive profile building)
        if not request.user.phone_number:
            request.user.phone_number = normalized_phone
            request.user.save(update_fields=['phone_number'])

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

        # Handle pass-based booking confirmation
        if use_pass:
            from domains.passes.models import CommuterPass, PassUsage, CreditTransaction
            from decimal import Decimal
            
            pass_instance = CommuterPass.objects.get(
                user=request.user,
                status=CommuterPass.Status.ACTIVE
            )
            
            # Calculate discount
            discount_percent = pass_instance.tier.discount_percent
            discount_amount = trip.fare * (discount_percent / Decimal('100'))
            final_amount = trip.fare - discount_amount
            
            # Use the trip
            pass_instance.use_trip(trip.fare)
            
            # Create pass usage record
            route_name = trip.route.name if trip.route else ''
            PassUsage.objects.create(
                pass_instance=pass_instance,
                booking=booking,
                original_fare=trip.fare,
                discount_applied=discount_amount,
                final_amount=final_amount,
                route_name=route_name
            )
            
            # For post-paid, create credit transaction
            if pass_instance.tier.tier_type == CommuterPass.TierType.POSTPAID:
                balance_before = pass_instance.current_balance - final_amount
                balance_after = pass_instance.current_balance
                
                CreditTransaction.objects.create(
                    pass_instance=pass_instance,
                    transaction_type=CreditTransaction.TransactionType.CHARGE,
                    amount=final_amount,
                    balance_before=balance_before,
                    balance_after=balance_after,
                    description=f'Trip charge - {route_name}',
                    reference=str(booking.id)
                )
            
            # Confirm booking with pass payment
            booking.status = 'confirmed'
            booking.fare_paid = final_amount
            booking.confirmed_at = timezone.now()
            booking.generate_ticket_codes()
            booking.save()
            
            from domains.notifications.tasks import send_booking_confirmed_sms
            send_booking_confirmed_sms.delay(str(booking.id))
            
            return Response({
                'booking_id': booking.id,
                'status': booking.status,
                'payment_method': 'pass',
                'message': 'Booking confirmed using commuter pass. Show your ticket to the conductor when boarding.',
                'pass_used': pass_instance.tier.name,
                'discount_applied': float(discount_amount),
                'final_amount': float(final_amount),
                'short_code': booking.short_code,
                'qr_code_token': booking.qr_code_token,
            }, status=status.HTTP_201_CREATED)

        # Original M-Pesa payment flow
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


class MultiModeBookingView(APIView):
    """
    Unified booking endpoint supporting all four trip modes:
    - Single trip: One-way booking
    - Return immediate: Book both legs upfront
    - Return open: Book outward, get credit for flexible return
    - Linked: Transfer journey with pending bay
    """
    permission_classes = [IsCommuter]

    def post(self, request):
        serializer = MultiModeBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        trip_mode = data['trip_mode']
        phone_number = data['phone_number']
        payment_method = data.get('payment_method', 'mpesa')
        use_pass = data.get('use_pass', False)

        try:
            normalized_phone = normalize_phone_number(phone_number)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Update user's phone number if not set (progressive profile building)
        if not request.user.phone_number:
            request.user.phone_number = normalized_phone
            request.user.save(update_fields=['phone_number'])

        use_mock_payment = config('MPESA_MOCK_PAYMENTS', default=settings.DEBUG, cast=bool)

        # Route to appropriate mode handler
        if trip_mode == 'single':
            return self._handle_single_trip(request, data, normalized_phone, payment_method, use_pass, use_mock_payment)
        elif trip_mode == 'return_immediate':
            return self._handle_return_immediate(request, data, normalized_phone, payment_method, use_pass, use_mock_payment)
        elif trip_mode == 'return_open':
            return self._handle_return_open(request, data, normalized_phone, payment_method, use_pass, use_mock_payment)
        elif trip_mode == 'linked':
            return self._handle_linked_trip(request, data, normalized_phone, payment_method, use_pass, use_mock_payment)

    def _handle_single_trip(self, request, data, phone_number, payment_method, use_pass, use_mock_payment):
        """Handle Mode 1: Single trip booking"""
        from decimal import Decimal
        
        trip_id = data['trip_id']
        boarding_stop_id = data.get('boarding_stop_id')
        alighting_stop_id = data.get('alighting_stop_id')

        with transaction.atomic():
            try:
                trip = Trip.all_objects.select_for_update().get(id=trip_id)
            except Trip.DoesNotExist:
                return Response({'detail': 'Trip not found.'}, status=status.HTTP_404_NOT_FOUND)

            if trip.available_seats <= 0:
                return Response({'detail': 'No seats available on this trip.'}, status=status.HTTP_400_BAD_REQUEST)

            booking = Booking.objects.create(
                tenant=trip.tenant,
                trip=trip,
                commuter=request.user,
                status='held',
                booking_type=Booking.BookingType.SINGLE,
                boarding_stop_id=boarding_stop_id,
                alighting_stop_id=alighting_stop_id,
            )

        # Handle pass-based payment
        if use_pass:
            return self._process_pass_payment(request, booking, trip)

        # Process M-Pesa payment
        return self._process_payment(booking, trip, phone_number, payment_method, use_mock_payment)

    def _handle_return_immediate(self, request, data, phone_number, payment_method, use_pass, use_mock_payment):
        """Handle Mode 2: Return trip - book both legs immediately using new booking_type and linked_booking fields"""
        from decimal import Decimal
        
        outbound_trip_id = data['outbound_trip_id']
        return_trip_id = data['return_trip_id']
        outbound_boarding_stop_id = data.get('outbound_boarding_stop_id')
        outbound_alighting_stop_id = data.get('outbound_alighting_stop_id')
        return_boarding_stop_id = data.get('return_boarding_stop_id')
        return_alighting_stop_id = data.get('return_alighting_stop_id')

        with transaction.atomic():
            try:
                outbound_trip = Trip.all_objects.select_for_update().get(id=outbound_trip_id)
                return_trip = Trip.all_objects.select_for_update().get(id=return_trip_id)
            except Trip.DoesNotExist:
                return Response({'detail': 'One or both trips not found.'}, status=status.HTTP_404_NOT_FOUND)

            if outbound_trip.available_seats <= 0 or return_trip.available_seats <= 0:
                return Response({'detail': 'No seats available on one or both trips.'}, status=status.HTTP_400_BAD_REQUEST)

            total_fare = outbound_trip.fare + return_trip.fare

            # Create outbound booking (RETURN_OUTWARD)
            outbound_booking = Booking.objects.create(
                tenant=outbound_trip.tenant,
                trip=outbound_trip,
                commuter=request.user,
                status='held',
                booking_type=Booking.BookingType.RETURN_OUTWARD,
                boarding_stop_id=outbound_boarding_stop_id,
                alighting_stop_id=outbound_alighting_stop_id,
            )

            # Create return booking (RETURN_INWARD with PENDING_PAYMENT status)
            return_booking = Booking.objects.create(
                tenant=return_trip.tenant,
                trip=return_trip,
                commuter=request.user,
                status='held',  # Will be set to pending_payment after linking
                booking_type=Booking.BookingType.RETURN_INWARD,
                boarding_stop_id=return_boarding_stop_id,
                alighting_stop_id=return_alighting_stop_id,
            )

            # Link the bookings together
            outbound_booking.linked_booking = return_booking
            return_booking.linked_booking = outbound_booking
            outbound_booking.save()
            return_booking.save()

            # Set return booking to pending_payment status
            return_booking.status = 'held'  # Both held until payment confirmed
            return_booking.save()

        # Handle pass-based payment
        if use_pass:
            return self._process_pass_payment_for_return_linked(request, outbound_booking, return_booking, outbound_trip, return_trip)

        # Process M-Pesa payment for total fare
        return self._process_payment_for_return_linked(outbound_booking, return_booking, outbound_trip, return_trip, phone_number, payment_method, use_mock_payment)

    def _handle_return_open(self, request, data, phone_number, payment_method, use_pass, use_mock_payment):
        """Handle Mode 2b: Return trip - open return credit"""
        from decimal import Decimal
        from datetime import timedelta
        
        outbound_trip_id = data['outbound_trip_id']
        outbound_boarding_stop_id = data.get('outbound_boarding_stop_id')
        outbound_alighting_stop_id = data.get('outbound_alighting_stop_id')
        return_window_hours = data.get('return_window_hours', 24)

        with transaction.atomic():
            try:
                outbound_trip = Trip.all_objects.select_for_update().get(id=outbound_trip_id)
            except Trip.DoesNotExist:
                return Response({'detail': 'Trip not found.'}, status=status.HTTP_404_NOT_FOUND)

            if outbound_trip.available_seats <= 0:
                return Response({'detail': 'No seats available on this trip.'}, status=status.HTTP_400_BAD_REQUEST)

            # Create outbound booking
            outbound_booking = Booking.objects.create(
                tenant=outbound_trip.tenant,
                trip=outbound_trip,
                commuter=request.user,
                status='held',
                boarding_stop_id=outbound_boarding_stop_id,
                alighting_stop_id=outbound_alighting_stop_id,
            )

        # Handle pass-based payment for outbound only
        if use_pass:
            result = self._process_pass_payment(request, outbound_booking, outbound_trip)
            if result.status_code != 201:
                return result
            
            # Create open return credit after successful payment
            return self._create_open_return_credit(outbound_booking, outbound_trip, return_window_hours)

        # Process M-Pesa payment for outbound fare only
        result = self._process_payment(outbound_booking, outbound_trip, phone_number, payment_method, use_mock_payment)
        if result.status_code != 201:
            return result
        
        # Create open return credit after successful payment
        return self._create_open_return_credit(outbound_booking, outbound_trip, return_window_hours)

    def _handle_linked_trip(self, request, data, phone_number, payment_method, use_pass, use_mock_payment):
        """Handle Mode 3: Linked trip with transfer bay"""
        from decimal import Decimal
        
        first_leg_trip_id = data['first_leg_trip_id']
        second_leg_trip_id = data['second_leg_trip_id']
        first_leg_boarding_stop_id = data.get('first_leg_boarding_stop_id')
        first_leg_alighting_stop_id = data.get('first_leg_alighting_stop_id')
        second_leg_boarding_stop_id = data.get('second_leg_boarding_stop_id')
        second_leg_alighting_stop_id = data.get('second_leg_alighting_stop_id')
        transfer_station_id = data['transfer_station_id']

        with transaction.atomic():
            try:
                first_trip = Trip.all_objects.select_for_update().get(id=first_leg_trip_id)
                second_trip = Trip.all_objects.select_for_update().get(id=second_leg_trip_id)
                from domains.routing.models import TransferStation, LinkedRoute
                try:
                    # Frontend passes linked_route_id as transfer_station_id, try looking it up as LinkedRoute first
                    linked_route = LinkedRoute.objects.get(id=transfer_station_id)
                    transfer_station = linked_route.transfer_station
                except LinkedRoute.DoesNotExist:
                    transfer_station = TransferStation.objects.get(id=transfer_station_id)
            except (Trip.DoesNotExist, TransferStation.DoesNotExist):
                return Response({'detail': 'Trip or transfer station not found.'}, status=status.HTTP_404_NOT_FOUND)

            if first_trip.available_seats <= 0:
                return Response({'detail': 'No seats available on first leg.'}, status=status.HTTP_400_BAD_REQUEST)

            # Create first leg booking (LINK_LEG_1 - immediate seat lock)
            first_booking = Booking.objects.create(
                tenant=first_trip.tenant,
                trip=first_trip,
                commuter=request.user,
                status='held',
                booking_type=Booking.BookingType.LINK_LEG_1,
                boarding_stop_id=first_leg_boarding_stop_id,
                alighting_stop_id=first_leg_alighting_stop_id,
            )

            # Create second leg booking (LINK_LEG_2 - held in pending bay, no seat decrement)
            second_booking = Booking.objects.create(
                tenant=second_trip.tenant,
                trip=second_trip,
                commuter=request.user,
                status='pending_transfer',  # Held in pending bay - doesn't count toward available_seats
                booking_type=Booking.BookingType.LINK_LEG_2,
                boarding_stop_id=second_leg_boarding_stop_id,
                alighting_stop_id=second_leg_alighting_stop_id,
                pending_transfer_stop=transfer_station,  # Store transfer station for monitoring
            )

            # Link the bookings together using linked_booking field
            first_booking.linked_booking = second_booking
            second_booking.linked_booking = first_booking
            first_booking.save()
            second_booking.save()

        # Calculate total fare (first leg only initially, second leg fare reserved)
        total_fare = first_trip.fare

        # Handle pass-based payment for first leg only
        if use_pass:
            result = self._process_pass_payment(request, first_booking, first_trip)
            if result.status_code != 201:
                # Rollback second leg booking
                second_booking.delete()
                first_booking.delete()
                return result
            
            first_booking.status = 'confirmed'
            first_booking.save()
            
            return Response({
                'booking_id': first_booking.id,
                'second_leg_booking_id': second_booking.id,
                'status': 'confirmed',
                'payment_method': 'pass',
                'message': 'First leg confirmed. Second leg will be booked automatically when you approach the transfer station.',
                'first_leg': CommuterTicketSerializer(first_booking).data,
                'second_leg_status': 'pending_transfer',
            }, status=status.HTTP_201_CREATED)

        # Process M-Pesa payment for first leg fare
        result = self._process_payment(first_booking, first_trip, phone_number, payment_method, use_mock_payment)
        if result.status_code != 201:
            # Rollback second leg booking
            second_booking.delete()
            first_booking.delete()
            return result
        
        first_booking.status = 'confirmed'
        first_booking.save()

        return Response({
            'booking_id': first_booking.id,
            'second_leg_booking_id': second_booking.id,
            'status': 'confirmed',
            'payment_method': payment_method,
            'message': 'First leg confirmed. Second leg will be booked automatically when you approach the transfer station.',
            'first_leg': CommuterTicketSerializer(first_booking).data,
            'second_leg_status': 'pending_transfer',
        }, status=status.HTTP_201_CREATED)

    def _process_payment(self, booking, trip, phone_number, payment_method, use_mock_payment):
        """Process M-Pesa payment for a single booking"""
        if use_mock_payment:
            stk_response = mock_stk_push(payment_method=payment_method)
        else:
            try:
                stk_response = initiate_stk_push(
                    phone_number=phone_number,
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
            phone_number=phone_number,
            checkout_request_id=stk_response['CheckoutRequestID'],
            status='pending',
        )

        auto_confirm = use_mock_payment or (
            settings.DEBUG
            and config('MPESA_ENV', default='sandbox') == 'sandbox'
            and config('MPESA_AUTO_CONFIRM', default=True, cast=bool)
        )
        if auto_confirm:
            receipt = stk_response.get('receipt', f'MOCK-{payment_method.upper()}-DEMO')
            confirm_booking_payment(
                booking, payment,
                receipt=receipt,
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

    def _process_payment_for_return(self, outbound_booking, return_booking, two_way_booking, outbound_trip, return_trip, phone_number, payment_method, use_mock_payment):
        """Process M-Pesa payment for return trip (both legs)"""
        total_fare = outbound_trip.fare + return_trip.fare
        
        if use_mock_payment:
            stk_response = mock_stk_push(payment_method=payment_method)
        else:
            try:
                stk_response = initiate_stk_push(
                    phone_number=phone_number,
                    amount=total_fare,
                    account_reference=str(two_way_booking.id)[:12],
                    transaction_desc=f'Return trip booking for {outbound_trip.route.name}',
                )
            except Exception as e:
                outbound_booking.status = 'cancelled'
                return_booking.status = 'cancelled'
                outbound_booking.save()
                return_booking.save()
                two_way_booking.status = TwoWayBooking.Status.CANCELLED
                two_way_booking.save()
                return Response(
                    {'detail': f'Payment initiation failed: {str(e)}'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        payment = Payment.objects.create(
            tenant=outbound_trip.tenant,
            booking=outbound_booking,
            amount=total_fare,
            phone_number=phone_number,
            checkout_request_id=stk_response['CheckoutRequestID'],
            status='pending',
        )

        auto_confirm = use_mock_payment or (
            settings.DEBUG
            and config('MPESA_ENV', default='sandbox') == 'sandbox'
            and config('MPESA_AUTO_CONFIRM', default=True, cast=bool)
        )
        if auto_confirm:
            # Confirm both bookings
            outbound_booking.status = 'confirmed'
            outbound_booking.fare_paid = outbound_trip.fare
            outbound_booking.confirmed_at = timezone.now()
            outbound_booking.generate_ticket_codes()
            outbound_booking.save()

            return_booking.status = 'confirmed'
            return_booking.fare_paid = return_trip.fare
            return_booking.confirmed_at = timezone.now()
            return_booking.generate_ticket_codes()
            return_booking.save()

            two_way_booking.status = TwoWayBooking.Status.CONFIRMED
            two_way_booking.fare_paid = total_fare
            two_way_booking.confirmed_at = timezone.now()
            two_way_booking.save()

            payment.status = 'success'
            payment.mpesa_receipt_number = f'MOCK-{payment_method.upper()}-DEMO'
            payment.save()

            from domains.notifications.tasks import send_booking_confirmed_sms
            send_booking_confirmed_sms.delay(str(outbound_booking.id))
            send_booking_confirmed_sms.delay(str(return_booking.id))

        return Response({
            'two_way_booking_id': two_way_booking.id,
            'outbound_booking_id': outbound_booking.id,
            'return_booking_id': return_booking.id,
            'status': two_way_booking.status,
            'payment_method': payment_method,
            'message': (
                'Return trip confirmed. Show your tickets to the conductor when boarding.'
                if two_way_booking.status == TwoWayBooking.Status.CONFIRMED
                else 'STK push sent. Enter your M-Pesa PIN to confirm.'
            ),
            'outbound_leg': CommuterTicketSerializer(outbound_booking).data if outbound_booking.status == 'confirmed' else None,
            'return_leg': CommuterTicketSerializer(return_booking).data if return_booking.status == 'confirmed' else None,
        }, status=status.HTTP_201_CREATED)

    def _process_pass_payment(self, request, booking, trip):
        """Process pass-based payment for single booking"""
        from domains.passes.models import CommuterPass, PassUsage
        from decimal import Decimal
        
        try:
            pass_instance = CommuterPass.objects.get(
                user=request.user,
                status=CommuterPass.Status.ACTIVE
            )
        except CommuterPass.DoesNotExist:
            return Response(
                {'detail': 'No active commuter pass found.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not pass_instance.can_use_pass():
            return Response(
                {'detail': 'Pass cannot be used. Check expiration or balance.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if pass_instance.tier.tier_type in [CommuterPass.TierType.WEEKLY, CommuterPass.TierType.MONTHLY]:
            if pass_instance.trips_remaining <= 0:
                return Response(
                    {'detail': 'No trips remaining on this pass.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if pass_instance.tier.tier_type == CommuterPass.TierType.POSTPAID:
            discounted_fare = trip.fare * (Decimal('1') - pass_instance.tier.discount_percent / Decimal('100'))
            if pass_instance.current_balance + discounted_fare > pass_instance.credit_limit:
                return Response(
                    {'detail': 'Transaction would exceed credit limit.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Calculate discount
        discount_percent = pass_instance.tier.discount_percent
        discount_amount = trip.fare * (discount_percent / Decimal('100'))
        final_amount = trip.fare - discount_amount
        
        # Use the trip
        pass_instance.use_trip(trip.fare)
        
        # Create pass usage record
        route_name = trip.route.name if trip.route else ''
        PassUsage.objects.create(
            pass_instance=pass_instance,
            booking=booking,
            original_fare=trip.fare,
            discount_applied=discount_amount,
            final_amount=final_amount,
            route_name=route_name
        )
        
        # For post-paid, create credit transaction
        if pass_instance.tier.tier_type == CommuterPass.TierType.POSTPAID:
            from domains.passes.models import CreditTransaction
            balance_before = pass_instance.current_balance - final_amount
            balance_after = pass_instance.current_balance
            
            CreditTransaction.objects.create(
                pass_instance=pass_instance,
                transaction_type=CreditTransaction.TransactionType.CHARGE,
                amount=final_amount,
                balance_before=balance_before,
                balance_after=balance_after,
                description=f'Trip charge - {route_name}',
                reference=str(booking.id)
            )
        
        # Confirm booking
        booking.status = 'confirmed'
        booking.fare_paid = final_amount
        booking.confirmed_at = timezone.now()
        booking.generate_ticket_codes()
        booking.save()
        
        from domains.notifications.tasks import send_booking_confirmed_sms
        send_booking_confirmed_sms.delay(str(booking.id))
        
        return Response({
            'booking_id': booking.id,
            'status': booking.status,
            'payment_method': 'pass',
            'message': 'Booking confirmed using commuter pass.',
            'pass_used': pass_instance.tier.name,
            'discount_applied': float(discount_amount),
            'final_amount': float(final_amount),
            'short_code': booking.short_code,
            'qr_code_token': booking.qr_code_token,
        }, status=status.HTTP_201_CREATED)

    def _process_payment_for_return_linked(self, outbound_booking, return_booking, outbound_trip, return_trip, phone_number, payment_method, use_mock_payment):
        """Process M-Pesa payment for linked return trip (both legs)"""
        total_fare = outbound_trip.fare + return_trip.fare
        
        if use_mock_payment:
            stk_response = mock_stk_push(payment_method=payment_method)
        else:
            try:
                stk_response = initiate_stk_push(
                    phone_number=phone_number,
                    amount=total_fare,
                    account_reference=str(outbound_booking.id)[:12],
                    transaction_desc=f'Return trip booking for {outbound_trip.route.name}',
                )
            except Exception as e:
                outbound_booking.status = 'cancelled'
                return_booking.status = 'cancelled'
                outbound_booking.save()
                return_booking.save()
                return Response(
                    {'detail': f'Payment initiation failed: {str(e)}'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        payment = Payment.objects.create(
            tenant=outbound_trip.tenant,
            booking=outbound_booking,
            amount=total_fare,
            phone_number=phone_number,
            checkout_request_id=stk_response['CheckoutRequestID'],
            status='pending',
        )

        auto_confirm = use_mock_payment or (
            settings.DEBUG
            and config('MPESA_ENV', default='sandbox') == 'sandbox'
            and config('MPESA_AUTO_CONFIRM', default=True, cast=bool)
        )
        if auto_confirm:
            # Confirm both bookings
            outbound_booking.status = 'confirmed'
            outbound_booking.fare_paid = outbound_trip.fare
            outbound_booking.confirmed_at = timezone.now()
            outbound_booking.generate_ticket_codes()
            outbound_booking.save()

            return_booking.status = 'confirmed'
            return_booking.fare_paid = return_trip.fare
            return_booking.confirmed_at = timezone.now()
            return_booking.generate_ticket_codes()
            return_booking.save()

            receipt = stk_response.get('receipt', f'MOCK-{payment_method.upper()}-DEMO')
            payment.status = 'success'
            payment.mpesa_receipt_number = receipt
            payment.save()

            from domains.notifications.tasks import send_booking_confirmed_sms
            send_booking_confirmed_sms.delay(str(outbound_booking.id))
            send_booking_confirmed_sms.delay(str(return_booking.id))

        return Response({
            'outbound_booking_id': outbound_booking.id,
            'return_booking_id': return_booking.id,
            'status': outbound_booking.status,
            'payment_method': payment_method,
            'message': (
                'Return trip confirmed. Show your tickets to the conductor when boarding.'
                if outbound_booking.status == 'confirmed'
                else 'STK push sent. Enter your M-Pesa PIN to confirm.'
            ),
            'outbound_leg': CommuterTicketSerializer(outbound_booking).data if outbound_booking.status == 'confirmed' else None,
            'return_leg': CommuterTicketSerializer(return_booking).data if return_booking.status == 'confirmed' else None,
        }, status=status.HTTP_201_CREATED)

    def _process_pass_payment_for_return_linked(self, request, outbound_booking, return_booking, outbound_trip, return_trip):
        """Process pass-based payment for linked return trip"""
        from domains.passes.models import CommuterPass, PassUsage
        from decimal import Decimal
        
        try:
            pass_instance = CommuterPass.objects.get(
                user=request.user,
                status=CommuterPass.Status.ACTIVE
            )
        except CommuterPass.DoesNotExist:
            return Response(
                {'detail': 'No active commuter pass found.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        total_fare = outbound_trip.fare + return_trip.fare
        discount_percent = pass_instance.tier.discount_percent
        discount_amount = total_fare * (discount_percent / Decimal('100'))
        final_amount = total_fare - discount_amount
        
        # Use two trips
        pass_instance.use_trip(outbound_trip.fare)
        pass_instance.use_trip(return_trip.fare)
        
        # Create pass usage records
        PassUsage.objects.create(
            pass_instance=pass_instance,
            booking=outbound_booking,
            original_fare=outbound_trip.fare,
            discount_applied=outbound_trip.fare * (discount_percent / Decimal('100')),
            final_amount=outbound_trip.fare - (outbound_trip.fare * (discount_percent / Decimal('100'))),
            route_name=outbound_trip.route.name if outbound_trip.route else ''
        )
        
        PassUsage.objects.create(
            pass_instance=pass_instance,
            booking=return_booking,
            original_fare=return_trip.fare,
            discount_applied=return_trip.fare * (discount_percent / Decimal('100')),
            final_amount=return_trip.fare - (return_trip.fare * (discount_percent / Decimal('100'))),
            route_name=return_trip.route.name if return_trip.route else ''
        )
        
        # Confirm both bookings
        outbound_booking.status = 'confirmed'
        outbound_booking.fare_paid = outbound_trip.fare - (outbound_trip.fare * (discount_percent / Decimal('100')))
        outbound_booking.confirmed_at = timezone.now()
        outbound_booking.generate_ticket_codes()
        outbound_booking.save()

        return_booking.status = 'confirmed'
        return_booking.fare_paid = return_trip.fare - (return_trip.fare * (discount_percent / Decimal('100')))
        return_booking.confirmed_at = timezone.now()
        return_booking.generate_ticket_codes()
        return_booking.save()

        from domains.notifications.tasks import send_booking_confirmed_sms
        send_booking_confirmed_sms.delay(str(outbound_booking.id))
        send_booking_confirmed_sms.delay(str(return_booking.id))
        
        return Response({
            'outbound_booking_id': outbound_booking.id,
            'return_booking_id': return_booking.id,
            'status': 'confirmed',
            'payment_method': 'pass',
            'message': 'Return trip confirmed using commuter pass.',
            'pass_used': pass_instance.tier.name,
            'discount_applied': float(discount_amount),
            'final_amount': float(final_amount),
            'outbound_leg': CommuterTicketSerializer(outbound_booking).data,
            'return_leg': CommuterTicketSerializer(return_booking).data,
        }, status=status.HTTP_201_CREATED)

    def _process_pass_payment_for_return(self, request, outbound_booking, return_booking, two_way_booking, outbound_trip, return_trip):
        """Process pass-based payment for return trip"""
        from domains.passes.models import CommuterPass, PassUsage
        from decimal import Decimal
        
        try:
            pass_instance = CommuterPass.objects.get(
                user=request.user,
                status=CommuterPass.Status.ACTIVE
            )
        except CommuterPass.DoesNotExist:
            return Response(
                {'detail': 'No active commuter pass found.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        total_fare = outbound_trip.fare + return_trip.fare
        discount_percent = pass_instance.tier.discount_percent
        discount_amount = total_fare * (discount_percent / Decimal('100'))
        final_amount = total_fare - discount_amount
        
        # Use two trips
        pass_instance.use_trip(outbound_trip.fare)
        pass_instance.use_trip(return_trip.fare)
        
        # Create pass usage records
        PassUsage.objects.create(
            pass_instance=pass_instance,
            booking=outbound_booking,
            original_fare=outbound_trip.fare,
            discount_applied=outbound_trip.fare * (discount_percent / Decimal('100')),
            final_amount=outbound_trip.fare - (outbound_trip.fare * (discount_percent / Decimal('100'))),
            route_name=outbound_trip.route.name if outbound_trip.route else ''
        )
        
        PassUsage.objects.create(
            pass_instance=pass_instance,
            booking=return_booking,
            original_fare=return_trip.fare,
            discount_applied=return_trip.fare * (discount_percent / Decimal('100')),
            final_amount=return_trip.fare - (return_trip.fare * (discount_percent / Decimal('100'))),
            route_name=return_trip.route.name if return_trip.route else ''
        )
        
        # Confirm both bookings
        outbound_booking.status = 'confirmed'
        outbound_booking.fare_paid = outbound_trip.fare - (outbound_trip.fare * (discount_percent / Decimal('100')))
        outbound_booking.confirmed_at = timezone.now()
        outbound_booking.generate_ticket_codes()
        outbound_booking.save()

        return_booking.status = 'confirmed'
        return_booking.fare_paid = return_trip.fare - (return_trip.fare * (discount_percent / Decimal('100')))
        return_booking.confirmed_at = timezone.now()
        return_booking.generate_ticket_codes()
        return_booking.save()

        two_way_booking.status = TwoWayBooking.Status.CONFIRMED
        two_way_booking.fare_paid = final_amount
        two_way_booking.confirmed_at = timezone.now()
        two_way_booking.save()
        
        from domains.notifications.tasks import send_booking_confirmed_sms
        send_booking_confirmed_sms.delay(str(outbound_booking.id))
        send_booking_confirmed_sms.delay(str(return_booking.id))
        
        return Response({
            'two_way_booking_id': two_way_booking.id,
            'outbound_booking_id': outbound_booking.id,
            'return_booking_id': return_booking.id,
            'status': two_way_booking.status,
            'payment_method': 'pass',
            'message': 'Return trip confirmed using commuter pass.',
            'pass_used': pass_instance.tier.name,
            'discount_applied': float(discount_amount),
            'final_amount': float(final_amount),
            'outbound_leg': CommuterTicketSerializer(outbound_booking).data,
            'return_leg': CommuterTicketSerializer(return_booking).data,
        }, status=status.HTTP_201_CREATED)

    def _create_open_return_credit(self, outbound_booking, outbound_trip, return_window_hours):
        """Create open return credit after successful outbound booking"""
        from datetime import timedelta
        
        valid_from = timezone.now() + timedelta(hours=1)  # Credit valid 1 hour after departure
        valid_until = timezone.now() + timedelta(hours=return_window_hours)
        
        # Estimate return fare (same as outbound for simplicity)
        credit_amount = outbound_trip.fare
        
        credit = OpenReturnCredit.objects.create(
            tenant=outbound_booking.tenant,
            commuter=outbound_booking.commuter,
            outbound_booking=outbound_booking,
            credit_amount=credit_amount,
            status=OpenReturnCredit.Status.ACTIVE,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        
        return Response({
            'booking_id': outbound_booking.id,
            'credit_id': credit.id,
            'credit_amount': float(credit_amount),
            'valid_from': valid_from,
            'valid_until': valid_until,
            'message': f'Outbound trip confirmed. You have an open return credit of KES {credit_amount} valid until {valid_until}.',
            'outbound_leg': CommuterTicketSerializer(outbound_booking).data,
        }, status=status.HTTP_201_CREATED)


class RedeemOpenReturnView(APIView):
    """Redeem open return credit for a return trip"""
    permission_classes = [IsCommuter]

    def post(self, request):
        serializer = RedeemOpenReturnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        credit_id = data['credit_id']
        return_trip_id = data['return_trip_id']
        return_boarding_stop_id = data.get('return_boarding_stop_id')
        return_alighting_stop_id = data.get('return_alighting_stop_id')

        with transaction.atomic():
            try:
                credit = OpenReturnCredit.objects.select_for_update().get(
                    id=credit_id,
                    commuter=request.user,
                    status=OpenReturnCredit.Status.ACTIVE
                )
            except OpenReturnCredit.DoesNotExist:
                return Response(
                    {'detail': 'Active credit not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if not credit.is_valid():
                return Response(
                    {'detail': 'Credit is not valid for redemption (expired or not yet valid).'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                return_trip = Trip.all_objects.select_for_update().get(id=return_trip_id)
            except Trip.DoesNotExist:
                return Response(
                    {'detail': 'Return trip not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if return_trip.available_seats <= 0:
                return Response(
                    {'detail': 'No seats available on return trip.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if credit amount covers the fare
            if credit.credit_amount < return_trip.fare:
                return Response(
                    {'detail': f'Credit amount KES {credit.credit_amount} is insufficient for trip fare KES {return_trip.fare}.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create return booking
            return_booking = Booking.objects.create(
                tenant=return_trip.tenant,
                trip=return_trip,
                commuter=request.user,
                status='confirmed',
                fare_paid=return_trip.fare,
                boarding_stop_id=return_boarding_stop_id,
                alighting_stop_id=return_alighting_stop_id,
                confirmed_at=timezone.now(),
            )
            return_booking.generate_ticket_codes()
            return_booking.save()
            
            # Redeem the credit
            credit.redeem(return_booking)
            
            from domains.notifications.tasks import send_booking_confirmed_sms
            send_booking_confirmed_sms.delay(str(return_booking.id))

        return Response({
            'booking_id': return_booking.id,
            'credit_id': credit.id,
            'status': return_booking.status,
            'message': 'Return trip booked using open return credit.',
            'fare_paid': float(return_booking.fare_paid),
            'short_code': return_booking.short_code,
            'qr_code_token': return_booking.qr_code_token,
        }, status=status.HTTP_201_CREATED)


class MyOpenReturnCreditsView(APIView):
    """View user's active open return credits"""
    permission_classes = [IsCommuter]

    def get(self, request):
        credits = OpenReturnCredit.objects.filter(
            commuter=request.user,
            status=OpenReturnCredit.Status.ACTIVE
        ).order_by('-created_at')
        serializer = OpenReturnCreditSerializer(credits, many=True)
        return Response(serializer.data)


class CancelTripView(APIView):
    """
    Fleet owner endpoint to cancel a trip and trigger automatic reassignment.
    This will:
    1. Cancel the trip
    2. Trigger the handle_bus_cancellation Celery task
    3. Automatically reassign affected bookings to available alternatives
    4. Notify affected commuters
    5. Alert admins if manual intervention is needed
    """
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def post(self, request, trip_id):
        from .tasks import handle_bus_cancellation
        
        try:
            trip = Trip.objects.get(id=trip_id)
        except Trip.DoesNotExist:
            return Response(
                {'detail': 'Trip not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if trip belongs to the fleet owner's tenant
        if trip.tenant != request.user.tenant and request.user.role != 'super_admin':
            return Response(
                {'detail': 'You do not have permission to cancel this trip.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if trip is already cancelled or completed
        if trip.status in ['cancelled', 'completed']:
            return Response(
                {'detail': f'Trip is already {trip.status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get cancellation reason from request
        reason = request.data.get('reason', 'bus_cancelled')
        
        # Trigger the cancellation task asynchronously
        task = handle_bus_cancellation.delay(str(trip_id), reason)
        
        return Response({
            'detail': 'Trip cancellation initiated. Automatic reassignment in progress.',
            'task_id': task.id,
            'trip_id': str(trip_id),
        }, status=status.HTTP_202_ACCEPTED)


class ReassignmentHistoryView(APIView):
    """
    View reassignment history for a specific booking or all reassignments.
    Used for audit trails and debugging.
    """
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get(self, request):
        booking_id = request.query_params.get('booking_id')
        status_filter = request.query_params.get('status')
        
        queryset = BookingReassignment.objects.all()
        
        # Filter by tenant for fleet owners
        if request.user.role == 'fleet_owner':
            queryset = queryset.filter(tenant=request.user.tenant)
        
        # Filter by booking if specified
        if booking_id:
            queryset = queryset.filter(booking_id=booking_id)
        
        # Filter by status if specified
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Order by most recent
        queryset = queryset.order_by('-created_at')
        
        # Serialize the results
        results = []
        for reassignment in queryset:
            results.append({
                'id': str(reassignment.id),
                'booking_id': str(reassignment.booking.id),
                'commuter': reassignment.booking.commuter.username if reassignment.booking.commuter else 'Cash walk-up',
                'original_trip_id': str(reassignment.original_trip.id) if reassignment.original_trip else None,
                'new_trip_id': str(reassignment.new_trip.id) if reassignment.new_trip else None,
                'reason': reassignment.reason,
                'status': reassignment.status,
                'original_departure_time': reassignment.original_departure_time,
                'new_departure_time': reassignment.new_departure_time,
                'original_vehicle_plate': reassignment.original_vehicle_plate,
                'new_vehicle_plate': reassignment.new_vehicle_plate,
                'notification_sent': reassignment.notification_sent,
                'created_at': reassignment.created_at,
                'resolved_at': reassignment.resolved_at,
                'admin_notes': reassignment.admin_notes,
            })
        
        return Response(results)


class ManualRerouteView(APIView):
    """
    Admin endpoint for manual rerouting of bookings flagged as PENDING_MANUAL_REROUTE.
    Allows fleet owners to manually assign alternative trips when automatic reassignment fails.
    """
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def post(self, request):
        booking_id = request.data.get('booking_id')
        new_trip_id = request.data.get('new_trip_id')
        admin_notes = request.data.get('admin_notes', '')
        
        if not booking_id or not new_trip_id:
            return Response(
                {'detail': 'booking_id and new_trip_id are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                booking = Booking.objects.select_for_update().get(id=booking_id)
                new_trip = Trip.objects.select_for_update().get(id=new_trip_id)
                
                # Check if booking is pending manual reroute
                if booking.status != 'pending_manual_reroute':
                    return Response(
                        {'detail': 'Booking is not pending manual reroute.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check if new trip has available seats
                if new_trip.available_seats <= 0:
                    return Response(
                        {'detail': 'New trip has no available seats.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Get the original reassignment record
                original_reassignment = BookingReassignment.objects.filter(
                    booking=booking,
                    status=BookingReassignment.ReassignmentStatus.PENDING_MANUAL
                ).first()
                
                if not original_reassignment:
                    return Response(
                        {'detail': 'No pending reassignment record found.'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # Execute manual reassignment
                from .services import BusCancellationService
                BusCancellationService._execute_reassignment(
                    booking,
                    original_reassignment.original_trip,
                    new_trip,
                    original_reassignment.reason
                )
                
                # Update the reassignment record
                original_reassignment.new_trip = new_trip
                original_reassignment.status = BookingReassignment.ReassignmentStatus.SUCCESS
                original_reassignment.new_departure_time = new_trip.departure_time
                original_reassignment.new_vehicle_plate = new_trip.vehicle.plate_number
                original_reassignment.admin_notes = admin_notes
                original_reassignment.admin_user = request.user
                original_reassignment.resolved_at = timezone.now()
                original_reassignment.save()
                
                return Response({
                    'detail': 'Manual reroute successful.',
                    'booking_id': str(booking.id),
                    'new_trip_id': str(new_trip.id),
                }, status=status.HTTP_200_OK)
                
        except Booking.DoesNotExist:
            return Response(
                {'detail': 'Booking not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Trip.DoesNotExist:
            return Response(
                {'detail': 'Trip not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'detail': f'Manual reroute failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )