import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_token(db, django_user_model):
    user = django_user_model.objects.create_user(
        username="testuser",
        password="testpassword123",
        email="test@example.com",
    )
    refresh = RefreshToken.for_user(user)
    return {
        "user": user,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


@pytest.fixture
def authenticated_client(api_client, auth_token):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth_token['access']}")
    return api_client
