import uuid
from django.db import models


class Tenant(models.Model):
    """
    A transit operator company (e.g. Supermetro) using the platform.
    Every tenant-scoped model below carries a FK back to this.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name



from .middleware import get_current_tenant


class TenantManager(models.Manager):
    """
    Default manager for tenant-scoped models. Automatically filters to
    the current thread-local tenant when one is set. When no tenant is
    set (e.g. a Celery task, a management command, or a super_admin
    context), returns the unfiltered queryset — callers in those contexts
    are responsible for filtering explicitly if needed.
    """
    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()
        if tenant is not None:
            return qs.filter(tenant=tenant)
        return qs


class TenantScopedModel(models.Model):
    """
    Abstract base for any model that belongs to exactly one tenant.
    Provides the `tenant` FK and swaps in TenantManager as the default
    manager so cross-tenant leaks require deliberate effort, not careful
    remembering.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='%(class)ss')

    objects = TenantManager()
    all_objects = models.Manager()  # explicit escape hatch for admin/superadmin/system use

    class Meta:
        abstract = True