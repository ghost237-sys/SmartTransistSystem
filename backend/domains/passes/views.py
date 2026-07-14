from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.permissions import IsFleetOwnerOrSuperAdmin
from .models import PassTier, CommuterPass, CreditScore
from .serializers import (
    PassTierSerializer, CommuterPassSerializer, CreateCommuterPassSerializer,
    UsePassSerializer, RenewPassSerializer, CreditScoreSerializer
)


class PassTierViewSet(viewsets.ReadOnlyModelViewSet):
    """View available pass tiers (read-only for commuters)."""
    serializer_class = PassTierSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        qs = PassTier.objects.filter(is_active=True)
        
        # Filter by tenant for fleet owners
        if self.request.user.role in ['fleet_owner', 'super_admin']:
            qs = qs.filter(tenant=self.request.user.tenant)
        # For commuters, show tiers from their tenant if they have one
        elif self.request.user.tenant:
            qs = qs.filter(tenant=self.request.user.tenant)
        
        tier_type = self.request.query_params.get('type')
        if tier_type:
            qs = qs.filter(tier_type=tier_type)
        return qs


class CommuterPassViewSet(viewsets.ModelViewSet):
    """Manage commuter passes."""
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role == 'commuter':
            return CommuterPass.objects.filter(user=self.request.user)
        return CommuterPass.objects.filter(tenant=self.request.user.tenant)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateCommuterPassSerializer
        return CommuterPassSerializer
    
    def perform_create(self, serializer):
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def my_pass(self, request):
        """Get the current user's active pass."""
        try:
            pass_instance = CommuterPass.objects.get(
                user=request.user,
                status=CommuterPass.Status.ACTIVE
            )
            serializer = CommuterPassSerializer(pass_instance)
            return Response(serializer.data)
        except CommuterPass.DoesNotExist:
            return Response({'detail': 'No active pass found'}, status=404)
    
    @action(detail=True, methods=['post'])
    def use(self, request, pk=None):
        """Use the pass for a trip."""
        pass_instance = self.get_object()
        serializer = UsePassSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result)
    
    @action(detail=True, methods=['post'])
    def renew(self, request, pk=None):
        """Renew a pass (for prepaid tiers)."""
        pass_instance = self.get_object()
        serializer = RenewPassSerializer(
            data={},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a pass."""
        pass_instance = self.get_object()
        if pass_instance.status != CommuterPass.Status.ACTIVE:
            return Response(
                {'detail': 'Only active passes can be cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        pass_instance.status = CommuterPass.Status.CANCELLED
        pass_instance.save()
        return Response({'detail': 'Pass cancelled successfully'})


class CreditScoreView(APIView):
    """View and manage credit score for post-paid eligibility."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current user's credit score."""
        try:
            credit_score = request.user.credit_score
            serializer = CreditScoreSerializer(credit_score)
            return Response(serializer.data)
        except CreditScore.DoesNotExist:
            # Create initial credit score
            credit_score = CreditScore.objects.create(user=request.user)
            serializer = CreditScoreSerializer(credit_score)
            return Response(serializer.data)
    
    def post(self, request):
        """Recalculate credit score."""
        try:
            credit_score = request.user.credit_score
            credit_score.calculate_score()
            serializer = CreditScoreSerializer(credit_score)
            return Response(serializer.data)
        except CreditScore.DoesNotExist:
            credit_score = CreditScore.objects.create(user=request.user)
            serializer = CreditScoreSerializer(credit_score)
            return Response(serializer.data)


class FleetPassTierViewSet(viewsets.ModelViewSet):
    """Fleet owners can manage pass tiers for their fleet."""
    serializer_class = PassTierSerializer
    permission_classes = [IsFleetOwnerOrSuperAdmin]
    
    def get_queryset(self):
        return PassTier.objects.all()
    
    def perform_create(self, serializer):
        serializer.save()
