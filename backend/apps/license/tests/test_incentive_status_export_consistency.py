"""The Excel export must show the same sold status as the list API and the cache."""
from datetime import date
from decimal import Decimal
from io import BytesIO

import openpyxl
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import CompanyModel, PortModel
from apps.license.models import IncentiveLicense
from apps.trade.models import IncentiveTradeLine, LicenseTrade

User = get_user_model()
LIST_URL = "/api/incentive-licenses/"


@pytest.fixture
def api_client(db):
    user = User.objects.create_user(username="incentive_export_tester", password="x-test-only")
    user.is_superuser = True
    user.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.mark.django_db
def test_xlsx_export_status_matches_stored_cache_and_list(api_client):
    exporter = CompanyModel.objects.create(iec="3000000001", name="Export Co")
    buyer = CompanyModel.objects.create(iec="3000000002", name="Buyer Co")
    port = PortModel.objects.create(code="EXPT01", name="Export Port")

    sold = IncentiveLicense.objects.create(
        license_type="RODTEP", license_number="EXP-SOLD-001", license_date=date(2025, 12, 19),
        exporter=exporter, port_code=port, license_value=Decimal("768600.00"), is_active=True,
    )
    available = IncentiveLicense.objects.create(
        license_type="RODTEP", license_number="EXP-AVAIL-001", license_date=date(2025, 12, 19),
        exporter=exporter, port_code=port, license_value=Decimal("5000.00"), is_active=True,
    )
    trade = LicenseTrade.objects.create(
        from_company=exporter, to_company=buyer, direction="SALE",
        invoice_number="EXP-SALE-001", invoice_date=date(2025, 12, 23), license_type="INCENTIVE",
    )
    IncentiveTradeLine.objects.create(
        trade=trade, incentive_license=sold, license_value=Decimal("768600.00"),
        rate_pct=Decimal("99.000"), amount_inr=Decimal("760914.00"),
    )

    listed = {r["license_number"]: r["sold_status"]
              for r in api_client.get(LIST_URL, {"page_size": 200}).json()["results"]}
    assert listed["EXP-SOLD-001"] == "YES"
    assert listed["EXP-AVAIL-001"] == "NO"

    response = api_client.get(LIST_URL + "export/", {"_export": "xlsx"})
    assert response.status_code == 200
    sheet = openpyxl.load_workbook(BytesIO(response.content)).active
    rows = list(sheet.iter_rows(values_only=True))
    header = [str(h).strip().lower() if h is not None else "" for h in rows[0]]
    status_col = next(i for i, h in enumerate(header) if "sold" in h and "status" in h)
    number_col = next(i for i, h in enumerate(header) if "licen" in h and "number" in h)

    exported = {str(r[number_col]): str(r[status_col]).strip().upper()
                for r in rows[1:] if r[number_col] is not None}
    assert exported["EXP-SOLD-001"] == "YES"
    assert exported["EXP-AVAIL-001"] == "NO"
