import threading

_thread_locals = threading.local()


def get_current_tenant():
    return getattr(_thread_locals, 'tenant', None)


def set_current_tenant(tenant):
    _thread_locals.tenant = tenant


class TenantMiddleware:
    """
    Reads the authenticated user's tenant and stashes it in thread-local
    storage for the duration of the request, so TenantManager can filter
    querysets without needing the request object passed around explicitly.

    Must run AFTER AuthenticationMiddleware (so request.user is populated)
    and AFTER JWT auth runs on the view, which means for DRF views, the
    tenant won't be set yet at the middleware stage — we set it again in
    a DRF authentication/permission hook in Phase 2's auth step.
    For now, this covers session-authenticated requests (e.g. Django admin).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and getattr(user, 'tenant_id', None):
            set_current_tenant(user.tenant)
        else:
            set_current_tenant(None)

        response = self.get_response(request)
        set_current_tenant(None)  # always clear after the request, avoid leaking across requests
        return response