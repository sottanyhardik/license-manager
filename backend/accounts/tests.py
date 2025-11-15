# FILE: accounts/tests.py
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


class AccountsAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_data = {"username": "testuser", "email": "u@example.com", "password": "P@ssw0rd123"}
        resp = self.client.post(reverse("accounts:register"), self.user_data)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # obtain token
        token_resp = self.client.post(reverse("accounts:token_obtain_pair"), {"username": "testuser", "password": "P@ssw0rd123"})
        self.assertEqual(token_resp.status_code, status.HTTP_200_OK)
        self.access = token_resp.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    def test_get_profile_me(self):
        resp = self.client.get("/api/accounts/users/me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["username"], "testuser")

    def test_avatar_upload_denied_for_other(self):
        # create another user
        other = User.objects.create_user(username="other", email="other@example.com", password="Other123!")
        # attempt to upload for other user
        url = f"/api/accounts/users/{other.pk}/avatar/"
        with open(__file__, "rb") as f:
            resp = self.client.post(url, {"avatar": f})
        # not allowed
        self.assertIn(resp.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN))
