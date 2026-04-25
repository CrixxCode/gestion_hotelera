from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model
from accounts.models import Role, Resource
from apps.hotel_settings.models import HotelSettings

User = get_user_model()

class FilterOrderingTests(APITestCase):
    def setUp(self):
        # Crear rol/recursos y usuarios
        self.r_read = Resource.objects.create(key="users.read", name="Leer usuarios")
        role = Role.objects.create(name="Manager", slug="manager")
        role.resources.add(self.r_read)

        self.u1 = User.objects.create_user(username="ana", email="ana@example.com", password="pass12345")
        self.u2 = User.objects.create_user(username="beto", email="beto@example.com", password="pass12345")
        self.u1.roles.add(role); self.u2.roles.add(role)

        # Autenticar vía sesión (bypaséando login view para test)
        self.client = APIClient()
        self.client.force_login(self.u1)

    def test_search_and_order(self):
        url = "/api/users/?search=et&ordering=-username"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        payload = r.data["results"] if isinstance(r.data, dict) and "results" in r.data else r.data
        usernames = [u["username"] for u in payload]
        self.assertTrue("beto" in usernames or "ana" in usernames)

    def test_filter_by_role_slug(self):
        url = "/api/users/?roles__slug=manager"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        if isinstance(r.data, dict) and "count" in r.data:
            self.assertGreaterEqual(r.data["count"], 2)
        else:
            self.assertGreaterEqual(len(r.data), 2)


class RoleTenantIsolationTests(APITestCase):
    def setUp(self):
        self.hotel_a = HotelSettings.objects.create(hotel_name="Hotel A")
        self.hotel_b = HotelSettings.objects.create(hotel_name="Hotel B")

        self.roles_write_resource = Resource.objects.create(
            key="roles.write",
            name="Roles Write",
            link_backend="/api/roles/",
        )
        self.roles_read_resource = Resource.objects.create(
            key="roles.read",
            name="Roles Read",
            link_backend="/api/roles/",
        )
        manager_role = Role.objects.create(name="Role Manager", slug="role-manager")
        manager_role.resources.add(self.roles_write_resource, self.roles_read_resource)
        self.manager_slug_role = Role.objects.create(name="Manager", slug="manager")
        self.manager_slug_role.resources.add(self.roles_write_resource, self.roles_read_resource)

        self.manager = User.objects.create_user(
            username="manager_a",
            email="manager_a@example.com",
            password="pass12345",
            hotel_settings=self.hotel_a,
        )
        self.manager.roles.add(manager_role)

        self.manager_superuser = User.objects.create_superuser(
            username="manager_superuser",
            email="manager_superuser@example.com",
            password="pass12345",
        )
        self.manager_superuser.hotel_settings = self.hotel_a
        self.manager_superuser.save(update_fields=["hotel_settings"])
        self.manager_superuser.roles.add(self.manager_slug_role)

        self.user_a = User.objects.create_user(
            username="user_a",
            email="user_a@example.com",
            password="pass12345",
            hotel_settings=self.hotel_a,
        )
        self.user_b = User.objects.create_user(
            username="user_b",
            email="user_b@example.com",
            password="pass12345",
            hotel_settings=self.hotel_b,
        )

        self.target_role = Role.objects.create(name="Front Desk", slug="front-desk")

        self.client = APIClient()
        self.client.force_login(self.manager)

    def test_assign_users_rejects_cross_tenant_ids(self):
        url = f"/api/roles/{self.target_role.id}/assign-users/"
        response = self.client.post(
            url,
            {"user_ids": [str(self.user_a.id), str(self.user_b.id)]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("rejected_user_ids", response.data)
        self.assertIn(str(self.user_b.id), response.data["rejected_user_ids"])

    def test_users_catalog_returns_only_authenticated_user_tenant(self):
        response = self.client.get("/api/roles/users-catalog/")
        self.assertEqual(response.status_code, 200)

        returned_ids = {entry["id"] for entry in response.data}
        self.assertIn(str(self.manager.id), returned_ids)
        self.assertIn(str(self.user_a.id), returned_ids)
        self.assertNotIn(str(self.user_b.id), returned_ids)

    def test_users_catalog_limits_superuser_when_user_has_manager_role(self):
        self.client.force_login(self.manager_superuser)
        response = self.client.get("/api/roles/users-catalog/")
        self.assertEqual(response.status_code, 200)

        returned_ids = {entry["id"] for entry in response.data}
        self.assertIn(str(self.manager_superuser.id), returned_ids)
        self.assertIn(str(self.manager.id), returned_ids)
        self.assertIn(str(self.user_a.id), returned_ids)
        self.assertNotIn(str(self.user_b.id), returned_ids)


class ScopeAliasPermissionTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

    def _login_user_with_resource_keys(self, keys: list[str]):
        resources = []
        for key in keys:
            resources.append(
                Resource.objects.create(
                    key=key,
                    name=key,
                    link_backend="/api/hotel-settings/",
                )
            )

        role = Role.objects.create(name="Settings Role", slug="settings-role")
        role.resources.add(*resources)

        user = User.objects.create_user(
            username="settings_user",
            email="settings_user@example.com",
            password="pass12345",
        )
        user.roles.add(role)
        self.client.force_login(user)

    def test_create_hotel_settings_accepts_hyphenated_scope_alias(self):
        self._login_user_with_resource_keys(["hotel-settings.write"])

        response = self.client.post(
            "/api/hotel-settings/",
            {"hotel_name": "Hotel Alias"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data.get("hotel_name"), "Hotel Alias")

    def test_create_hotel_settings_accepts_resource_wildcard_scope(self):
        self._login_user_with_resource_keys(["hotel-settings.*"])

        response = self.client.post(
            "/api/hotel-settings/",
            {"hotel_name": "Hotel Wildcard"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data.get("hotel_name"), "Hotel Wildcard")

    def test_create_hotel_settings_without_write_scope_is_forbidden(self):
        self._login_user_with_resource_keys(["hotel-settings.read"])

        response = self.client.post(
            "/api/hotel-settings/",
            {"hotel_name": "Hotel Forbidden"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
