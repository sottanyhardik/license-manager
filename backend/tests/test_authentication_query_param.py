import pytest
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.authentication import JWTAuthenticationFromQueryParam


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
