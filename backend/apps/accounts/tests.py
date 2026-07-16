# FILE: accounts/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_delete, pre_save
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.management.commands.migrate_auth import Command as MigrateAuthCommand
from apps.accounts.management.commands.migrate_auth import redact_dsn
from apps.accounts.management.commands.repair_user_fk_constraints import quote_identifier_path

User = get_user_model()


class AccountsAPITestCase(TestCase):
    def tearDown(self):
        cache.clear()

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.password = "P@ssw0rd123"
        self.user = User.objects.create_user(
            username="testuser",
            email="u@example.com",
            password=self.password,
        )
        token_resp = self.client.post(
            "/api/auth/login/",
            {"username": self.user.username, "password": self.password},
            format="json",
        )
        self.assertEqual(token_resp.status_code, status.HTTP_200_OK)
        self.access = token_resp.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    def test_get_profile_me(self):
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["username"], "testuser")

    def test_logout_rejects_invalid_refresh_token(self):
        resp = self.client.post(
            "/api/auth/logout/",
            {"refresh": "not-a-valid-refresh-token"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["detail"], "invalid token")

    def test_user_management_denied_without_role(self):
        resp = self.client.get("/api/auth/users/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_management_create_rejects_weak_password(self):
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="AdminP@ssw0rd123",
        )
        client = APIClient()
        token_resp = client.post(
            "/api/auth/login/",
            {"username": admin.username, "password": "AdminP@ssw0rd123"},
            format="json",
        )
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_resp.data['access']}")

        resp = client.post(
            "/api/auth/users/",
            {
                "username": "weakuser",
                "email": "weak@example.com",
                "password": "123",
            },
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", resp.data)
        self.assertFalse(User.objects.filter(username="weakuser").exists())

    def test_user_management_reset_password_rejects_weak_password(self):
        admin = User.objects.create_superuser(
            username="admin2",
            email="admin2@example.com",
            password="AdminP@ssw0rd123",
        )
        target = User.objects.create_user(
            username="managed",
            email="managed@example.com",
            password="ExistingP@ssw0rd123",
        )
        client = APIClient()
        token_resp = client.post(
            "/api/auth/login/",
            {"username": admin.username, "password": "AdminP@ssw0rd123"},
            format="json",
        )
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_resp.data['access']}")

        resp = client.post(
            f"/api/auth/users/{target.pk}/reset-password/",
            {"password": "123"},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", resp.data)
        target.refresh_from_db()
        self.assertTrue(target.check_password("ExistingP@ssw0rd123"))

    def test_account_avatar_cleanup_signals_are_registered(self):
        self.assertTrue(pre_save.has_listeners(User))
        self.assertTrue(post_delete.has_listeners(User))


class FakeSourceCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.index = 0

    def execute(self, query):
        self.query = query

    def fetchmany(self, size):
        rows = self.rows[self.index:self.index + size]
        self.index += len(rows)
        return rows


class AuditRecorder:
    def __init__(self):
        self.records = []

    def record(self, **entry):
        self.records.append(entry)


class MigrateAuthCommandTests(TestCase):
    def test_migrate_users_creates_missing_user_with_username(self):
        cursor = FakeSourceCursor([
            {
                "id": 42,
                "password": "pbkdf2_sha256$fixture",
                "last_login": None,
                "is_superuser": False,
                "username": "sourceuser",
                "first_name": "Source",
                "last_name": "User",
                "email": "source@example.com",
                "is_staff": False,
                "is_active": True,
                "date_joined": timezone.now(),
                "avatar": "",
            }
        ])
        audit = AuditRecorder()

        MigrateAuthCommand()._migrate_users(cursor, audit, dry_run=False, batch_size=500)

        user = User.objects.get(username="sourceuser")
        self.assertEqual(user.email, "source@example.com")
        self.assertEqual(audit.records[-1]["status"], "migrated")
        self.assertEqual(audit.records[-1]["target_pk"], user.pk)

    def test_redact_dsn_masks_url_and_keyword_passwords(self):
        self.assertEqual(
            redact_dsn("postgres://user:secret@example.com:5432/source"),
            "postgres://user:***@example.com:5432/source",
        )
        self.assertEqual(
            redact_dsn("dbname=source user=dbuser password=secret host=localhost"),
            "dbname=source user=dbuser password=*** host=localhost",
        )


class RepairUserFKConstraintsCommandTests(TestCase):
    def test_quote_identifier_path_handles_schema_qualified_table_names(self):
        self.assertEqual(
            quote_identifier_path("public.license_licensedetailsmodel"),
            '"public"."license_licensedetailsmodel"',
        )
