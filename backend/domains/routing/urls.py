from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import RouteViewSet, StopViewSet, TripViewSet, StopSeatAvailabilityView

router = DefaultRouter()
router.register('routes', RouteViewSet, basename='route')
router.register('stops', StopViewSet, basename='stop')
router.register('trips', TripViewSet, basename='trip')

urlpatterns = router.urls + [
    path('stops/<uuid:stop_id>/seat-availability/', StopSeatAvailabilityView.as_view(), name='stop-seat-availability'),
]