from rest_framework import generics, permissions
from domains.accounts.serializers import RegisterUserSerializer, UserProfileSerializer
from domains.accounts.permissions import IsSuperAdmin


class RegisterUserView(generics.CreateAPIView):
    """
    Super admin only — creates fleet owners, drivers, conductors, commuters.
    Self-registration is handled separately for commuters in Phase 4.
    """
    serializer_class = RegisterUserSerializer
    permission_classes = [IsSuperAdmin]


class MeView(generics.RetrieveAPIView):
    """Returns the authenticated user's profile."""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user