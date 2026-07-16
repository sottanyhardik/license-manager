from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.license.views.ledger_upload import LedgerUploadView


@pytest.mark.parametrize(
    ("filename", "expected_license_numbers"),
    [
        ("L1.csv", ["0311051667", "5211018767"]),
        ("L2.csv", ["0310834974", "0310835522"]),
        ("l3.csv", ["0311054528", "0311007151"]),
    ],
)
def test_ledger_upload_parser_accepts_icegate_csv_exports(filename, expected_license_numbers):
    path = Path(__file__).resolve().parents[2] / "ledgers" / filename
    uploaded_file = SimpleUploadedFile(filename, path.read_bytes(), content_type="text/csv")

    parsed = LedgerUploadView()._parse_file(uploaded_file)

    assert [item["lic_no"] for item in parsed] == expected_license_numbers
    assert all(item["row"] for item in parsed)


@pytest.mark.django_db
def test_ledger_upload_endpoint_accepts_sample_icegate_csv_exports(authenticated_client):
    ledger_dir = Path(__file__).resolve().parents[2] / "ledgers"
    expected_license_numbers = [
        "0311051667",
        "5211018767",
        "0310834974",
        "0310835522",
        "0311054528",
        "0311007151",
    ]

    files = [
        (ledger_dir / filename).open("rb")
        for filename in ("L1.csv", "L2.csv", "l3.csv")
    ]
    try:
        response = authenticated_client.post(
            reverse("license:upload-ledger"),
            {"ledger": files},
            format="multipart",
        )
    finally:
        for file_obj in files:
            file_obj.close()

    assert response.status_code == status.HTTP_200_OK
    assert response.data["licenses"] == expected_license_numbers
    assert response.data["stats"] == {
        "files_processed": 3,
        "files_failed": 0,
        "total_licenses": len(expected_license_numbers),
    }
    for result in response.data["results"]:
        assert result["success"] is True
        assert result["failed"] == []


@pytest.mark.django_db
def test_ledger_upload_session_auth_requires_csrf_token(test_user):
    client = APIClient(enforce_csrf_checks=True)
    assert client.login(username="testuser", password="testpass123!")

    response = client.post(reverse("license:upload-ledger"), {}, format="multipart")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "CSRF" in str(response.data["detail"])


@pytest.mark.django_db
def test_ledger_upload_bearer_auth_does_not_require_csrf_token(test_user):
    token = RefreshToken.for_user(test_user).access_token
    client = APIClient(enforce_csrf_checks=True)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = client.post(reverse("license:upload-ledger"), {}, format="multipart")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {
        "error": "No files uploaded. Please upload at least one CSV file."
    }
