from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from domains.accounts.permissions import IsFleetOwnerOrSuperAdmin

from .models import User
from .serializers import CustomTokenObtainPairSerializer, StaffSerializer


@method_decorator(
    ratelimit(key='ip', rate='10/m', method='POST', block=True),
    name='dispatch'
)
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        phone_number = request.data.get('phone_number', '')

        if not username or not password:
            return Response(
                {'detail': 'Username and password are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from django.db import IntegrityError
        try:
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=User.Role.COMMUTER,
                phone_number=phone_number
            )
            # Default demo location at Nairobi CBD
            user.demo_latitude = -1.2921
            user.demo_longitude = 36.8219
            user.demo_location_label = 'Nairobi CBD'
            user.save()

            return Response(
                {'message': 'Registration successful. Please log in.'},
                status=status.HTTP_201_CREATED
            )
        except IntegrityError:
            return Response(
                {'detail': 'Username already exists.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class StaffViewSet(viewsets.ModelViewSet):
    serializer_class = StaffSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        qs = User.objects.filter(
            tenant=self.request.user.tenant,
            role__in=[User.Role.DRIVER, User.Role.CONDUCTOR],
        ).order_by('role', 'username')
        role = self.request.query_params.get('role')
        if role in ('driver', 'conductor'):
            qs = qs.filter(role=role)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        from domains.fleet.models import Vehicle
        Vehicle.objects.filter(assigned_driver=user).update(assigned_driver=None)
        Vehicle.objects.filter(assigned_conductor=user).update(assigned_conductor=None)
        return super().destroy(request, *args, **kwargs)
