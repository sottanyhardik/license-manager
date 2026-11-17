"""
Owner decision D2 — BOE role matrix (positive + negative), exercised through
the real HTTP/permission layer.

BOE_VIEWER is read-only with exactly ONE write exception:
`POST /bill-of-entries/{id}/update-invoice-no/`. ACCOUNT_ACCESS keeps its
documented behaviour (read + update-invoice-no). BOE_MANAGER keeps full BOE
access. TL_GENERATE reads + generates transfer letters. Superuser unchanged.
Licence-hosted hide/restore BOE actions require BOE_MANAGER *and*
LICENSE_MANAGER.

"Allowed" for a side-effecting action is asserted as "not 401/403" (the
permission gate passed); "denied" is asserted as exactly 403 plus no
mutation, since DRF checks permissions before touching the object.
"""
import uuid
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.response import Response

from apps.accounts.permissions import AccountAccessPermission, BillOfEntryPermission
from apps.bill_of_entry.models import BillOfEntryModel
from apps.bill_of_entry.tests.test_boe_api_contract import (
    BOE_URL,
    LOCMEM_CACHES,
    BoeApiFixtureMixin,
    boe_detail_url,
)

DENIED = 403
NO_ROLE = "NO_ROLE"
ALL_ROLES = ("BOE_MANAGER", "BOE_VIEWER", "ACCOUNT_ACCESS", "TL_GENERATE", NO_ROLE)
READ_ROLES = {"BOE_MANAGER", "BOE_VIEWER", "ACCOUNT_ACCESS", "TL_GENERATE"}
MANAGER_ONLY = {"BOE_MANAGER"}
INVOICE_NO_ROLES = {"BOE_MANAGER", "BOE_VIEWER", "ACCOUNT_ACCESS"}
TL_ROLES = {"BOE_MANAGER", "TL_GENERATE"}


@override_settings(CACHES=LOCMEM_CACHES)
class BoePermissionMatrixTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license)
        self.allotment = self.make_allotment(self.company, item=self.item)

    # -- helpers ---------------------------------------------------------
    def user_for(self, role):
        if role == NO_ROLE:
            return self.make_role_user()
        return self.make_role_user(role)

    def client_as(self, role):
        return self.client_for(self.user_for(role), raise_request_exception=False)

    def assert_allowed(self, response, label):
        self.assertNotIn(response.status_code, (401, 403), f"{label}: expected allowed, got {response.status_code}")

    def assert_denied(self, response, label):
        self.assertEqual(response.status_code, DENIED, f"{label}: expected 403, got {response.status_code}")

    def check(self, allowed_roles, label, call):
        """call(client, boe) -> response; runs for every role in ALL_ROLES."""
        for role in ALL_ROLES:
            with self.subTest(role=role, endpoint=label):
                boe = self.make_boe(self.company)
                response = call(self.client_as(role), boe)
                if role in allowed_roles:
                    self.assert_allowed(response, f"{role} {label}")
                else:
                    self.assert_denied(response, f"{role} {label}")

    def create_payload(self):
        return {
            "bill_of_entry_number": str(uuid.uuid4().int)[:9],
            "bill_of_entry_date": "2026-02-01",
            "company": self.company.id,
        }

    # -- reads -----------------------------------------------------------
    def test_list_detail_export_and_fetch_allotment_are_read_roles(self):
        self.check(READ_ROLES, "GET list", lambda c, b: c.get(BOE_URL))
        self.check(READ_ROLES, "GET detail", lambda c, b: c.get(boe_detail_url(b.id), {"is_invoice": "all"}))
        self.check(READ_ROLES, "GET export", lambda c, b: c.get(BOE_URL + "export/"))
        self.check(
            READ_ROLES, "GET fetch-allotment-details",
            lambda c, b: c.get(BOE_URL + "fetch-allotment-details/", {"allotment_id": self.allotment.id}),
        )

    def test_read_roles_get_200_on_list_and_detail(self):
        for role in READ_ROLES:
            with self.subTest(role=role):
                client = self.client_as(role)
                boe = self.make_boe(self.company)
                self.assertEqual(client.get(BOE_URL).status_code, 200)
                self.assertEqual(client.get(boe_detail_url(boe.id)).status_code, 200)

    # -- CRUD writes: BOE_MANAGER only ------------------------------------
    def test_create_is_manager_only(self):
        self.check(MANAGER_ONLY, "POST create", lambda c, b: c.post(BOE_URL, self.create_payload(), format="json"))

    def test_put_patch_delete_are_manager_only(self):
        self.check(
            MANAGER_ONLY, "PATCH",
            lambda c, b: c.patch(boe_detail_url(b.id), {"comments": "x"}, format="json"),
        )
        self.check(
            MANAGER_ONLY, "PUT",
            lambda c, b: c.put(
                boe_detail_url(b.id),
                {**self.create_payload(), "bill_of_entry_number": b.bill_of_entry_number},
                format="json",
            ),
        )
        self.check(MANAGER_ONLY, "DELETE", lambda c, b: c.delete(boe_detail_url(b.id)))

    def test_denied_writes_do_not_mutate(self):
        for role in [r for r in ALL_ROLES if r not in MANAGER_ONLY]:
            with self.subTest(role=role):
                client = self.client_as(role)
                boe = self.make_boe(self.company)
                before = BillOfEntryModel.objects.count()
                self.assert_denied(client.patch(boe_detail_url(boe.id), {"comments": "hacked"}, format="json"), role)
                self.assert_denied(client.delete(boe_detail_url(boe.id)), role)
                self.assert_denied(client.post(BOE_URL, self.create_payload(), format="json"), role)
                boe.refresh_from_db()
                self.assertNotEqual(boe.comments, "hacked")
                self.assertEqual(BillOfEntryModel.objects.count(), before)

    # -- custom BOE write actions: BOE_MANAGER only -----------------------
    def test_custom_write_actions_are_manager_only(self):
        self.check(MANAGER_ONLY, "update-product-name", lambda c, b: c.post(boe_detail_url(b.id, "update-product-name/")))
        self.check(MANAGER_ONLY, "resolve-dispute", lambda c, b: c.post(boe_detail_url(b.id, "resolve-dispute/")))
        self.check(
            MANAGER_ONLY, "merge",
            lambda c, b: c.post(boe_detail_url(b.id, "merge/"), {"source_boe_id": b.id}, format="json"),
        )
        self.check(MANAGER_ONLY, "bulk-update-product-names", lambda c, b: c.post(BOE_URL + "bulk-update-product-names/"))

    def test_parse_pdf_is_manager_only(self):
        # Manager passes the gate and gets the "no file" 400; nothing is parsed/created.
        self.check(MANAGER_ONLY, "parse-pdf", lambda c, b: c.post(BOE_URL + "parse-pdf/", {}, format="multipart"))

    # -- the one viewer write exception -----------------------------------
    def test_update_invoice_no_matrix(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                boe = self.make_boe(self.company)
                response = self.client_as(role).post(
                    boe_detail_url(boe.id, "update-invoice-no/"), {"invoice_no": "INV-D2"}, format="json",
                )
                boe.refresh_from_db()
                if role in INVOICE_NO_ROLES:
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(boe.invoice_no, "INV-D2")
                else:
                    self.assertEqual(response.status_code, DENIED)
                    self.assertEqual(boe.invoice_no, "")

    def test_update_invoice_no_service_value_error_is_400_error_shape(self):
        """D1 view side: a ValueError from the service maps to 400 {'error': msg}."""
        boe = self.make_boe(self.company)
        with mock.patch(
            "apps.bill_of_entry.api.views.boe_service.update_invoice_no",
            side_effect=ValueError("BOE is hidden; use restore instead."),
        ):
            response = self.client_as("BOE_VIEWER").post(
                boe_detail_url(boe.id, "update-invoice-no/"), {"invoice_no": "X"}, format="json",
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "BOE is hidden; use restore instead."})

    # -- transfer letter keeps TL roles -----------------------------------
    def test_generate_transfer_letter_keeps_tl_roles(self):
        with mock.patch(
            "apps.bill_of_entry.api.views.generate_transfer_letter_generic",
            return_value=Response({"ok": True}),
        ):
            self.check(TL_ROLES, "generate-transfer-letter", lambda c, b: c.post(boe_detail_url(b.id, "generate-transfer-letter/")))

    def test_boe_viewer_cannot_generate_transfer_letter(self):
        boe = self.make_boe(self.company)
        with mock.patch(
            "apps.bill_of_entry.api.views.generate_transfer_letter_generic",
            return_value=Response({"ok": True}),
        ) as gen:
            response = self.client_as("BOE_VIEWER").post(boe_detail_url(boe.id, "generate-transfer-letter/"))
        self.assertEqual(response.status_code, 403)
        gen.assert_not_called()

    # -- licence-hosted hide/restore BOE ----------------------------------
    def _licence_hide_actions(self):
        base = f"/api/licenses/{self.license.id}/"
        return {
            "hide-boe": (base + "hide-boe/", {}),
            "restore-boe": (base + "restore-boe/", {}),
            "hide-boe-bulk": (base + "hide-boe-bulk/", {"boe_ids": []}),
            "restore-boe-bulk": (base + "restore-boe-bulk/", {"boe_ids": []}),
        }

    def test_licence_hide_restore_denied_for_every_single_boe_role(self):
        for label, (url, body) in self._licence_hide_actions().items():
            for role in ALL_ROLES:
                with self.subTest(role=role, endpoint=label):
                    self.assert_denied(self.client_as(role).post(url, body, format="json"), f"{role} {label}")
            with self.subTest(role="BOE_VIEWER+LICENSE_MANAGER", endpoint=label):
                client = self.client_for(self.make_role_user("BOE_VIEWER", "LICENSE_MANAGER"))
                self.assert_denied(client.post(url, body, format="json"), label)

    def test_licence_hide_restore_allowed_for_boe_and_licence_manager(self):
        client = self.client_for(
            self.make_role_user("BOE_MANAGER", "LICENSE_MANAGER"), raise_request_exception=False,
        )
        for label, (url, body) in self._licence_hide_actions().items():
            with self.subTest(endpoint=label):
                # Empty body -> 400 "required" after passing the gate; nothing is hidden.
                response = client.post(url, body, format="json")
                self.assert_allowed(response, label)
                self.assertEqual(response.status_code, 400)

    # -- superuser + anonymous --------------------------------------------
    def test_superuser_unchanged(self):
        client = self.client_for(self.make_role_user(superuser=True), raise_request_exception=False)
        boe = self.make_boe(self.company)
        self.assertEqual(client.get(BOE_URL).status_code, 200)
        self.assertEqual(client.patch(boe_detail_url(boe.id), {"comments": "su"}, format="json").status_code, 200)
        self.assertEqual(
            client.post(boe_detail_url(boe.id, "update-invoice-no/"), {"invoice_no": "SU"}, format="json").status_code,
            200,
        )
        self.assertEqual(client.post(BOE_URL + "parse-pdf/", {}, format="multipart").status_code, 400)

    def test_anonymous_denied_everywhere(self):
        from rest_framework.test import APIClient

        boe = self.make_boe(self.company)
        client = APIClient()
        self.assertIn(client.get(BOE_URL).status_code, (401, 403))
        self.assertIn(
            client.post(boe_detail_url(boe.id, "update-invoice-no/"), {"invoice_no": "A"}, format="json").status_code,
            (401, 403),
        )


class AccountAccessPermissionUnitTests(BoeApiFixtureMixin, TestCase):
    """Defence in depth: AccountAccessPermission only grants writes for the
    `update_invoice_no` action, so reusing it elsewhere cannot widen
    viewer/accounts access."""

    def setUp(self):
        self.factory = RequestFactory()

    def _req(self, method, user):
        request = getattr(self.factory, method)("/x/")
        request.user = user
        return request

    def test_write_only_for_update_invoice_no(self):
        perm = AccountAccessPermission()
        for role in ("BOE_VIEWER", "ACCOUNT_ACCESS", "BOE_MANAGER"):
            user = self.make_role_user(role)
            with self.subTest(role=role):
                self.assertTrue(perm.has_permission(self._req("post", user), SimpleNamespace(action="update_invoice_no")))
                self.assertTrue(perm.has_permission(self._req("get", user), SimpleNamespace(action="retrieve")))
                for action in ("merge_boe", "resolve_dispute", "partial_update", "destroy", None):
                    self.assertFalse(perm.has_permission(self._req("post", user), SimpleNamespace(action=action)))

    def test_other_roles_and_anonymous_denied(self):
        perm = AccountAccessPermission()
        view = SimpleNamespace(action="update_invoice_no")
        self.assertFalse(perm.has_permission(self._req("post", self.make_role_user("TL_GENERATE")), view))
        self.assertFalse(perm.has_permission(self._req("post", self.make_role_user()), view))
        self.assertFalse(perm.has_permission(self._req("post", AnonymousUser()), view))

    def test_superuser_bypass_unchanged(self):
        perm = AccountAccessPermission()
        su = self.make_role_user(superuser=True)
        self.assertTrue(perm.has_permission(self._req("delete", su), SimpleNamespace(action="destroy")))

    def test_boe_permission_write_roles_unchanged(self):
        self.assertEqual(BillOfEntryPermission.required_roles_for_write, ["BOE_MANAGER"])
        self.assertEqual(
            BillOfEntryPermission.required_roles_for_read,
            ["BOE_MANAGER", "BOE_VIEWER", "ACCOUNT_ACCESS", "TL_GENERATE"],
        )

