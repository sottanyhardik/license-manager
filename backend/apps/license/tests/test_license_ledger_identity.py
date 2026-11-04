"""Licence identity in the License Ledger: DFIA and incentive ids can collide.

Both tables use independent primary-key sequences, so the same numeric id can
exist in each. A composite 'TYPE:REF' key must always resolve to the licence of
that type, and a bare id keeps its established lookup for compatibility.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.test import SimpleTestCase

from apps.core.models import CompanyModel, PortModel
from apps.license.models import IncentiveLicense, LicenseDetailsModel
from apps.license.views.ledger import LicenseLedgerViewSet

SHARED_ID = 7777


class ParseLicenceRefTests(SimpleTestCase):
    def test_composite_key_pins_the_licence_type(self):
        self.assertEqual(LicenseLedgerViewSet._parse_licence_ref("DFIA:12"), ("12", "DFIA"))
        self.assertEqual(LicenseLedgerViewSet._parse_licence_ref(" rodtep : 5 "), ("5", "RODTEP"))

    def test_bare_reference_keeps_the_established_lookup(self):
        self.assertEqual(LicenseLedgerViewSet._parse_licence_ref("12"), ("12", "AUTO"))
        self.assertEqual(LicenseLedgerViewSet._parse_licence_ref(" 0311051359 "), ("0311051359", "AUTO"))

    def test_malformed_composite_is_treated_as_a_bare_reference(self):
        # An empty side is not a valid composite key; it must not become a lookup of ''.
        self.assertEqual(LicenseLedgerViewSet._parse_licence_ref("DFIA:"), ("DFIA:", "AUTO"))
        self.assertEqual(LicenseLedgerViewSet._parse_licence_ref(":12"), (":12", "AUTO"))
        # A licence number that contains a colon is not a type prefix.
        self.assertEqual(LicenseLedgerViewSet._parse_licence_ref("0310:123"), ("0310:123", "AUTO"))


@pytest.fixture
def shared_id_rows(db):
    """A DFIA licence and an incentive licence that share the same primary key."""
    company = CompanyModel.objects.create(iec="9900000007", name="Identity Exporter")
    port = PortModel.objects.create(code="IDENT1", name="Identity Port")
    dfia = LicenseDetailsModel.objects.create(
        id=SHARED_ID, license_number="DFIA-SHARED-7", license_date=date(2026, 4, 1),
        license_expiry_date=date(2027, 3, 31), exporter=company, port=port,
    )
    incentive = IncentiveLicense.objects.create(
        id=SHARED_ID, license_number="RODTEP-SHARED-7", license_type="RODTEP",
        license_date=date(2026, 4, 1), exporter=company, port_code=port,
        license_value=Decimal("1000.00"),
    )
    return dfia, incentive


@pytest.mark.django_db
def test_composite_dfia_key_never_resolves_to_the_incentive_row(shared_id_rows):
    dfia, _incentive = shared_id_rows
    ref, licence_type = LicenseLedgerViewSet._parse_licence_ref(f"DFIA:{SHARED_ID}")
    found_type, licence = LicenseLedgerViewSet()._authorized_license(None, ref, licence_type)
    assert found_type == "DFIA"
    assert licence.pk == dfia.pk


@pytest.mark.django_db
def test_composite_incentive_key_never_resolves_to_the_dfia_row(shared_id_rows):
    _dfia, incentive = shared_id_rows
    ref, licence_type = LicenseLedgerViewSet._parse_licence_ref(f"RODTEP:{SHARED_ID}")
    found_type, licence = LicenseLedgerViewSet()._authorized_license(None, ref, licence_type)
    assert found_type == "RODTEP"
    assert licence.pk == incentive.pk


@pytest.mark.django_db
def test_bare_shared_id_keeps_the_legacy_dfia_first_lookup(shared_id_rows):
    # Documented ambiguity kept for existing bare-id clients. New clients send
    # composite keys, so selection and packaging never rely on this path.
    dfia, _incentive = shared_id_rows
    found_type, licence = LicenseLedgerViewSet()._authorized_license(None, str(SHARED_ID), "AUTO")
    assert found_type == "DFIA"
    assert licence.pk == dfia.pk
