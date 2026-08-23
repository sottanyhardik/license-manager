import pytest
from django.conf import settings
from rest_framework.test import APIRequestFactory
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.authentication import JWTAuthenticationFromQueryParam


def test_jwt_authentication_precedes_session_authentication_for_api_mutations():
    """A bearer token must win over any browser session cookie/CSRF state."""
    classes = settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]

    assert classes.index("apps.core.authentication.JWTAuthenticationFromQueryParam") < classes.index(
        "rest_framework.authentication.SessionAuthentication"
    )


@pytest.mark.django_db
def test_bearer_token_mutation_succeeds_even_when_a_browser_session_has_no_csrf_token(test_user):
    """JWT must authenticate before SessionAuthentication can enforce CSRF."""
    class ProtectedMutation(APIView):
        permission_classes = [IsAuthenticated]

        def post(self, request):
            return Response({"user_id": request.user.id})

    token = RefreshToken.for_user(test_user).access_token
    request = APIRequestFactory().post(
        "/api/test-protected-mutation/",
        {},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    # Simulate the browser's simultaneously-present Django session cookie. If
    # SessionAuthentication runs first, it rejects this request for CSRF.
    request.user = test_user

    response = ProtectedMutation.as_view()(request)

    assert response.status_code == 200
    assert response.data == {"user_id": test_user.id}


@pytest.mark.django_db
def test_query_param_jwt_is_ignored_on_normal_api_paths(test_user):
    token = RefreshToken.for_user(test_user).access_token
    request = APIRequestFactory().get('/api/licenses/', {'access_token': str(token)})

    assert JWTAuthenticationFromQueryParam().authenticate(request) is None


@pytest.mark.django_db
def test_query_param_jwt_is_allowed_for_download_paths(test_user):
    token = RefreshToken.for_user(test_user).access_token
    request = APIRequestFactory().get(
        '/api/license-actions/1/download-ledger/',
        {'access_token': str(token)},
    )

    user, validated_token = JWTAuthenticationFromQueryParam().authenticate(request)

    assert user == test_user
    assert validated_token is not None


@pytest.mark.django_db
def test_query_param_jwt_is_ignored_for_non_get_download_paths(test_user):
    token = RefreshToken.for_user(test_user).access_token
    request = APIRequestFactory().post(
        '/api/license-actions/1/download-ledger/',
        {'access_token': str(token)},
    )

    assert JWTAuthenticationFromQueryParam().authenticate(request) is None
