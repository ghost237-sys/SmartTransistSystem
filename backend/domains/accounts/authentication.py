from rest_framework_simplejwt.authentication import JWTAuthentication

from domains.tenants.middleware import set_current_tenant


class TenantAwareJWTAuthentication(JWTAuthentication):
    """
    Wraps the standard JWT authentication to also set the thread-local
    tenant context once we know who the authenticated user is — this is
    what makes TenantManager actually scope querysets correctly for API
    requests, since TenantMiddleware alone can't see request.user in time.
    """
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, token = result
            tenant = getattr(user, 'tenant', None)
            set_current_tenant(tenant)
        return result