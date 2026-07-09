from django.urls import path



from .views import (
    BookingDetailView, BookingPickupStatusView, CompleteTripView, CreateBookingView, DepartTripView,
    MyBookingsView, RecordCashPaymentView, TripManifestView, VerifyTicketView,
)

urlpatterns = [
    path('create/', CreateBookingView.as_view(), name='create-booking'),
    path('my/', MyBookingsView.as_view(), name='my-bookings'),
    path('<uuid:booking_id>/', BookingDetailView.as_view(), name='booking-detail'),
    path('<uuid:booking_id>/pickup-status/', BookingPickupStatusView.as_view(), name='booking-pickup-status'),
    path('verify-ticket/', VerifyTicketView.as_view(), name='verify-ticket'),
    path('cash-payment/', RecordCashPaymentView.as_view(), name='cash-payment'),
    path('trips/<uuid:trip_id>/manifest/', TripManifestView.as_view(), name='trip-manifest'),
    path('trips/<uuid:trip_id>/depart/', DepartTripView.as_view(), name='trip-depart'),
    path('trips/<uuid:trip_id>/complete/', CompleteTripView.as_view(), name='trip-complete'),
]