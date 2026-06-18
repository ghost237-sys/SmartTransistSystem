from django.urls import re_path

from .consumers import TripTrackingConsumer

websocket_urlpatterns = [
    re_path(r'ws/trip/(?P<trip_id>[0-9a-f-]+)/tracking/$', TripTrackingConsumer.as_asgi()),
]