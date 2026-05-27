# FILE: accounts/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


class AccountsAPITestCase(TestCase):
    def setUp(self):
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

    def test_user_management_denied_without_role(self):
        resp = self.client.get("/api/auth/users/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
