"""
Concurrency regression: concurrent allocations on DIFFERENT import rows of one
licence must not together exceed the licence's available CIF.

The existing parent-allotment lock serialises requests against the same
allotment only.  Two allotments drawing on two rows of one licence each read the
shared licence-wide balance; without a licence-level lock both could pass.

Uses real connections (transaction=True) so the two requests race in the
database, not in mocks.
"""
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import close_old_connections
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.models import CompanyModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel

User = get_user_model()


def _client(username):
    user = User.objects.create_user(username=username, password="test-pass-123")
    user.groups.add(Group.objects.get_or_create(name="ALLOTMENT_MANAGER")[0])
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.mark.django_db(transaction=True)
def test_concurrent_allocations_on_two_rows_of_one_licence_cannot_both_pass():
    company = CompanyModel.objects.create(iec="CONCLIC001", name="Concurrent Licence Co")
    licence = LicenseDetailsModel.objects.create(
        license_number="CONC-LICENCE-1",
        license_date=date.today() - timedelta(days=30),
        license_expiry_date=date.today() + timedelta(days=90),
        exporter=company,
    )
    rows = [
        LicenseImportItemsModel.objects.create(
            license=licence, serial_number=index, description=f"Concurrent row {index}",
            quantity=Decimal("100.000"), available_quantity=Decimal("100.000"),
            available_value=Decimal("100.00"), condition_type="",
        )
        for index in (1, 2)
    ]
    # Licence-wide CIF available: 100.  Each request asks for 60, so exactly one may succeed.
    LicenseExportItemModel.objects.update_or_create(license=licence, defaults={"cif_fc": Decimal("100.00")})
    allotments = [
        AllotmentModel.objects.create(company=company, required_quantity=Decimal("1000.00"))
        for _ in (1, 2)
    ]
    client = _client("concurrent-licence-cif")
    start = Barrier(2)

    from apps.allotment import views_actions
    real_available = views_actions.effective_source_row_cif_available

    def slow_read(**kwargs):
        # Widen the read-to-commit window so both requests observe the same
        # balance before either writes.  Only a serialising lock makes the second
        # request wait for the first request's debit.
        value = real_available(**kwargs)
        time.sleep(0.5)
        return value

    def submit(index):
        close_old_connections()
        try:
            start.wait(timeout=10)
            response = client.post(
                f"/api/allotment-actions/{allotments[index].id}/allocate-items/",
                {"allocations": [{"item_id": rows[index].pk, "qty": "1", "cif_fc": "60.00"}]},
                format="json",
            )
            return response.status_code, response.data
        finally:
            close_old_connections()

    with patch.object(views_actions, "effective_source_row_cif_available", slow_read), \
            ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, (0, 1)))

    # Exactly one request is accepted and the other is rejected by the CIF
    # ceiling itself (a 400 validation error).  A 500 is not an acceptable
    # outcome: it would mean the second request failed for an unrelated reason
    # (such as a deadlock) rather than being checked against the balance.
    statuses = sorted(status for status, _ in results)
    assert statuses == [201, 400], results
    rejected = next(data for status, data in results if status == 400)
    assert rejected["errors"][0]["code"] == "ALLOTMENT_CIF_EXCEEDS_ACTUAL", rejected
    debited = sum(
        (item.cif_fc for item in AllotmentItems.objects.filter(item__license=licence)),
        Decimal("0"),
    )
    assert debited <= Decimal("100.00"), f"licence over-utilised: {debited}"
