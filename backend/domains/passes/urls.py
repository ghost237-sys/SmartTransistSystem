from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PassTierViewSet, CommuterPassViewSet, CreditScoreView, FleetPassTierViewSet
)

router = DefaultRouter()
router.register(r'tiers', PassTierViewSet, basename='passtier')
router.register(r'passes', CommuterPassViewSet, basename='commuterpass')
router.register(r'fleet-tiers', FleetPassTierViewSet, basename='fleetpasstier')

urlpatterns = [
    path('', include(router.urls)),
    path('credit-score/', CreditScoreView.as_view(), name='credit-score'),
]
