from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DocumentAlertsView,
    FinancialExportView,
    FleetAnalyticsView,
    FleetViewSet,
    LiveFleetView,
    VehicleViewSet,
)

router = DefaultRouter()
router.register('fleets', FleetViewSet, basename='fleet')
router.register('vehicles', VehicleViewSet, basename='vehicle')

urlpatterns = router.urls + [
    path('live/', LiveFleetView.as_view(), name='live-fleet'),
    path('tracking/live/', LiveFleetView.as_view(), name='tracking-live-fleet'),
    path('analytics/', FleetAnalyticsView.as_view(), name='fleet-analytics'),
    path('document-alerts/', DocumentAlertsView.as_view(), name='document-alerts'),
    path('export/', FinancialExportView.as_view(), name='financial-export'),
]