from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'super_admin'
        )


class IsFleetOwner(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'fleet_owner'
        )


class IsDriver(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'driver'
        )


class IsConductor(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'conductor'
        )


class IsCommuter(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'commuter'
        )


class IsFleetOwnerOrSuperAdmin(BasePermission):
    """For endpoints that both fleet owners and super admins can access."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in ('fleet_owner', 'super_admin')
        )


class IsSameTenant(BasePermission):
    """
    Object-level guard. Ensures the requesting user belongs to the same
    tenant as the object being accessed. Use alongside role checks.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'super_admin':
            return True
        tenant = getattr(obj, 'tenant', None)
        return tenant is not None and tenant == request.user.tenant