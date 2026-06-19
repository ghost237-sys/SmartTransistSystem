from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.booking.models import Booking

from .models import Payment


class MpesaCallbackView(APIView):
    """
    Daraja posts here asynchronously once the customer enters their PIN
    (or cancels, or the request times out). No auth — Safaricom can't
    send our JWT tokens — so this endpoint must validate by other means
    in production (IP allowlisting or a shared secret in the URL path).
    For sandbox testing, we accept it open.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        body = request.data.get('Body', {})
        stk_callback = body.get('stkCallback', {})

        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')

        if not checkout_request_id:
            return Response({'detail': 'Malformed callback.'}, status=400)

        try:
            payment = Payment.all_objects.get(checkout_request_id=checkout_request_id)
        except Payment.DoesNotExist:
            return Response({'detail': 'Payment record not found.'}, status=404)

        payment.raw_callback = request.data

        if result_code == 0:
            metadata_items = stk_callback.get('CallbackMetadata', {}).get('Item', [])
            receipt = next(
                (item['Value'] for item in metadata_items if item.get('Name') == 'MpesaReceiptNumber'),
                None,
            )
            payment.status = 'success'
            payment.mpesa_receipt_number = receipt
            payment.save()

            booking = payment.booking
            booking.status = 'confirmed'
            booking.fare_paid = payment.amount
            booking.confirmed_at = timezone.now()
            booking.generate_ticket_codes()
            booking.save()

            # Fire SMS notification asynchronously via Celery
            from domains.notifications.tasks import send_booking_confirmed_sms
            send_booking_confirmed_sms.delay(str(booking.id))

        return Response({'detail': 'Callback processed.'}, status=200)