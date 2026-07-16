from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, StaffViewSet, DeviceHandshakeView,
    RequestDeviceMigrationView, VerifyDeviceMigrationView,
    CommuterProfileStatusView, CommuterProfileUpdateView, MeView
)

router = DefaultRouter()
router.register(r'staff', StaffViewSet, basename='staff')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('me/', MeView.as_view(), name='me'),
    path('device/handshake/', DeviceHandshakeView.as_view(), name='device-handshake'),
    path('device/migration/request/', RequestDeviceMigrationView.as_view(), name='device-migration-request'),
    path('device/migration/verify/', VerifyDeviceMigrationView.as_view(), name='device-migration-verify'),
    path('commuter/profile/status/', CommuterProfileStatusView.as_view(), name='commuter-profile-status'),
    path('commuter/profile/update/', CommuterProfileUpdateView.as_view(), name='commuter-profile-update'),
]

urlpatterns += router.urls