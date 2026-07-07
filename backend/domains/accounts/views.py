from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import CustomTokenObtainPairSerializer, RegisterSerializer

"""@method_decorator(
    ratelimit(key='ip', rate='10/m', method='POST', block=True),
    name='dispatch'
)"""

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    JWT login endpoint. Rate limited to 10 attempts per minute per IP —
    enough for legitimate use (a user retrying a mistyped password),
    not enough for a brute-force attack.
    """
    serializer_class = CustomTokenObtainPairSerializer


from rest_framework.permissions import AllowAny
from .serializers import RegisterSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            'detail': 'Account created successfully.',
            'username': user.username,
        }, status=status.HTTP_201_CREATED)