from django.urls import path

from .views import ParcelListView, RegisterParcelView, ScanParcelView, TrackParcelView

urlpatterns = [
    path('register/', RegisterParcelView.as_view(), name='parcel-register'),
    path('scan/', ScanParcelView.as_view(), name='parcel-scan'),
    path('track/<str:tracking_code>/', TrackParcelView.as_view(), name='parcel-track'),
    path('', ParcelListView.as_view(), name='parcel-list'),
]