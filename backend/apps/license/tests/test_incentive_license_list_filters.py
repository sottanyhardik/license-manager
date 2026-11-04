"""API regression tests for the Incentive Licences list (/api/incentive-licenses/).

Expected IDs are derived from the fixture rows below, not from the code under
test. Sorting cases use an ordering where the requested sequence differs from
the default ``-license_date`` sequence, so a silently ignored ``ordering`` param
cannot pass by accident.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient

from apps.core.models import CompanyModel, PortModel
from apps.license.models import IncentiveLicense
from apps.trade.models import IncentiveTradeLine, LicenseTrade

User = get_user_model()
LIST_URL = "/api/incentive-licenses/"


@pytest.fixture
def api_client(db):
    user = User.objects.create_user(username="incentive_list_tester", password="x-test-only")
    user.is_superuser = True
    user.save()
    token = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def fixture_rows(db):
    e1 = CompanyModel.objects.create(iec="1100000001", name="Alpha Exports")
    e2 = CompanyModel.objects.create(iec="1100000002", name="Beta Traders")
    p1 = PortModel.objects.create(code="INCLP1", name="Port One")
    p2 = PortModel.objects.create(code="INCLP2", name="Port Two")

    def make(number, ltype, when, exporter, port, *, active):
        return IncentiveLicense.objects.create(
            license_number=number,
            license_type=ltype,
            license_date=when,
            exporter=exporter,
            port_code=port,
            license_value=Decimal("1000.00"),
            is_active=active,
        )

    def sale(licence, value):
        # sold_status is derived from SALE lines; it cannot be set directly.
        trade = LicenseTrade.objects.create(
            from_company=e1, to_company=e2, direction="SALE",
            invoice_number=f"INCLIST-SALE-{licence.license_number}",
            invoice_date=date(2025, 12, 1), license_type="INCENTIVE",
        )
        IncentiveTradeLine.objects.create(
            trade=trade, incentive_license=licence, license_value=Decimal(value),
            rate_pct=Decimal("97.25"), amount_inr=Decimal(value),
        )

    rows = {
        "A": make("LIC-A", "RODTEP", date(2025, 1, 10), e1, p1, active=True),
        "B": make("LIC-B", "ROSTL", date(2025, 3, 5), e2, p1, active=False),
        "C": make("LIC-C", "MEIS", date(2025, 6, 20), e1, p2, active=True),
        "D": make("LIC-D", "RODTEP", date(2025, 9, 1), e2, p2, active=True),
    }
    sale(rows["B"], "1000.00")  # fully sold -> YES
    sale(rows["C"], "400.00")   # partly sold -> PARTIAL
    return rows


def _ids(response):
    assert response.status_code == 200, response.content
    return [row["id"] for row in response.json()["results"]]


def _expect(rows, *keys):
    return [rows[k].id for k in keys]


@pytest.mark.django_db
def test_list_ordering_by_license_date_descending_is_honoured(api_client, fixture_rows):
    # Pk order (creation order) is A,B,C,D, so this cannot pass by accident.
    ids = _ids(api_client.get(LIST_URL, {"ordering": "-license_date", "page_size": 50}))
    assert ids == _expect(fixture_rows, "D", "C", "B", "A")


@pytest.mark.django_db
def test_list_ordering_by_license_date_ascending_is_honoured(api_client, fixture_rows):
    ids = _ids(api_client.get(LIST_URL, {"ordering": "license_date", "page_size": 50}))
    assert ids == _expect(fixture_rows, "A", "B", "C", "D")


@pytest.mark.django_db
def test_list_ordering_by_license_number_descending_is_honoured(api_client, fixture_rows):
    ids = _ids(api_client.get(LIST_URL, {"ordering": "-license_number", "page_size": 50}))
    assert ids == _expect(fixture_rows, "D", "C", "B", "A")


@pytest.mark.django_db
def test_default_ordering_is_newest_license_first(api_client, fixture_rows):
    # Declared as the view's default in views_incentive.py and Meta.ordering on the model.
    ids = _ids(api_client.get(LIST_URL, {"page_size": 50}))
    assert ids == _expect(fixture_rows, "D", "C", "B", "A")


@pytest.mark.django_db
def test_filter_by_exporter(api_client, fixture_rows):
    exporter_id = fixture_rows["A"].exporter_id
    ids = _ids(api_client.get(LIST_URL, {"exporter": exporter_id, "page_size": 50}))
    assert sorted(ids) == sorted(_expect(fixture_rows, "A", "C"))


@pytest.mark.django_db
def test_filter_by_port_code(api_client, fixture_rows):
    port_id = fixture_rows["C"].port_code_id
    ids = _ids(api_client.get(LIST_URL, {"port_code": port_id, "page_size": 50}))
    assert sorted(ids) == sorted(_expect(fixture_rows, "C", "D"))


@pytest.mark.django_db
def test_filter_by_license_type(api_client, fixture_rows):
    ids = _ids(api_client.get(LIST_URL, {"license_type": "RODTEP", "page_size": 50}))
    assert sorted(ids) == sorted(_expect(fixture_rows, "A", "D"))


@pytest.mark.django_db
def test_filter_inactive_only(api_client, fixture_rows):
    ids = _ids(api_client.get(LIST_URL, {"is_active": "false", "page_size": 50}))
    assert ids == _expect(fixture_rows, "B")


@pytest.mark.django_db
def test_filter_active_only(api_client, fixture_rows):
    ids = _ids(api_client.get(LIST_URL, {"is_active": "true", "page_size": 50}))
    assert sorted(ids) == sorted(_expect(fixture_rows, "A", "C", "D"))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status_value, expected_keys",
    [("NO", ("A", "D")), ("YES", ("B",)), ("PARTIAL", ("C",))],
)
def test_filter_by_sold_status(api_client, fixture_rows, status_value, expected_keys):
    ids = _ids(api_client.get(LIST_URL, {"sold_status": status_value, "page_size": 50}))
    assert sorted(ids) == sorted(_expect(fixture_rows, *expected_keys))


@pytest.mark.django_db
def test_sold_status_empty_string_means_all(api_client, fixture_rows):
    ids = _ids(api_client.get(LIST_URL, {"sold_status": "", "page_size": 50}))
    assert sorted(ids) == sorted(_expect(fixture_rows, "A", "B", "C", "D"))


@pytest.mark.django_db
def test_license_date_range_from_and_to(api_client, fixture_rows):
    ids = _ids(
        api_client.get(
            LIST_URL,
            {"license_date_from": "2025-03-01", "license_date_to": "2025-06-30", "page_size": 50},
        )
    )
    assert sorted(ids) == sorted(_expect(fixture_rows, "B", "C"))


@pytest.mark.django_db
def test_license_date_range_uses_django_lookup_params_sent_by_ui(api_client, fixture_rows):
    # AdvancedFilter/MasterList convert *_from/*_to into __gte/__lte before the request.
    ids = _ids(
        api_client.get(
            LIST_URL,
            {"license_date__gte": "2025-03-01", "license_date__lte": "2025-06-30", "page_size": 50},
        )
    )
    assert sorted(ids) == sorted(_expect(fixture_rows, "B", "C"))


@pytest.mark.django_db
def test_license_date_range_from_only(api_client, fixture_rows):
    ids = _ids(api_client.get(LIST_URL, {"license_date_from": "2025-06-20", "page_size": 50}))
    assert sorted(ids) == sorted(_expect(fixture_rows, "C", "D"))


@pytest.mark.django_db
def test_license_date_range_to_only(api_client, fixture_rows):
    ids = _ids(api_client.get(LIST_URL, {"license_date_to": "2025-03-05", "page_size": 50}))
    assert sorted(ids) == sorted(_expect(fixture_rows, "A", "B"))


@pytest.mark.django_db
def test_search_matches_license_number_case_insensitively(api_client, fixture_rows):
    ids = _ids(api_client.get(LIST_URL, {"search": "lic-c", "page_size": 50}))
    assert ids == _expect(fixture_rows, "C")


@pytest.mark.django_db
def test_search_matches_exporter_name(api_client, fixture_rows):
    ids = _ids(api_client.get(LIST_URL, {"search": "beta", "page_size": 50}))
    assert sorted(ids) == sorted(_expect(fixture_rows, "B", "D"))


@pytest.mark.django_db
def test_combined_exporter_license_type_and_sold_status(api_client, fixture_rows):
    exporter_id = fixture_rows["D"].exporter_id
    ids = _ids(
        api_client.get(
            LIST_URL,
            {
                "exporter": exporter_id,
                "license_type": "RODTEP",
                "sold_status": "NO",
                "page_size": 50,
            },
        )
    )
    assert ids == _expect(fixture_rows, "D")


@pytest.mark.django_db
def test_combined_filters_with_search_and_date_range(api_client, fixture_rows):
    ids = _ids(
        api_client.get(
            LIST_URL,
            {
                "search": "lic",
                "license_date_from": "2025-01-01",
                "license_date_to": "2025-06-30",
                "is_active": "true",
                "page_size": 50,
            },
        )
    )
    assert ids == _expect(fixture_rows, "C", "A")
