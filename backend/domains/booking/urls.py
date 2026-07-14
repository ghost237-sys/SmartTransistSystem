from django.urls import path



from .views import (
    BookingDetailView, BookingPickupStatusView, CompleteTripView, CreateBookingView, DepartTripView,
    MyBookingsView, RecordCashPaymentView, TripManifestView, VerifyTicketView,
    MultiModeBookingView, RedeemOpenReturnView, MyOpenReturnCreditsView,
    CancelTripView, ReassignmentHistoryView, ManualRerouteView,
)

urlpatterns = [
    path('create/', CreateBookingView.as_view(), name='create-booking'),
    path('multi-mode/', MultiModeBookingView.as_view(), name='multi-mode-booking'),
    path('my/', MyBookingsView.as_view(), name='my-bookings'),
    path('my/credits/', MyOpenReturnCreditsView.as_view(), name='my-open-return-credits'),
    path('redeem-return/', RedeemOpenReturnView.as_view(), name='redeem-open-return'),
    path('trips/<uuid:trip_id>/cancel/', CancelTripView.as_view(), name='cancel-trip'),
    path('reassignments/', ReassignmentHistoryView.as_view(), name='reassignment-history'),
    path('manual-reroute/', ManualRerouteView.as_view(), name='manual-reroute'),
    path('<uuid:booking_id>/', BookingDetailView.as_view(), name='booking-detail'),
    path('<uuid:booking_id>/pickup-status/', BookingPickupStatusView.as_view(), name='booking-pickup-status'),
    path('verify-ticket/', VerifyTicketView.as_view(), name='verify-ticket'),
    path('cash-payment/', RecordCashPaymentView.as_view(), name='cash-payment'),
    path('trips/<uuid:trip_id>/manifest/', TripManifestView.as_view(), name='trip-manifest'),
    path('trips/<uuid:trip_id>/depart/', DepartTripView.as_view(), name='trip-depart'),
    path('trips/<uuid:trip_id>/complete/', CompleteTripView.as_view(), name='trip-complete'),
]