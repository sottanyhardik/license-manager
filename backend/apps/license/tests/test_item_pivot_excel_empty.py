"""Item pivot Excel export with filters matching zero groups returns a valid xlsx."""
import io

import openpyxl
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

URL = "/api/reports/item-pivot/"


@pytest.fixture
def client(db):
    user = get_user_model().objects.create_user(username="pivot-empty", email="pe@example.com", password="RoleP@ssw0rd123")
    user.groups.add(Group.objects.get_or_create(name="REPORT_VIEWER")[0])
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return c


def test_empty_export_is_valid_xlsx(client):
    r = client.get(URL, {"format": "excel", "sion_norm": "NO-SUCH-NORM", "license_status": "all", "min_balance": 0})
    assert r.status_code == 200, getattr(r, "content", b"")[:300]
    assert r["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert r["Content-Disposition"] == 'attachment; filename="item_pivot_report.xlsx"'
    wb = openpyxl.load_workbook(io.BytesIO(b"".join(r.streaming_content)))
    assert wb.sheetnames == ["TOTAL_Summary"]
