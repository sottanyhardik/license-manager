"""Slice 1 (V1 decision register, Q-002 = A): USER_MANAGER cannot act on superusers.

Each denied case asserts the backend result (status and database state), not just
the absence of a frontend control. Superusers are not reachable through the
user-management API for USER_MANAGER callers; for those callers a superuser id
must be indistinguishable from a non-existent id.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

PASSWORD = "P@ssw0rd123"
NEW_PASSWORD = "NewP@ssw0rd456"
MISSING_ID = 999999999


class SuperuserProtectionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.superuser = User.objects.create_superuser(
            username="root-admin", email="root@example.com", password=PASSWORD,
        )
        self.other_superuser = User.objects.create_superuser(
            username="second-admin", email="second@example.com", password=PASSWORD,
        )
        self.user_manager = User.objects.create_user(
            username="manager", email="manager@example.com", password=PASSWORD,
        )
        self.user_manager.groups.add(Group.objects.get_or_create(name="USER_MANAGER")[0])
        self.ordinary = User.objects.create_user(
            username="ordinary", email="ordinary@example.com", password=PASSWORD,
        )
        self.role_less = User.objects.create_user(
            username="roleless", email="roleless@example.com", password=PASSWORD,
        )

    def tearDown(self):
        cache.clear()

    # ---- helpers -------------------------------------------------------
    def _client_for(self, user):
        if user is None:
            return APIClient()
        client = APIClient()
        response = client.post(
            "/api/auth/login/",
            {"username": user.username, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return client

    def _detail(self, pk):
        return f"/api/auth/users/{pk}/"

    def _reset(self, pk):
        return f"/api/auth/users/{pk}/reset-password/"

    # ---- USER_MANAGER denied on superusers -----------------------------
    def test_user_manager_list_omits_superusers(self):
        response = self._client_for(self.user_manager).get("/api/auth/users/?page_size=500")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in _rows(response.data)}
        self.assertNotIn(self.superuser.id, ids)
        self.assertNotIn(self.other_superuser.id, ids)
        self.assertIn(self.ordinary.id, ids)

    def test_user_manager_search_cannot_find_superuser(self):
        response = self._client_for(self.user_manager).get("/api/auth/users/?search=root-admin")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(_rows(response.data), [])

    def test_user_manager_cannot_retrieve_superuser(self):
        response = self._client_for(self.user_manager).get(self._detail(self.superuser.id))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertNotIn("root-admin", str(response.data))

    def test_user_manager_cannot_reset_superuser_password(self):
        response = self._client_for(self.user_manager).post(
            self._reset(self.superuser.id), {"password": NEW_PASSWORD}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.check_password(PASSWORD))
        self.assertFalse(self.superuser.check_password(NEW_PASSWORD))

    def test_user_manager_cannot_delete_superuser(self):
        response = self._client_for(self.user_manager).delete(self._detail(self.superuser.id))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(User.objects.filter(pk=self.superuser.id).exists())

    def test_user_manager_cannot_deactivate_superuser(self):
        response = self._client_for(self.user_manager).patch(
            self._detail(self.superuser.id), {"is_active": False}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)

    def test_user_manager_cannot_change_superuser_roles(self):
        response = self._client_for(self.user_manager).patch(
            self._detail(self.superuser.id), {"roles": []}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(self.superuser.is_superuser)

    def test_user_manager_cannot_grant_superuser_flag_to_ordinary_user(self):
        response = self._client_for(self.user_manager).patch(
            self._detail(self.ordinary.id), {"is_superuser": True}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ordinary.refresh_from_db()
        self.assertFalse(self.ordinary.is_superuser)

    def test_user_manager_cannot_create_superuser(self):
        response = self._client_for(self.user_manager).post(
            "/api/auth/users/",
            {
                "username": "made-by-manager",
                "email": "made@example.com",
                "password": NEW_PASSWORD,
                "is_superuser": True,
                "is_staff": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(username="made-by-manager")
        self.assertFalse(created.is_superuser)
        self.assertFalse(created.is_staff)

    def test_profile_endpoint_cannot_set_superuser_flag(self):
        response = self._client_for(self.user_manager).patch(
            "/api/auth/me/", {"is_superuser": True}, format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user_manager.refresh_from_db()
        self.assertFalse(self.user_manager.is_superuser)

    def test_superuser_id_and_missing_id_return_identical_errors(self):
        client = self._client_for(self.user_manager)
        for method, suffix in (("get", ""), ("delete", "")):
            hidden = getattr(client, method)(self._detail(self.superuser.id))
            missing = getattr(client, method)(self._detail(MISSING_ID))
            self.assertEqual(hidden.status_code, missing.status_code, method)
            self.assertEqual(hidden.data, missing.data, method)
        hidden = client.post(self._reset(self.superuser.id), {"password": NEW_PASSWORD}, format="json")
        missing = client.post(self._reset(MISSING_ID), {"password": NEW_PASSWORD}, format="json")
        self.assertEqual(hidden.status_code, missing.status_code)
        self.assertEqual(hidden.data, missing.data)

    # ---- ordinary users remain manageable ------------------------------
    def test_user_manager_can_manage_ordinary_user(self):
        client = self._client_for(self.user_manager)

        detail = client.get(self._detail(self.ordinary.id))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        renamed = client.patch(self._detail(self.ordinary.id), {"first_name": "Renamed"}, format="json")
        self.assertEqual(renamed.status_code, status.HTTP_200_OK)
        self.ordinary.refresh_from_db()
        self.assertEqual(self.ordinary.first_name, "Renamed")

        reset = client.post(self._reset(self.ordinary.id), {"password": NEW_PASSWORD}, format="json")
        self.assertEqual(reset.status_code, status.HTTP_200_OK)
        self.ordinary.refresh_from_db()
        self.assertTrue(self.ordinary.check_password(NEW_PASSWORD))

        deleted = client.delete(self._detail(self.ordinary.id))
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=self.ordinary.id).exists())

    # ---- superusers keep their access ----------------------------------
    def test_superuser_retains_full_access_to_superusers(self):
        client = self._client_for(self.superuser)

        listed = client.get("/api/auth/users/?page_size=500")
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in _rows(listed.data)}
        self.assertIn(self.other_superuser.id, ids)

        detail = client.get(self._detail(self.other_superuser.id))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        reset = client.post(self._reset(self.other_superuser.id), {"password": NEW_PASSWORD}, format="json")
        self.assertEqual(reset.status_code, status.HTTP_200_OK)

        deleted = client.delete(self._detail(self.other_superuser.id))
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    # ---- denied callers without a manager role -------------------------
    def test_anonymous_callers_are_denied(self):
        client = self._client_for(None)

        self.assertEqual(client.get(self._detail(self.superuser.id)).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            client.post(self._reset(self.superuser.id), {"password": NEW_PASSWORD}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(client.delete(self._detail(self.superuser.id)).status_code, status.HTTP_401_UNAUTHORIZED)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.check_password(PASSWORD))

    def test_role_less_callers_are_denied(self):
        client = self._client_for(self.role_less)

        self.assertEqual(client.get("/api/auth/users/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(client.get(self._detail(self.superuser.id)).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(client.delete(self._detail(self.superuser.id)).status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(User.objects.filter(pk=self.superuser.id).exists())


def _rows(data):
    """List responses may be paginated; return the result rows either way."""
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data
