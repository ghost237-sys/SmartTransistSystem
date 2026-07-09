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
        return Response({'detail': 'Use staff management to create fleet accounts.'}, status=405)


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
