from rest_framework_simplejwt.authentication import JWTAuthentication
from domains.tenants.middleware import set_current_tenant


class TenantJWTAuthentication(JWTAuthentication):
    """
    Extends SimpleJWT's authentication to set the thread-local tenant
    context immediately after the token is validated, so TenantManager
    filters correctly on every DRF request without needing the middleware
    to do it (middleware runs before JWT auth, so it can't do this).
    """
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            set_current_tenant(None)
            return None

        user, token = result
        set_current_tenant(user.tenant if user.tenant_id else None)
        return user, token