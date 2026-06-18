from django.urls import path

from .views import PositionUpdateView

urlpatterns = [
    path('position/', PositionUpdateView.as_view(), name='position-update'),
]