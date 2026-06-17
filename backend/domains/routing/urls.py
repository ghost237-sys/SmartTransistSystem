from rest_framework.routers import DefaultRouter

from .views import RouteViewSet, StopViewSet, TripViewSet

router = DefaultRouter()
router.register('routes', RouteViewSet, basename='route')
router.register('stops', StopViewSet, basename='stop')
router.register('trips', TripViewSet, basename='trip')

urlpatterns = router.urls