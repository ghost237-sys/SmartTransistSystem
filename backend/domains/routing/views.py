from rest_framework import viewsets

from domains.accounts.permissions import IsFleetOwnerOrSuperAdmin

from .models import Route, Stop, Trip
from .serializers import RouteSerializer, StopSerializer, TripSerializer


class RouteViewSet(viewsets.ModelViewSet):
    serializer_class = RouteSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        return Route.objects.all()

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class StopViewSet(viewsets.ModelViewSet):
    serializer_class = StopSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        # Stop has no tenant field of its own — scoped indirectly through its route.
        return Stop.objects.filter(route__tenant=self.request.user.tenant)


class TripViewSet(viewsets.ModelViewSet):
    serializer_class = TripSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]

    def get_queryset(self):
        return Trip.objects.all()

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)