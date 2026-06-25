from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    RouteViewSet, StopViewSet, TripViewSet,
    StopSeatAvailabilityView, ListStopsView, PublicTripListView, PublicTripDetailView,
    ConductorTripListView, DriverTripListView, DriverTripDetailView, TripStopsView,
)

router = DefaultRouter()
router.register('routes', RouteViewSet, basename='route')
router.register('stops', StopViewSet, basename='stop')
router.register('trips', TripViewSet, basename='trip')

urlpatterns = [
    # Custom paths MUST come before router.urls to avoid being swallowed
    path('stops/<uuid:stop_id>/seat-availability/', StopSeatAvailabilityView.as_view(), name='stop-seat-availability'),
    path('stops/list/', ListStopsView.as_view(), name='list-stops'),
    path('commuter/trips/', PublicTripListView.as_view(), name='public-trips'),
    path('commuter/trips/<uuid:trip_id>/', PublicTripDetailView.as_view(), name='public-trip-detail'),
    path('conductor/trips/', ConductorTripListView.as_view(), name='conductor-trips'),
    path('driver/trips/', DriverTripListView.as_view(), name='driver-trips'),
    path('driver/trips/<uuid:trip_id>/', DriverTripDetailView.as_view(), name='driver-trip-detail'),
    path('commuter/trips/<uuid:trip_id>/stops/', TripStopsView.as_view(), name='trip-stops'),
] + router.urls