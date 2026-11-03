"""
Contract tests for the licence list endpoint (``GET /api/licenses/``).

These go through the real endpoint, so they pin what the frontend actually
depends on: every filter alone, the include/exclude NULL rules, inclusive
date and balance boundaries, the three-state boolean filters, combinations,
pagination, the default ordering, malformed input (400, never 500), and the
role gates.

Two conventions used throughout:

- Every request states ``is_expired`` and ``flags__is_null`` explicitly
  (``all`` unless the test is about them). Without that, the backend silently
  applies ``False`` to both (BR-1 / BR-2), which would hide fixtures and make
  the assertions depend on which licences happen to be expired or "null".
- Live balance is set through real export/import/debit rows, not the stored
  ``LicenseBalance`` cache, because the list filters read the live figure.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.core.models import (
    HeadSIONNormsModel,
    NotificationNumber,
    PortModel,
    PurchaseStatus,
    SchemeCode,
    SionNormClassModel,
)
from apps.license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
    LicenseTransferModel,
)
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin

User = get_user_model()

URL = "/api/licenses/"
# Explicit baseline: every request in this module sends these unless a test
# overrides them, so the backend's silent defaults never decide a result.
BASELINE = {"is_expired": "all", "flags__is_null": "all", "page_size": 200}
DEBIT = Decimal("1000.00")
# Measured 17 queries for a page of 5 and for a page of 25 (non-live path,
# every row carrying a transfer and a norm-classed export line); ceiling = +3.
# The accordion's canonical available CIF adds one fixed batch of 4 queries per
# page (`available_cif_by_licence`). That is 21, so ceiling = 21 + 3.
QUERY_CEILING_PER_PAGE = 24


class LicenseListFilterContractTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def setUp(self):
        self.viewer = self._user_with_roles("LICENSE_VIEWER")
        self.client = APIClient()
        self.client.force_authenticate(user=self.viewer)
        self.boe_company = self.make_company("BOE Company")
        self._seq = 0

    # ------------------------------------------------------------------
    # Fixture helpers
    # ------------------------------------------------------------------
    def _user_with_roles(self, *roles):
        user = User.objects.create_user(
            username=f"list-contract-{self._uuid()}",
            email=f"{self._uuid()}@example.com",
            password="testpass123!",
        )
        for role in roles:
            group, _ = Group.objects.get_or_create(name=role)
            user.groups.add(group)
        return user

    @staticmethod
    def _uuid():
        return uuid.uuid4().hex[:8]

    def _licence(self, *, exporter=None, port=None, purchase_status=None, scheme_code=None,
                 notification_number=None, expiry=..., license_date=None, balance=None):
        """Create a licence with an explicit, searchable number (prefix ``LST``)."""
        self._seq += 1
        today = date.today()
        if expiry is ...:
            expiry = today + timedelta(days=365)
        license_obj = LicenseDetailsModel.objects.create(
            license_number=f"LST{self._seq:04d}-{self._uuid()}",
            license_date=license_date or today,
            license_expiry_date=expiry,
            exporter=exporter,
            port=port,
            purchase_status=purchase_status,
            scheme_code=scheme_code,
            notification_number=notification_number,
        )
        if balance is not None:
            self._give_live_balance(license_obj, Decimal(balance))
        return license_obj

    def _give_live_balance(self, license_obj, balance):
        """Make the live financial balance equal ``balance`` (export CIF less one debit)."""
        export_cif = balance + DEBIT
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=export_cif)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Contract widget",
            quantity=Decimal("1000.000"),
            cif_fc=export_cif,
        )
        boe = self.make_boe(self.boe_company)
        self.make_debit_row(boe, item, cif_fc=DEBIT, qty=Decimal("100.000"))

    def _ps(self, code):
        status, _ = PurchaseStatus.objects.get_or_create(code=code, defaults={"label": f"Status {code}"})
        return status

    def _get(self, **params):
        response = self.client.get(URL, {**BASELINE, **params})
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def _ids(self, **params):
        return {row["id"] for row in self._get(**params).data["results"]}

    # ------------------------------------------------------------------
    # BE-01: ordering=balance_cif must never 500
    # ------------------------------------------------------------------
    def test_ordering_by_balance_cif_is_ignored_not_500(self):
        """``balance_cif`` is a property, not a column. It must not be an ordering field.

        Before the fix the view listed it in ``ordering_fields``, so DRF passed
        it to ``order_by`` and the request failed with a FieldError (HTTP 500).
        After the fix the term is dropped like any other unknown ordering field
        and the default order applies.
        """
        self._licence()
        response = self.client.get(URL, {**BASELINE, "ordering": "balance_cif"})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn("balance_cif", response.data["ordering_fields"])

    def test_ordering_by_balance_cif_mixed_with_a_real_field_still_sorts_by_the_real_field(self):
        older = self._licence(expiry=date.today() + timedelta(days=5))
        newer = self._licence(expiry=date.today() + timedelta(days=50))

        response = self.client.get(URL, {**BASELINE, "ordering": "balance_cif,-license_expiry_date"})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([row["id"] for row in response.data["results"]][:2], [newer.id, older.id])

    # ------------------------------------------------------------------
    # BE-08: default ordering is expiry first, then licence number, then id
    # ------------------------------------------------------------------
    def test_default_order_is_expiry_then_licence_number_not_primary_key(self):
        """No ``ordering`` param: order by expiry, then licence number.

        The three licences are created so that primary-key order differs from
        the documented order. Two share an expiry date and are told apart by
        licence number, which is unique, so the result is fully deterministic.
        """
        far = self._licence(expiry=date.today() + timedelta(days=30))
        tie_second = self._licence(expiry=date.today() + timedelta(days=10))
        tie_first = self._licence(expiry=date.today() + timedelta(days=10))
        # Force the licence-number order to be the reverse of creation order.
        LicenseDetailsModel.objects.filter(pk=tie_second.pk).update(license_number="LSTZZ-B")
        LicenseDetailsModel.objects.filter(pk=tie_first.pk).update(license_number="LSTAA-A")
        self.assertLess(far.pk, tie_second.pk)
        self.assertLess(tie_second.pk, tie_first.pk)

        expected = [tie_first.id, tie_second.id, far.id]
        first = self.client.get(URL, {"is_expired": "all", "flags__is_null": "all", "page_size": 200})
        second = self.client.get(URL, {"is_expired": "all", "flags__is_null": "all", "page_size": 200})

        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual([row["id"] for row in first.data["results"]], expected)
        self.assertEqual([row["id"] for row in second.data["results"]], expected)

    def test_explicit_ordering_param_overrides_the_default(self):
        far = self._licence(expiry=date.today() + timedelta(days=30))
        near = self._licence(expiry=date.today() + timedelta(days=10))

        response = self.client.get(URL, {**BASELINE, "ordering": "-license_expiry_date"})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([row["id"] for row in response.data["results"]], [far.id, near.id])

    # ------------------------------------------------------------------
    # BE-02: malformed input is a field-level 400, never a 500
    # ------------------------------------------------------------------
    def test_malformed_balance_bounds_return_400_naming_the_parameter(self):
        self._licence(balance="500")
        for param in ("balance__balance_cif_min", "balance__balance_cif_max"):
            for bad in ("abc", "1,5", "NaN", "Infinity", "--1"):
                with self.subTest(param=param, value=bad):
                    response = self.client.get(URL, {**BASELINE, param: bad})
                    self.assertEqual(response.status_code, 400, response.data)
                    self.assertIn(param, response.data)

    def test_malformed_dates_return_400_naming_the_parameter(self):
        cases = {
            "license_date__gte": "abc",
            "license_expiry_date__lte": "2026-13-45",
            "license_date_from": "2026/01/01",
            "license_expiry_date_to": "01-02-2026",
            "license_date__lte": "2026-01-01T10:00",
        }
        for param, bad in cases.items():
            with self.subTest(param=param, value=bad):
                response = self.client.get(URL, {**BASELINE, param: bad})
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(param, response.data)

    def test_malformed_id_filters_return_400_naming_the_parameter(self):
        cases = {
            "exporter": "abc",
            "exclude_exporter": "1.5",
            "port": "x",
            "exclude_port": "abc",
            "purchase_status": "1,abc",
            "export_license__norm_class": "A3627",
        }
        for param, bad in cases.items():
            with self.subTest(param=param, value=bad):
                response = self.client.get(URL, {**BASELINE, param: bad})
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(param, response.data)

    def test_malformed_model_field_params_return_400(self):
        # Direct model-field names that are not configured filters reach the
        # generic remaining-params loop, which used to 500 on a bad value.
        for param, bad in {"id": "abc", "individual_item_cif_override": "maybe"}.items():
            with self.subTest(param=param, value=bad):
                response = self.client.get(URL, {**BASELINE, param: bad})
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(param, response.data)

    def test_id_outside_the_integer_range_matches_nothing_and_is_not_500(self):
        """A well-formed id too large for the database column is an unknown id, not an error."""
        response = self._get(exporter="99999999999999999999", purchase_status="-99999999999")

        self.assertEqual(response.data["count"], 0)

    def test_valid_forms_that_worked_before_are_still_accepted(self):
        """Regression guard: the validation must not reject any input that already worked."""
        match = self._licence(balance="500.00", expiry=date.today() + timedelta(days=5))
        today = date.today().isoformat()
        cases = [
            {"balance__balance_cif_min": "500"},
            {"balance__balance_cif_min": "499.99", "balance__balance_cif_max": "500.00"},
            {"balance__balance_cif_min": "-100"},
            {"balance__balance_cif_max": "1e3"},
            {"license_date__gte": today, "license_date__lte": today},
            {"license_expiry_date_from": today, "license_expiry_date_to": today},
            {"exporter": "-1"},
            {"purchase_status": "1,2,,3"},
            {"is_expired": "True"},
            {"is_expired": "false"},
            {"flags__is_null": "1"},
            {"is_planned": "all"},
        ]
        for params in cases:
            with self.subTest(params=params):
                response = self.client.get(URL, {"page_size": 200, **params})
                self.assertEqual(response.status_code, 200, response.data)

        self.assertIn(match.id, self._ids(balance__balance_cif_min="500", balance__balance_cif_max="500.00"))

    def test_empty_values_are_ignored_as_before(self):
        self._licence(balance="500")
        response = self.client.get(URL, {
            "is_expired": "all", "flags__is_null": "all", "page_size": 200,
            "balance__balance_cif_min": "", "balance__balance_cif_max": "",
            "exporter": "", "license_date__gte": "", "license_expiry_date__lte": "",
        })
        self.assertEqual(response.status_code, 200, response.data)

    # ------------------------------------------------------------------
    # Single filters
    # ------------------------------------------------------------------
    def test_exporter_filter_matches_only_the_selected_company(self):
        company_a = self.make_company("Exporter A")
        company_b = self.make_company("Exporter B")
        in_a = self._licence(exporter=company_a)
        in_b = self._licence(exporter=company_b)

        ids = self._ids(exporter=str(company_a.id))

        self.assertIn(in_a.id, ids)
        self.assertNotIn(in_b.id, ids)

    def test_exporter_csv_is_or_across_ids(self):
        company_a = self.make_company("Exporter A")
        company_b = self.make_company("Exporter B")
        company_c = self.make_company("Exporter C")
        in_a = self._licence(exporter=company_a)
        in_b = self._licence(exporter=company_b)
        in_c = self._licence(exporter=company_c)

        ids = self._ids(exporter=f"{company_a.id},{company_b.id}")

        self.assertTrue({in_a.id, in_b.id}.issubset(ids))
        self.assertNotIn(in_c.id, ids)

    def test_exclude_exporter_keeps_licences_without_an_exporter(self):
        company_a = self.make_company("Exporter A")
        company_b = self.make_company("Exporter B")
        excluded = self._licence(exporter=company_a)
        kept = self._licence(exporter=company_b)
        no_exporter = self._licence(exporter=None)

        ids = self._ids(exclude_exporter=str(company_a.id))

        self.assertIn(kept.id, ids)
        self.assertIn(no_exporter.id, ids, "NULL exporter must survive NOT IN (BR-6)")
        self.assertNotIn(excluded.id, ids)

    def test_port_filter_matches_only_the_selected_port(self):
        port_a = self.make_port()
        port_b = PortModel.objects.create(code="TSTPB", name="Port B")
        in_a = self._licence(port=port_a)
        in_b = self._licence(port=port_b)

        ids = self._ids(port=str(port_a.id))

        self.assertIn(in_a.id, ids)
        self.assertNotIn(in_b.id, ids)

    def test_exclude_port_keeps_licences_without_a_port(self):
        port_a = self.make_port()
        port_b = PortModel.objects.create(code="TSTPC", name="Port C")
        excluded = self._licence(port=port_a)
        kept = self._licence(port=port_b)
        no_port = self._licence(port=None)

        ids = self._ids(exclude_port=str(port_a.id))

        self.assertIn(kept.id, ids)
        self.assertIn(no_port.id, ids, "NULL port must survive NOT IN (BR-6)")
        self.assertNotIn(excluded.id, ids)

    def test_purchase_status_is_or_across_ids_and_unknown_id_matches_nothing(self):
        ps1, ps2, ps3 = self._ps("P1"), self._ps("P2"), self._ps("P3")
        l1 = self._licence(purchase_status=ps1)
        l2 = self._licence(purchase_status=ps2)
        l3 = self._licence(purchase_status=ps3)
        unknown_id = 987654

        self.assertEqual(self._ids(purchase_status=f"{ps1.id},{ps2.id}") & {l1.id, l2.id, l3.id},
                         {l1.id, l2.id})
        self.assertEqual(self._ids(purchase_status=str(unknown_id)) & {l1.id, l2.id, l3.id}, set())
        self.assertEqual(self._ids(purchase_status=f"{ps1.id},{unknown_id}") & {l1.id, l2.id, l3.id},
                         {l1.id})

    def test_purchase_status_array_format_is_or(self):
        ps1, ps2, ps3 = self._ps("A1"), self._ps("A2"), self._ps("A3")
        l1 = self._licence(purchase_status=ps1)
        l2 = self._licence(purchase_status=ps2)
        l3 = self._licence(purchase_status=ps3)

        response = self.client.get(URL, {**BASELINE, "purchase_status[]": [str(ps1.id), str(ps3.id)]})

        self.assertEqual(response.status_code, 200, response.data)
        ids = {row["id"] for row in response.data["results"]}
        self.assertTrue({l1.id, l3.id}.issubset(ids))
        self.assertNotIn(l2.id, ids)

    def test_scheme_code_filters_by_code_not_by_id(self):
        dfia, _ = SchemeCode.objects.get_or_create(code="DFIA", defaults={"label": "DFIA"})
        other, _ = SchemeCode.objects.get_or_create(code="ZZT1", defaults={"label": "Other"})
        matched = self._licence(scheme_code=dfia)
        not_matched = self._licence(scheme_code=other)

        ids = self._ids(scheme_code="DFIA")

        self.assertIn(matched.id, ids)
        self.assertNotIn(not_matched.id, ids)

    def test_notification_number_filters_by_code(self):
        notif, _ = NotificationNumber.objects.get_or_create(code="N-1", defaults={"label": "N-1"})
        other, _ = NotificationNumber.objects.get_or_create(code="N-2", defaults={"label": "N-2"})
        matched = self._licence(notification_number=notif)
        not_matched = self._licence(notification_number=other)

        ids = self._ids(notification_number="N-1")

        self.assertIn(matched.id, ids)
        self.assertNotIn(not_matched.id, ids)

    def test_norm_class_filter_returns_each_licence_once(self):
        """A licence with two export lines of the same norm class must appear once (distinct())."""
        head = HeadSIONNormsModel.objects.create(name=f"ListContract{self._uuid()}")
        norm = SionNormClassModel.objects.create(head_norm=head, norm_class=f"LC{self._uuid()}", is_active=True)
        licence = self._licence()
        LicenseExportItemModel.objects.create(license=licence, cif_fc=Decimal("10"), norm_class=norm)
        LicenseExportItemModel.objects.create(license=licence, cif_fc=Decimal("20"), norm_class=norm)

        response = self._get(export_license__norm_class=str(norm.id))

        ids = [row["id"] for row in response.data["results"]]
        self.assertEqual(ids.count(licence.id), 1)
        self.assertEqual(response.data["count"], 1)

    def test_license_date_bounds_are_inclusive(self):
        day = date(2026, 3, 10)
        before = self._licence(license_date=day - timedelta(days=1))
        start = self._licence(license_date=day)
        end = self._licence(license_date=day + timedelta(days=5))
        after = self._licence(license_date=day + timedelta(days=6))

        ids = self._ids(license_date__gte=day.isoformat(), license_date__lte=(day + timedelta(days=5)).isoformat())

        self.assertTrue({start.id, end.id}.issubset(ids))
        self.assertNotIn(before.id, ids)
        self.assertNotIn(after.id, ids)

    def test_license_expiry_bounds_are_inclusive_and_exclude_null_expiry(self):
        day = date(2027, 6, 1)
        before = self._licence(expiry=day - timedelta(days=1))
        start = self._licence(expiry=day)
        end = self._licence(expiry=day + timedelta(days=3))
        after = self._licence(expiry=day + timedelta(days=4))
        no_expiry = self._licence(expiry=None)

        ids = self._ids(license_expiry_date__gte=day.isoformat(),
                        license_expiry_date__lte=(day + timedelta(days=3)).isoformat())

        self.assertTrue({start.id, end.id}.issubset(ids))
        self.assertNotIn(before.id, ids)
        self.assertNotIn(after.id, ids)
        self.assertNotIn(no_expiry.id, ids, "A NULL expiry cannot satisfy a date bound")

    def test_from_to_aliases_behave_like_gte_lte(self):
        day = date(2026, 3, 10)
        inside = self._licence(license_date=day)
        outside = self._licence(license_date=day + timedelta(days=30))
        lo, hi = day.isoformat(), day.isoformat()

        via_aliases = self._ids(license_date_from=lo, license_date_to=hi)
        via_django = self._ids(license_date__gte=lo, license_date__lte=hi)

        self.assertEqual(via_aliases & {inside.id, outside.id}, via_django & {inside.id, outside.id})
        self.assertIn(inside.id, via_aliases)
        self.assertNotIn(outside.id, via_aliases)

    def test_balance_bounds_are_inclusive_at_exactly_the_boundary(self):
        below = self._licence(balance="199.99")
        at_min = self._licence(balance="500.00")
        at_max = self._licence(balance="800.00")
        above = self._licence(balance="800.01")
        for licence_obj, expected in ((below, "199.99"), (at_min, "500.00"), (at_max, "800.00"), (above, "800.01")):
            self.assertEqual(LicenseBalanceCalculator.calculate_financial_balance(licence_obj), Decimal(expected))

        ids = self._ids(balance__balance_cif_min="500.00", balance__balance_cif_max="800.00")

        self.assertEqual(ids & {below.id, at_min.id, at_max.id, above.id}, {at_min.id, at_max.id})

    def test_is_expired_true_false_all_with_null_expiry_as_not_expired(self):
        expired = self._licence(expiry=date.today() - timedelta(days=1))
        active = self._licence(expiry=date.today() + timedelta(days=10))
        no_expiry = self._licence(expiry=None)

        expired_ids = self._ids(is_expired="True")
        active_ids = self._ids(is_expired="False")
        all_ids = self._ids(is_expired="all")

        self.assertIn(expired.id, expired_ids)
        self.assertNotIn(active.id, expired_ids)
        self.assertNotIn(no_expiry.id, expired_ids)
        self.assertIn(active.id, active_ids)
        self.assertIn(no_expiry.id, active_ids, "NULL expiry counts as not expired (BR-1)")
        self.assertNotIn(expired.id, active_ids)
        self.assertTrue({expired.id, active.id, no_expiry.id}.issubset(all_ids))

    def test_flags_is_null_true_false_all_uses_live_200_threshold(self):
        low = self._licence(balance="199.99")
        high = self._licence(balance="200.00")

        null_ids = self._ids(flags__is_null="true")
        non_null_ids = self._ids(flags__is_null="false")
        all_ids = self._ids(flags__is_null="all")

        self.assertIn(low.id, null_ids)
        self.assertNotIn(high.id, null_ids)
        self.assertIn(high.id, non_null_ids)
        self.assertNotIn(low.id, non_null_ids)
        self.assertTrue({low.id, high.id}.issubset(all_ids))

    def test_is_planned_true_false_all(self):
        company = self.make_company("Plan Co")
        planned = self._licence(exporter=company)
        unplanned = self._licence(exporter=company)
        item = LicenseImportItemsModel.objects.create(
            license=planned, serial_number=1, description="Planned item",
            quantity=Decimal("10.000"), cif_fc=Decimal("10.00"),
        )
        LicenseItemPlan.objects.create(
            license=planned, import_item=item, planned_quantity=Decimal("1"), planned_cif_fc=Decimal("1"),
            baseline_used_quantity=Decimal("0"), baseline_used_cif_fc=Decimal("0"),
        )

        planned_ids = self._ids(is_planned="True", exporter=str(company.id))
        unplanned_ids = self._ids(is_planned="False", exporter=str(company.id))
        all_ids = self._ids(is_planned="all", exporter=str(company.id))

        self.assertEqual(planned_ids, {planned.id})
        self.assertEqual(unplanned_ids, {unplanned.id})
        self.assertEqual(all_ids, {planned.id, unplanned.id})

    def test_absent_is_expired_applies_the_false_default(self):
        """BR-1: with no ``is_expired`` param, expired licences are hidden."""
        expired = self._licence(expiry=date.today() - timedelta(days=1))
        active = self._licence(expiry=date.today() + timedelta(days=1))

        response = self.client.get(URL, {"page_size": 200})

        self.assertEqual(response.status_code, 200, response.data)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(active.id, ids)
        self.assertNotIn(expired.id, ids)

    def test_absent_flags_is_null_currently_applies_no_filter(self):
        """Pins CURRENT behaviour, which differs from BR-2 and design doc §6.1.

        ``license.py`` reads ``default_filters.get('is_null')`` but the configured
        key is ``flags__is_null``, so an absent param applies no filter and
        null-balance licences are returned. The doc says ``False`` is applied.
        Changing this alters results for every caller that omits the param, so
        it is a decision for the owner. If it is changed, flip this test.
        """
        null_balance = self._licence(balance="0")

        response = self.client.get(URL, {"is_expired": "all", "page_size": 200})

        self.assertEqual(response.status_code, 200, response.data)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(null_balance.id, ids)

    # ------------------------------------------------------------------
    # Combinations
    # ------------------------------------------------------------------
    def test_exporter_and_purchase_status_combine_with_and(self):
        company_a = self.make_company("Combo A")
        company_b = self.make_company("Combo B")
        ps = self._ps("C1")
        other_ps = self._ps("C2")
        a_ps = self._licence(exporter=company_a, purchase_status=ps)
        a_other = self._licence(exporter=company_a, purchase_status=other_ps)
        b_ps = self._licence(exporter=company_b, purchase_status=ps)

        ids = self._ids(exporter=str(company_a.id), purchase_status=str(ps.id))

        self.assertIn(a_ps.id, ids)
        self.assertNotIn(a_other.id, ids)
        self.assertNotIn(b_ps.id, ids)

    def test_exporter_and_port_combine_with_and(self):
        company = self.make_company("Combo Port")
        port = self.make_port()
        other_port = PortModel.objects.create(code="TSTCP", name="Other port")
        match = self._licence(exporter=company, port=port)
        wrong_port = self._licence(exporter=company, port=other_port)
        wrong_company = self._licence(exporter=self.make_company("Other co"), port=port)

        ids = self._ids(exporter=str(company.id), port=str(port.id))

        self.assertIn(match.id, ids)
        self.assertNotIn(wrong_port.id, ids)
        self.assertNotIn(wrong_company.id, ids)

    def test_purchase_status_and_is_expired_combine_with_and(self):
        ps = self._ps("E1")
        expired = self._licence(purchase_status=ps, expiry=date.today() - timedelta(days=2))
        active = self._licence(purchase_status=ps, expiry=date.today() + timedelta(days=2))

        ids = self._ids(purchase_status=str(ps.id), is_expired="True")

        self.assertEqual(ids & {expired.id, active.id}, {expired.id})

    def test_balance_range_and_flags_is_null_combine_with_and(self):
        low_100 = self._licence(balance="100")
        mid_150 = self._licence(balance="150")
        high_250 = self._licence(balance="250")

        ids = self._ids(balance__balance_cif_min="100", balance__balance_cif_max="300",
                        flags__is_null="true")

        self.assertEqual(ids & {low_100.id, mid_150.id, high_250.id}, {low_100.id, mid_150.id})

    def test_license_date_and_expiry_ranges_combine_with_and(self):
        issued = date(2026, 5, 1)
        match = self._licence(license_date=issued, expiry=date(2027, 5, 1))
        wrong_expiry = self._licence(license_date=issued, expiry=date(2029, 5, 1))
        wrong_issue = self._licence(license_date=date(2025, 1, 1), expiry=date(2027, 5, 1))

        ids = self._ids(license_date__gte="2026-01-01", license_date__lte="2026-12-31",
                        license_expiry_date__gte="2027-01-01", license_expiry_date__lte="2027-12-31")

        self.assertEqual(ids & {match.id, wrong_expiry.id, wrong_issue.id}, {match.id})

    def test_search_combines_with_two_filters(self):
        company = self.make_company("Search Co")
        ps = self._ps("S1")
        hit = self._licence(exporter=company, purchase_status=ps)
        wrong_status = self._licence(exporter=company, purchase_status=self._ps("S2"))
        outside_search = self._licence(exporter=company, purchase_status=ps)
        LicenseDetailsModel.objects.filter(pk=outside_search.pk).update(license_number="OTHER-99999")

        ids = self._ids(search="LST", exporter=str(company.id), purchase_status=str(ps.id))

        self.assertIn(hit.id, ids)
        self.assertNotIn(wrong_status.id, ids)
        self.assertNotIn(outside_search.id, ids)

    def test_exclude_and_include_on_different_ids_combine_with_and(self):
        company_a = self.make_company("Include A")
        company_b = self.make_company("Include B")
        company_c = self.make_company("Include C")
        in_a = self._licence(exporter=company_a)
        in_b = self._licence(exporter=company_b)
        in_c = self._licence(exporter=company_c)

        ids = self._ids(exporter=f"{company_a.id},{company_b.id}", exclude_exporter=str(company_b.id))

        self.assertIn(in_a.id, ids)
        self.assertNotIn(in_b.id, ids)
        self.assertNotIn(in_c.id, ids)

    def test_same_id_in_include_and_exclude_returns_no_rows(self):
        """Documents FE-13: the API does not reject a contradictory pair. It returns zero rows."""
        company = self.make_company("Contradiction Co")
        self._licence(exporter=company)

        response = self._get(exporter=str(company.id), exclude_exporter=str(company.id))

        self.assertEqual(response.data["results"], [])
        self.assertEqual(response.data["count"], 0)

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------
    def test_pages_have_no_duplicates_and_no_gaps(self):
        company = self.make_company("Paging Co")
        created = {self._licence(exporter=company).id for _ in range(5)}

        seen = []
        for page in (1, 2, 3):
            response = self.client.get(URL, {**BASELINE, "exporter": str(company.id),
                                             "page": page, "page_size": 2})
            self.assertEqual(response.status_code, 200, response.data)
            seen.extend(row["id"] for row in response.data["results"])

        self.assertEqual(len(seen), len(set(seen)), "a licence appeared on two pages")
        self.assertEqual(set(seen), created, "a licence was missing from every page")

    def test_page_beyond_the_last_returns_404(self):
        company = self.make_company("Last Page Co")
        for _ in range(3):
            self._licence(exporter=company)

        response = self.client.get(URL, {**BASELINE, "exporter": str(company.id),
                                         "page": 3, "page_size": 2})

        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------
    def test_unauthenticated_request_is_rejected_with_401(self):
        response = APIClient().get(URL, BASELINE)

        self.assertEqual(response.status_code, 401)

    def test_user_without_a_licence_role_is_forbidden(self):
        client = APIClient()
        client.force_authenticate(user=self._user_with_roles())

        self.assertEqual(client.get(URL, BASELINE).status_code, 403)

    def test_read_only_licence_viewer_can_list_but_not_create(self):
        self._licence()

        read = self.client.get(URL, BASELINE)
        write = self.client.post(URL, {}, format="json")

        self.assertEqual(read.status_code, 200, read.data)
        self.assertEqual(write.status_code, 403)

    # ------------------------------------------------------------------
    # Query count
    # ------------------------------------------------------------------
    def _count_queries(self, page_size, **params):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(URL, {"page_size": page_size, **params})
        self.assertEqual(response.status_code, 200, response.data)
        return len(ctx.captured_queries)

    def _licence_with_row_relations(self, company, norm):
        """A licence carrying every per-row relation the list serializer reads."""
        licence = self._licence(exporter=company, purchase_status=self._ps("Q1"))
        LicenseExportItemModel.objects.create(license=licence, cif_fc=Decimal("10"), norm_class=norm)
        LicenseTransferModel.objects.create(
            license=licence, transfer_status="Transferred", transfer_date=date.today(),
        )
        return licence

    def test_query_count_for_a_page_does_not_grow_with_page_size(self):
        """Non-live path (``is_expired=all``, ``flags__is_null=all``): the page size must not add queries.

        Each licence carries a transfer and an export line with a norm class,
        the relations the list serializer reads per row. Before the prefetch
        fix each one cost a query per row.
        """
        company = self.make_company("Query Co")
        head = HeadSIONNormsModel.objects.create(name=f"QueryHead{self._uuid()}")
        norm = SionNormClassModel.objects.create(head_norm=head, norm_class=f"QN{self._uuid()}", is_active=True)
        params = dict(exporter=str(company.id), is_expired="all", flags__is_null="all")
        for _ in range(5):
            self._licence_with_row_relations(company, norm)
        self._count_queries(5, **params)  # warm process-level caches so both counts are comparable

        five = self._count_queries(5, **params)
        for _ in range(20):
            self._licence_with_row_relations(company, norm)
        twenty_five = self._count_queries(25, **params)

        self.assertEqual(twenty_five, five, "query count grew with page size")
        self.assertLessEqual(twenty_five, QUERY_CEILING_PER_PAGE)

    def test_list_latest_transfer_and_norm_class_match_the_detail_view(self):
        """The list reads transfers and norm classes from prefetches; detail reads them directly. Same values."""
        company = self.make_company("Match Co")
        head = HeadSIONNormsModel.objects.create(name=f"MatchHead{self._uuid()}")
        norm = SionNormClassModel.objects.create(head_norm=head, norm_class=f"MN{self._uuid()}", is_active=True)
        licence = self._licence(exporter=company)
        LicenseExportItemModel.objects.create(license=licence, cif_fc=Decimal("10"), norm_class=norm)
        LicenseTransferModel.objects.create(
            license=licence, transfer_status="Old", transfer_date=date(2026, 1, 1),
        )
        LicenseTransferModel.objects.create(
            license=licence, transfer_status="New", transfer_date=date(2026, 6, 1),
        )

        listed = self._get(exporter=str(company.id))
        row = next(r for r in listed.data["results"] if r["id"] == licence.id)
        detail = self.client.get(f"{URL}{licence.id}/")

        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(row["latest_transfer"], detail.data["latest_transfer"])
        self.assertIn("New", row["latest_transfer"], "the most recent transfer must win")
        self.assertEqual(row["get_norm_class"], detail.data["get_norm_class"])
        self.assertEqual(row["get_norm_class"], norm.norm_class)
