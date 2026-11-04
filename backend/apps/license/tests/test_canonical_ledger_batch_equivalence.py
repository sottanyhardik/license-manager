"""Permanent equivalence gate: batched collection build == per-licence build.

The batched loader (``canonical_ledger_batch.LedgerBatch``) must hand every licence
exactly the rows its per-licence query would have returned. These tests build the
same licences both ways and require the complete dataset to be equal, field by field,
not merely equal in aggregate. A licence-level misallocation therefore fails here
even when grand totals still match.

The live-data golden snapshot (see the batch module docstring) is the wider proof;
these fixtures are the repeatable regression guard that runs in CI.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.license.models import IncentiveLicense, LicenseDetailsModel
from apps.license.services.canonical_ledger_batch import LedgerBatch
from apps.license.services.canonical_ledger_service import CanonicalLedgerService


def _build(refs, batched: bool):
    batch = LedgerBatch.for_licences(refs) if batched else None
    return [CanonicalLedgerService.build_canonical_ledger_dataset(license_id, license_type, batch=batch)
            for license_id, license_type in refs]


@pytest.mark.django_db
def test_batched_datasets_equal_per_licence_datasets_field_by_field(
    test_license, test_company, test_port, test_trade,
):
    # A DFIA licence with no trades: a missing relationship must stay missing, not borrowed.
    empty = LicenseDetailsModel.objects.create(
        license_number="EQ-EMPTY-DFIA", license_date=date(2026, 4, 1),
        license_expiry_date=date(2027, 3, 31), exporter=test_company, port=test_port,
    )
    # An incentive licence that shares the DFIA licence's numeric primary key.
    collision = IncentiveLicense.objects.create(
        id=test_license.id, license_number="EQ-RODTEP-COLLIDE", license_type="RODTEP",
        license_date=date(2026, 4, 1), exporter=test_company, port_code=test_port,
        license_value=Decimal("1000.00"),
    )
    refs = [(test_license.id, "DFIA"), (empty.id, "DFIA"), (collision.id, "RODTEP")]

    per_licence = _build(refs, batched=False)
    batched = _build(refs, batched=True)

    assert per_licence == batched
    # The fixture is not trivially empty: the trade really was loaded and counted once.
    assert per_licence[0]["license_type"] == "DFIA"
    assert per_licence[0]["transactions"], "fixture must exercise the trade path"
    assert per_licence[1]["transactions"] == []
    assert per_licence[2]["license_type"] == "RODTEP"


@pytest.mark.django_db
def test_shared_numeric_id_resolves_to_the_requested_licence_type(
    test_license, test_company, test_port,
):
    collision = IncentiveLicense.objects.create(
        id=test_license.id, license_number="EQ-RODTEP-ONLY", license_type="RODTEP",
        license_date=date(2026, 4, 1), exporter=test_company, port_code=test_port,
        license_value=Decimal("500.00"),
    )
    batch = LedgerBatch.for_licences([(test_license.id, "DFIA"), (collision.id, "RODTEP")])
    assert batch.license_object(test_license.id, "DFIA").pk == test_license.pk
    assert batch.license_object(collision.id, "RODTEP").pk == collision.pk
    # A DFIA lookup must never return the incentive row with the same key.
    assert type(batch.license_object(test_license.id, "DFIA")).__name__ == "LicenseDetailsModel"


@pytest.mark.django_db
def test_unknown_keys_return_none_so_callers_fall_back_to_the_original_query(test_license):
    batch = LedgerBatch.for_licences([(test_license.id, "DFIA")])
    assert batch.license_object(999999999, "DFIA") is None
    assert batch.license_object(test_license.id, "NOT_A_TYPE") is None
    assert batch.opening_balance(test_license.id, "RODTEP") is None  # incentive: getattr default
    # Only licences the batch was built for are covered; anything else must fall back.
    assert batch.covers(test_license.id, "DFIA")
    assert not batch.covers(999999999, "DFIA")
    assert not batch.covers(test_license.id, "RODTEP")
