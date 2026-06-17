from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class SmartTransitTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends the default JWT payload with role, tenant_id, and tenant_slug
    so the frontend and DRF views never need a separate /me call just to
    know who they're talking to.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['tenant_id'] = str(user.tenant_id) if user.tenant_id else None
        token['tenant_slug'] = user.tenant.slug if user.tenant_id else None
        return token


class SmartTransitTokenObtainPairView(TokenObtainPairView):
    serializer_class = SmartTransitTokenObtainPairSerializer