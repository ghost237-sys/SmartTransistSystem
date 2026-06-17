from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.permissions import IsCommuter
from domains.payments.mpesa import initiate_stk_push, normalize_phone_number
from domains.payments.models import Payment
from domains.routing.models import Trip

from .models import Booking
from .serializers import BookingSerializer


class CreateBookingView(APIView):
    permission_classes = [IsCommuter]

    def post(self, request):
        serializer = BookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        trip_id = serializer.validated_data['trip'].id
        phone_number = serializer.validated_data['phone_number']

        try:
            normalized_phone = normalize_phone_number(phone_number)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                # select_for_update locks this Trip row until the transaction
                # commits or rolls back, so a second concurrent request for
                # the same trip blocks here until this one finishes —
                # preventing two commuters from both grabbing the last seat.
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
            )

        # STK push happens OUTSIDE the transaction/lock deliberately — it's
        # a slow network call to an external API, and holding a database
        # row lock for the duration of a slow HTTP request would block
        # every other booking attempt on this trip for that whole time.
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

        Payment.objects.create(
            tenant=trip.tenant,
            booking=booking,
            amount=trip.fare,
            phone_number=normalized_phone,
            checkout_request_id=stk_response['CheckoutRequestID'],
            status='pending',
        )

        return Response(
            {
                'booking_id': booking.id,
                'status': booking.status,
                'message': 'STK push sent. Enter your M-Pesa PIN to confirm.',
            },
            status=status.HTTP_201_CREATED,
        )