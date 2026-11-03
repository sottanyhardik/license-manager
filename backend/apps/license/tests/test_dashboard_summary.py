"""
Dashboard v3 contract tests: bridge identities, expiry bands, scope and
validation, role-gated sections, error isolation, caching, and invoice status.
Contract: docs/09-module-implementation/dashboard.md §4.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.license.models import LicenseExportItemModel, LicenseFlags
from apps.license.services import dashboard_summary as summary
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.trade.models import LicenseTrade, LicenseTradePayment

from .test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


def _today():
    return date.today()


def _scope(**kwargs):
    return summary.DashboardScope(as_of=_today(), **kwargs)


def _money(value: str) -> Decimal:
    return Decimal(value)


class FlaggedLicenceMixin(LicenseBalanceLedgerFixtureMixin):
    """Creates a licence with explicit flags, so each test controls the stored status."""

    def make_flagged(self, company, expiry, *, active=True, expired=None, null=False):
        licence = self.make_license(company)
        licence.license_expiry_date = expiry
        licence.save()
        LicenseFlags.objects.update_or_create(
            license=licence,
            defaults={
                "is_active": active,
                "is_expired": (expiry is not None and expiry < _today()) if expired is None else expired,
                "is_null": null,
            },
        )
        return licence


class EngineProjectionTests(FlaggedLicenceMixin, TestCase):
    def test_financial_balance_is_the_projection_of_the_components(self):
        company = self.make_company()
        licence = self.make_license(company)
        LicenseExportItemModel.objects.create(license=licence, cif_fc=Decimal("9000.00"))
        item = self.make_item(licence, 1)
        self.make_debit_row(self.make_boe(company), item, cif_fc=Decimal("2000.00"))

        components = LicenseBalanceCalculator.calculate_financial_components_for_licenses([licence.pk])
        projected = LicenseBalanceCalculator.calculate_financial_balance_for_licenses([licence.pk])

        self.assertEqual(components[licence.pk]["available"], Decimal("7000.00"))
        self.assertEqual(projected[licence.pk], components[licence.pk]["available"])
        self.assertEqual(licence.get_balance_cif, components[licence.pk]["available"])


class BridgeTests(FlaggedLicenceMixin, TestCase):
    def test_bridge_closes_exactly_and_the_floor_is_reported_separately(self):
        company = self.make_company()
        healthy = self.make_flagged(company, _today() + timedelta(days=200))
        LicenseExportItemModel.objects.create(license=healthy, cif_fc=Decimal("9000.00"))
        self.make_debit_row(self.make_boe(company), self.make_item(healthy, 1), cif_fc=Decimal("2000.00"))

        over = self.make_flagged(company, _today() + timedelta(days=200))
        LicenseExportItemModel.objects.create(license=over, cif_fc=Decimal("100.00"))
        over_item = self.make_item(over, 1)
        self.make_debit_row(self.make_boe(company), over_item, cif_fc=Decimal("90.00"))
        self.make_debit_row(self.make_boe(company), over_item, cif_fc=Decimal("20.00"))

        financial = summary._licence_snapshot(_scope())["financial"]
        bridge = financial["bridge"]

        self.assertEqual(financial["authorized_cif"], "9100.00")
        self.assertEqual(financial["utilized_cif"], "2110.00")
        self.assertEqual(financial["available_cif"], "7000.00")
        self.assertEqual(financial["over_utilised_licences"], 1)
        self.assertEqual(bridge["raw_available"], "6990.00")
        self.assertEqual(bridge["over_utilisation_floor"], "10.00")

        # Identities: the bridge closes, and the floor is the only term after raw.
        rebuilt_raw = (
            _money(bridge["authorized"])
            - _money(bridge["previous_owner_utilisation"])
            + _money(bridge["purchased_cif"])
            - _money(bridge["sale_utilisation"])
            - _money(bridge["boe_utilisation"])
            - _money(bridge["reserved"])
            + _money(bridge["rounding"])
        )
        self.assertEqual(rebuilt_raw, _money(bridge["raw_available"]))
        self.assertEqual(
            _money(bridge["raw_available"]) + _money(bridge["over_utilisation_floor"]),
            _money(bridge["available"]),
        )
        self.assertEqual(bridge["available"], financial["available_cif"])

    def test_committed_percentage_is_null_without_authorised_cif(self):
        financial = summary._licence_snapshot(_scope())["financial"]
        self.assertIsNone(financial["committed_pct"])


class PortfolioTests(FlaggedLicenceMixin, TestCase):
    def test_expiry_bands_partition_every_licence_and_the_windows_are_inclusive(self):
        company = self.make_company()
        today = _today()
        self.make_flagged(company, today)                                  # d0_7
        self.make_flagged(company, today - timedelta(days=1))              # expired (date)
        self.make_flagged(company, today + timedelta(days=7))              # d0_7
        self.make_flagged(company, today + timedelta(days=8))              # d8_15
        self.make_flagged(company, today + timedelta(days=15))             # d8_15
        self.make_flagged(company, today + timedelta(days=16))             # d16_30
        self.make_flagged(company, today + timedelta(days=30))             # d16_30
        self.make_flagged(company, today + timedelta(days=31))             # d31_60
        self.make_flagged(company, today + timedelta(days=60))             # d31_60
        self.make_flagged(company, today + timedelta(days=61))             # over_60
        self.make_flagged(company, None)                                   # no_expiry
        self.make_flagged(company, today + timedelta(days=100), active=False)  # inactive
        # Stale flag, date in the future: the date rule decides, so this is active in d16_30.
        self.make_flagged(company, today + timedelta(days=20), expired=True, null=False)
        # Stale flag, date in the past: the date rule decides, so this is expired.
        self.make_flagged(company, today - timedelta(days=10), expired=False)
        self.make_flagged(company, today + timedelta(days=40))

        portfolio = summary._licence_snapshot(_scope())["portfolio"]
        bands = {row["key"]: row["count"] for row in portfolio["bands"]}

        self.assertEqual(portfolio["total"], 15)
        self.assertEqual(sum(bands.values()), portfolio["total"], "bands must partition the licences")
        self.assertEqual(bands, {
            "expired": 2, "d0_7": 2, "d8_15": 2, "d16_30": 3, "d31_60": 3,
            "over_60": 1, "inactive": 1, "no_expiry": 1,
        })
        self.assertEqual(portfolio["expired"], 2)
        self.assertEqual(portfolio["active"], 12)
        self.assertEqual(portfolio["within"], {"7": 2, "15": 4, "30": 7, "60": 10})
        self.assertEqual(portfolio["stale_expiry_flags"], 2)

    def test_missing_dgft_follows_the_licence_list_live_balance_rule(self):
        """`is_null=True` in the licence list means live balance < 200. The count uses the same rule."""
        company = self.make_company()
        unfunded = self.make_flagged(company, _today() + timedelta(days=90))
        funded = self.make_flagged(company, _today() + timedelta(days=90))
        LicenseExportItemModel.objects.create(license=funded, cif_fc=Decimal("500.00"))

        snapshot = summary._licence_snapshot(_scope())

        self.assertEqual(snapshot["portfolio"]["missing_dgft"], 1)
        self.assertEqual(snapshot["exceptions"]["over_utilised"], [])
        self.assertTrue(unfunded.pk)

    def test_exception_lists_name_the_licences_behind_each_count(self):
        company = self.make_company()
        expired_funded = self.make_flagged(company, _today() - timedelta(days=5))
        LicenseExportItemModel.objects.create(license=expired_funded, cif_fc=Decimal("900.00"))
        stale = self.make_flagged(company, _today() + timedelta(days=50), expired=True)

        snapshot = summary._licence_snapshot(_scope())

        self.assertEqual(snapshot["metrics"]["expired_with_balance"], 1)
        self.assertEqual(
            snapshot["exceptions"]["expired_with_balance"],
            [{"id": expired_funded.pk, "license_number": expired_funded.license_number}],
        )
        self.assertEqual(
            snapshot["exceptions"]["stale_expiry_flags"],
            [{"id": stale.pk, "license_number": stale.license_number}],
        )

    def test_expiry_band_boundaries_are_pure(self):
        today = _today()
        self.assertEqual(summary.expiry_band(expiry=None, days=None, expired=False, active=True), "no_expiry")
        self.assertEqual(summary.expiry_band(expiry=today, days=0, expired=False, active=True), "d0_7")
        self.assertEqual(summary.expiry_band(expiry=today, days=0, expired=True, active=False), "expired")
        self.assertEqual(summary.expiry_band(expiry=today, days=0, expired=False, active=False), "inactive")

    def test_company_scope_excludes_other_companies(self):
        mine = self.make_company("Mine")
        other = self.make_company("Other")
        self.make_flagged(mine, _today() + timedelta(days=5))
        self.make_flagged(other, _today() + timedelta(days=5))

        portfolio = summary._licence_snapshot(_scope(company=mine))["portfolio"]
        self.assertEqual(portfolio["total"], 1)


class ActivityAndInvoiceTests(FlaggedLicenceMixin, TestCase):
    def test_boe_date_range_bounds_the_activity_counts(self):
        from apps.bill_of_entry.models import BillOfEntryModel

        company = self.make_company()
        inside = self.make_boe(company, number="IN-RANGE")
        outside = self.make_boe(company, number="OUT-OF-RANGE")
        BillOfEntryModel.objects.filter(pk=outside.pk).update(bill_of_entry_date=_today() - timedelta(days=400))

        boe = summary.build_boe_activity(_scope(company=company, date_from=_today() - timedelta(days=30)))
        self.assertEqual(boe["total"], 1)
        self.assertEqual(boe["recent"][0]["id"], inside.pk)
        self.assertEqual(boe["pending_licence_mapping"], 1, "a BOE with no licence rows is pending mapping")

    def test_invoice_status_follows_the_trade_settlement_rule(self):
        company = self.make_company()

        def trade(total, paid, number):
            t = LicenseTrade.objects.create(
                direction=LicenseTrade.DIR_SALE,
                from_company=company,
                invoice_number=number,
                invoice_date=_today(),
            )
            LicenseTrade.objects.filter(pk=t.pk).update(total_amount=Decimal(total))
            if paid:
                LicenseTradePayment.objects.create(trade=t, amount=Decimal(paid))
            return t

        trade("1000.00", "1000.00", f"INV-PAID-{uuid.uuid4().hex[:6]}")
        trade("1000.00", "400.00", f"INV-PART-{uuid.uuid4().hex[:6]}")
        trade("1000.00", None, f"INV-UNPAID-{uuid.uuid4().hex[:6]}")
        LicenseTrade.objects.create(direction=LicenseTrade.DIR_SALE, from_company=company, invoice_number="")

        invoices = summary.build_invoice_activity(_scope(company=company))

        self.assertEqual(invoices["total"], 3, "blank invoice numbers are not invoices")
        self.assertEqual((invoices["paid"], invoices["partially_paid"], invoices["unpaid"]), (1, 1, 1))
        self.assertEqual(invoices["outstanding_inr"], "1600.00")
        self.assertEqual(invoices["by_direction"]["sale"], {"total": 3, "outstanding_inr": "1600.00"})
        self.assertEqual(invoices["by_direction"]["purchase"], {"total": 0, "outstanding_inr": "0.00"})
        self.assertEqual(invoices["not_tracked"], ["draft", "pending", "confirmed", "posted"])


class ApiContractTests(FlaggedLicenceMixin, TestCase):
    def setUp(self):
        cache.clear()
        self.superuser = self.make_superuser()
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.superuser)

    def tearDown(self):
        cache.clear()

    def get(self, **params):
        return self.client_api.get(reverse("license:dashboard"), params)

    def test_bad_scope_is_rejected_with_400(self):
        company = self.make_company()
        self.assertEqual(self.get(company_id="abc").status_code, 400)
        self.assertEqual(self.get(company_id="999999").status_code, 400)
        self.assertEqual(self.get(date_from="2026-13-01").status_code, 400)
        self.assertEqual(self.get(date_from="2026-06-02", date_to="2026-06-01").status_code, 400)

    def test_scope_is_echoed_and_the_as_of_date_is_present(self):
        company = self.make_company("Echo Co")
        body = self.get(company_id=company.pk, date_from="2026-01-01", date_to="2026-12-31").json()

        self.assertEqual(body["meta"]["scope"]["company_id"], company.pk)
        self.assertEqual(body["meta"]["scope"]["company_name"], "Echo Co")
        self.assertEqual(body["meta"]["scope"]["date_from"], "2026-01-01")
        self.assertEqual(body["meta"]["as_of"], summary.as_of_today().isoformat())
        self.assertEqual(body["meta"]["units"], {"cif": "FC", "invoice": "INR"})

    def test_money_crosses_the_api_as_two_decimal_strings(self):
        body = self.get().json()
        financial = body["financial"]
        for key in ("authorized_cif", "utilized_cif", "reserved_cif", "available_cif"):
            self.assertRegex(financial[key], r"^-?\d+\.\d{2}$")

    def test_second_request_is_served_from_cache_and_refresh_bypasses_it(self):
        first = self.get().json()
        self.assertFalse(first["meta"]["cached"])
        second = self.get().json()
        self.assertTrue(second["meta"]["cached"])
        refreshed = self.get(refresh="1").json()
        self.assertFalse(refreshed["meta"]["cached"])

    def test_cache_key_includes_the_scope(self):
        company = self.make_company()
        self.get(company_id=company.pk)
        self.assertIsNotNone(cache.get(f"view:dashboard:v4:superuser:{company.pk}:all:all"))
        self.assertIsNone(cache.get("view:dashboard:v4:superuser:all:all:all"))

    def test_one_failing_section_is_isolated_and_not_cached(self):
        with patch("apps.license.services.dashboard_summary.build_boe_activity", side_effect=RuntimeError("boom")):
            body = self.get().json()

        self.assertEqual(body["boe_activity"], {"error": "Dashboard section 'boe_activity' could not be loaded"})
        self.assertIn("licence_portfolio", body)
        self.assertIn("financial", body)
        self.assertIsNone(cache.get("view:dashboard:v4:superuser:all:all:all"))


class RoleGatingTests(FlaggedLicenceMixin, TestCase):
    def _user_with_roles(self, *role_codes):
        user = self.make_plain_user()
        for code in role_codes:
            user.groups.add(Group.objects.get_or_create(name=code)[0])
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_a_user_without_roles_gets_no_data_sections(self):
        client = self._user_with_roles()
        body = client.get(reverse("license:dashboard")).json()

        for key in ("licence_portfolio", "financial", "allotment_activity", "boe_activity", "invoice_activity"):
            self.assertNotIn(key, body, f"{key} must be absent, never zero-filled")
        self.assertEqual(body["attention"], [])

    def test_allotment_viewer_sees_only_allotment_activity(self):
        client = self._user_with_roles("ALLOTMENT_VIEWER")
        body = client.get(reverse("license:dashboard")).json()

        self.assertIn("allotment_activity", body)
        self.assertNotIn("licence_portfolio", body)
        self.assertNotIn("financial", body)
        self.assertNotIn("boe_activity", body)
        self.assertNotIn("invoice_activity", body)

    def test_trade_viewer_sees_invoices_but_no_licence_or_boe_zeros(self):
        client = self._user_with_roles("TRADE_VIEWER")
        body = client.get(reverse("license:dashboard")).json()

        self.assertIn("invoice_activity", body)
        self.assertNotIn("licence_portfolio", body)
        self.assertNotIn("boe_activity", body)


class LicenceListLinkTests(FlaggedLicenceMixin, TestCase):
    """The dashboard's links must select exactly the set its counts describe."""

    def setUp(self):
        self.superuser = self.make_superuser()
        self.client_api = APIClient()
        self.client_api.force_authenticate(user=self.superuser)

    def _numbers(self, **params):
        response = self.client_api.get(reverse("license:licenses-list"), params)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        rows = body["results"] if isinstance(body, dict) and "results" in body else body
        return {row["license_number"] for row in rows}

    def test_is_active_filter_matches_the_active_definition(self):
        company = self.make_company()
        active = self.make_flagged(company, _today() + timedelta(days=90), active=True)
        inactive = self.make_flagged(company, _today() + timedelta(days=90), active=False)

        self.assertIn(active.license_number, self._numbers(is_active="true"))
        self.assertNotIn(inactive.license_number, self._numbers(is_active="true"))
        self.assertIn(inactive.license_number, self._numbers(is_active="false"))
        self.assertNotIn(active.license_number, self._numbers(is_active="false"))

    def test_is_expired_filter_is_date_based(self):
        company = self.make_company()
        past = self.make_flagged(company, _today() - timedelta(days=3), expired=False)  # stale flag
        future = self.make_flagged(company, _today() + timedelta(days=30), expired=True)  # stale flag

        expired = self._numbers(is_expired="True")
        self.assertIn(past.license_number, expired)
        self.assertNotIn(future.license_number, expired)
