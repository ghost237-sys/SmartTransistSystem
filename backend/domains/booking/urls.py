from django.urls import path

from .views import (
    CompleteTripView,
    CreateBookingView,
    DepartTripView,
    RecordCashPaymentView,
    TripManifestView,
    VerifyTicketView,
)

urlpatterns = [
    path('create/', CreateBookingView.as_view(), name='create-booking'),
    path('verify-ticket/', VerifyTicketView.as_view(), name='verify-ticket'),
    path('cash-payment/', RecordCashPaymentView.as_view(), name='cash-payment'),
    path('trips/<uuid:trip_id>/manifest/', TripManifestView.as_view(), name='trip-manifest'),
    path('trips/<uuid:trip_id>/depart/', DepartTripView.as_view(), name='trip-depart'),
    path('trips/<uuid:trip_id>/complete/', CompleteTripView.as_view(), name='trip-complete'),
]