from rest_framework.routers import DefaultRouter

from .views import FleetViewSet, VehicleViewSet

router = DefaultRouter()
router.register('fleets', FleetViewSet, basename='fleet')
router.register('vehicles', VehicleViewSet, basename='vehicle')

urlpatterns = router.urls