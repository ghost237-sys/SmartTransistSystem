from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import CustomTokenObtainPairSerializer


@method_decorator(
    ratelimit(key='ip', rate='10/m', method='POST', block=True),
    name='dispatch'
)
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    JWT login endpoint. Rate limited to 10 attempts per minute per IP —
    enough for legitimate use (a user retrying a mistyped password),
    not enough for a brute-force attack.
    """
    serializer_class = CustomTokenObtainPairSerializer