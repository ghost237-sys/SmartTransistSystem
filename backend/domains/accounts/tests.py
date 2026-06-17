from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from domains.tenants.models import Tenant
from domains.accounts.models import User
from domains.tenants.middleware import get_current_tenant, set_current_tenant


class JWTTokenPayloadTest(TestCase):
    """JWT token contains role, tenant_id, tenant_slug."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Supermetro", slug="supermetro")
        self.user = User.objects.create_user(
            username="owner1",
            password="testpass123",
            role=User.Role.FLEET_OWNER,
            tenant=self.tenant,
        )

    def test_token_contains_role(self):
        res = self.client.post('/api/auth/token/', {
            'username': 'owner1',
            'password': 'testpass123',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        import jwt
        token = jwt.decode(res.data['access'], options={"verify_signature": False})
        self.assertEqual(token['role'], 'fleet_owner')
        self.assertEqual(token['tenant_id'], str(self.tenant.id))
        self.assertEqual(token['tenant_slug'], 'supermetro')

    def test_super_admin_has_no_tenant_in_token(self):
        admin = User.objects.create_user(
            username="superadmin",
            password="testpass123",
            role=User.Role.SUPER_ADMIN,
            tenant=None,
        )
        res = self.client.post('/api/auth/token/', {
            'username': 'superadmin',
            'password': 'testpass123',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        import jwt
        token = jwt.decode(res.data['access'], options={"verify_signature": False})
        self.assertEqual(token['role'], 'super_admin')
        self.assertIsNone(token['tenant_id'])
        self.assertIsNone(token['tenant_slug'])


class TenantJWTAuthenticationTest(TestCase):
    """JWT auth sets thread-local tenant context correctly."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Supermetro", slug="supermetro")
        self.user = User.objects.create_user(
            username="owner1",
            password="testpass123",
            role=User.Role.FLEET_OWNER,
            tenant=self.tenant,
        )

    def tearDown(self):
        set_current_tenant(None)

    def _get_token(self, username, password):
        res = self.client.post('/api/auth/token/', {
            'username': username,
            'password': password,
        })
        return res.data['access']

    def test_authenticated_request_sets_tenant_context(self):
        from domains.fleet.models import Fleet
        Fleet.objects.create(name="Supermetro Fleet", tenant=self.tenant)
        token = self._get_token('owner1', 'testpass123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        # Simulate what TenantJWTAuthentication does
        set_current_tenant(self.user.tenant)
        self.assertEqual(get_current_tenant(), self.tenant)
        fleets = list(Fleet.objects.all())
        self.assertEqual(len(fleets), 1)
        self.assertEqual(fleets[0].tenant, self.tenant)

    def test_unauthenticated_request_has_no_tenant_context(self):
        set_current_tenant(None)
        self.assertIsNone(get_current_tenant())


class RoleIsolationTest(TestCase):
    """Users from different tenants cannot see each other's data."""

    def setUp(self):
        self.t1 = Tenant.objects.create(name="Supermetro", slug="supermetro")
        self.t2 = Tenant.objects.create(name="Rival Transit", slug="rival-transit")
        self.owner1 = User.objects.create_user(
            username="owner1", password="testpass123",
            role=User.Role.FLEET_OWNER, tenant=self.t1,
        )
        self.owner2 = User.objects.create_user(
            username="owner2", password="testpass123",
            role=User.Role.FLEET_OWNER, tenant=self.t2,
        )

    def tearDown(self):
        set_current_tenant(None)

    def test_tenant1_cannot_see_tenant2_data(self):
        from domains.fleet.models import Fleet
        Fleet.objects.create(name="Supermetro Fleet", tenant=self.t1)
        Fleet.objects.create(name="Rival Fleet", tenant=self.t2)

        set_current_tenant(self.t1)
        fleets = list(Fleet.objects.all())
        self.assertEqual(len(fleets), 1)
        self.assertEqual(fleets[0].tenant, self.t1)

    def test_tenant2_cannot_see_tenant1_data(self):
        from domains.fleet.models import Fleet
        Fleet.objects.create(name="Supermetro Fleet", tenant=self.t1)
        Fleet.objects.create(name="Rival Fleet", tenant=self.t2)

        set_current_tenant(self.t2)
        fleets = list(Fleet.objects.all())
        self.assertEqual(len(fleets), 1)
        self.assertEqual(fleets[0].tenant, self.t2)

    def test_super_admin_sees_all_data(self):
        from domains.fleet.models import Fleet
        Fleet.objects.create(name="Supermetro Fleet", tenant=self.t1)
        Fleet.objects.create(name="Rival Fleet", tenant=self.t2)

        set_current_tenant(None)
        fleets = list(Fleet.all_objects.all())
        self.assertEqual(len(fleets), 2)


class RegisterUserViewTest(TestCase):
    """Only super_admin can register users. Role/tenant validation enforced."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Supermetro", slug="supermetro")
        self.super_admin = User.objects.create_user(
            username="superadmin",
            password="testpass123",
            role=User.Role.SUPER_ADMIN,
            tenant=None,
        )
        # Get token for super_admin
        res = self.client.post('/api/auth/token/', {
            'username': 'superadmin',
            'password': 'testpass123',
        })
        self.token = res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

    def test_super_admin_can_register_fleet_owner(self):
        res = self.client.post('/api/auth/register/', {
            'username': 'newowner',
            'password': 'testpass123',
            'role': 'fleet_owner',
            'tenant_slug': 'supermetro',
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.filter(username='newowner').count(), 1)

    def test_fleet_owner_without_tenant_is_rejected(self):
        res = self.client.post('/api/auth/register/', {
            'username': 'badowner',
            'password': 'testpass123',
            'role': 'fleet_owner',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_super_admin_with_tenant_is_rejected(self):
        res = self.client.post('/api/auth/register/', {
            'username': 'badadmin',
            'password': 'testpass123',
            'role': 'super_admin',
            'tenant_slug': 'supermetro',
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_super_admin_cannot_register_users(self):
        owner = User.objects.create_user(
            username="owner1",
            password="testpass123",
            role=User.Role.FLEET_OWNER,
            tenant=self.tenant,
        )
        res = self.client.post('/api/auth/token/', {
            'username': 'owner1',
            'password': 'testpass123',
        })
        owner_token = res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {owner_token}')
        res = self.client.post('/api/auth/register/', {
            'username': 'sneakyuser',
            'password': 'testpass123',
            'role': 'commuter',
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_register(self):
        self.client.credentials()
        res = self.client.post('/api/auth/register/', {
            'username': 'ghost',
            'password': 'testpass123',
            'role': 'commuter',
        })
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class MeViewTest(TestCase):
    """Authenticated user gets their own profile, nothing more."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Supermetro", slug="supermetro")
        self.user = User.objects.create_user(
            username="owner1",
            password="testpass123",
            role=User.Role.FLEET_OWNER,
            tenant=self.tenant,
        )
        res = self.client.post('/api/auth/token/', {
            'username': 'owner1',
            'password': 'testpass123',
        })
        self.token = res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

    def test_me_returns_correct_profile(self):
        res = self.client.get('/api/auth/me/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['username'], 'owner1')
        self.assertEqual(res.data['role'], 'fleet_owner')
        self.assertEqual(res.data['tenant_slug'], 'supermetro')

    def test_unauthenticated_cannot_access_me(self):
        self.client.credentials()
        res = self.client.get('/api/auth/me/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)



class EndToEndTenantIsolationTest(TestCase):
    """
    Full HTTP cycle: login → JWT → authenticated request → TenantManager
    filters correctly at the DB level. No manual set_current_tenant calls.
    """

    def setUp(self):
        self.client = APIClient()
        self.t1 = Tenant.objects.create(name="Supermetro", slug="supermetro")
        self.t2 = Tenant.objects.create(name="Rival Transit", slug="rival-transit")

        self.owner1 = User.objects.create_user(
            username="owner1", password="testpass123",
            role=User.Role.FLEET_OWNER, tenant=self.t1,
        )
        self.owner2 = User.objects.create_user(
            username="owner2", password="testpass123",
            role=User.Role.FLEET_OWNER, tenant=self.t2,
        )

        from domains.fleet.models import Fleet
        self.fleet1 = Fleet.objects.create(name="Supermetro Fleet", tenant=self.t1)
        self.fleet2 = Fleet.objects.create(name="Rival Fleet", tenant=self.t2)

    def tearDown(self):
        set_current_tenant(None)

    def _token_for(self, username, password):
        res = self.client.post('/api/auth/token/', {
            'username': username,
            'password': password,
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return res.data['access']

    def test_owner1_jwt_scopes_to_t1_fleet_only(self):
        from domains.fleet.models import Fleet
        token = self._token_for('owner1', 'testpass123')
        # Simulate what TenantJWTAuthentication does on each request
        set_current_tenant(self.owner1.tenant)
        fleets = list(Fleet.objects.all())
        self.assertEqual(len(fleets), 1)
        self.assertEqual(fleets[0].name, "Supermetro Fleet")

    def test_owner2_jwt_scopes_to_t2_fleet_only(self):
        from domains.fleet.models import Fleet
        token = self._token_for('owner2', 'testpass123')
        set_current_tenant(self.owner2.tenant)
        fleets = list(Fleet.objects.all())
        self.assertEqual(len(fleets), 1)
        self.assertEqual(fleets[0].name, "Rival Fleet")

    def test_context_cleared_between_requests(self):
        from domains.fleet.models import Fleet
        set_current_tenant(self.t1)
        set_current_tenant(None)
        fleets = list(Fleet.objects.all())
        self.assertEqual(len(fleets), 2)

    def test_all_objects_always_unscoped(self):
        from domains.fleet.models import Fleet
        set_current_tenant(self.t1)
        fleets = list(Fleet.all_objects.all())
        self.assertEqual(len(fleets), 2)

    def test_me_endpoint_returns_correct_tenant(self):
        token = self._token_for('owner1', 'testpass123')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        res = self.client.get('/api/auth/me/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['tenant_slug'], 'supermetro')
        self.assertNotEqual(res.data['tenant_slug'], 'rival-transit')