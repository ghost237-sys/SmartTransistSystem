from rest_framework import viewsets

from domains.accounts.permissions import IsFleetOwnerOrSuperAdmin

from .models import Fleet, Vehicle
from .serializers import FleetSerializer, VehicleSerializer


class FleetViewSet(viewsets.ModelViewSet):
    serializer_class = FleetSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        return Fleet.objects.all()  # already tenant-scoped by TenantManager

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class VehicleViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        return Vehicle.objects.all()  # already tenant-scoped by TenantManager

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)