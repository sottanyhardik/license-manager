"""
Characterization tests (WS4): pin the CURRENT HTTP contract of
`/api/bill-of-entries/` -- status codes, response keys, the role matrix and
the custom actions -- so later work (WS5 / owner decisions) changes it only
deliberately.

These tests assert what the code does TODAY. Where today's behaviour is a
known gap awaiting an owner decision, the assertion is marked with
"# CURRENT BEHAVIOUR — owner decision pending: <escalation>" so the one
assertion to flip is easy to find. No production code is changed here.
"""
import uuid
from decimal import Decimal

from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.bill_of_entry.tests.test_boe_hide_service import BoeHideServiceFixtureMixin
from apps.core.models import PortModel

BOE_URL = "/api/bill-of-entries/"

# Isolate DRF throttle counters from the shared Redis cache.
LOCMEM_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "boe-ws4-characterization",
    }
}

# Exact serializer field set returned by create/update/retrieve today
# (`BillOfEntrySerializer.Meta.fields`; `allotments` is added only when the
# BOE has linked allotments).
#
# CURRENT BEHAVIOUR: the dotted read-only display fields `port_name`
# (`port.name`) and `planning_target_item_name` (`planning_target_item.name`)
# are OMITTED from the payload (DRF SkipField) when the FK is null, rather
# than being sent as null. `company_name` behaves the same way.
NULL_FK_OMITTED_KEYS = {"port_name", "planning_target_item_name"}
BOE_RESPONSE_KEYS = {
    "id", "company", "company_name", "bill_of_entry_number", "bill_of_entry_date",
    "port", "port_name", "allotment", "exchange_rate", "product_name", "invoice_no",
    "invoice_date", "is_fetch", "boe_pdf_copy", "failed", "appraisement", "ooc_date",
    "cha", "comments", "planning_target_item", "planning_target_item_name",
    "item_details", "total_inr", "total_fc", "total_quantity", "licenses",
    "unit_price", "created_on", "modified_on", "created_by", "modified_by",
}
BOE_RESPONSE_KEYS_NO_PORT_NO_PLAN = BOE_RESPONSE_KEYS - NULL_FK_OMITTED_KEYS
BOE_RESPONSE_KEYS_NO_PLAN = BOE_RESPONSE_KEYS - {"planning_target_item_name"}

ROW_RESPONSE_KEYS = {
    "id", "sr_number", "cif_inr", "cif_fc", "qty", "is_frozen", "is_dispute",
    "license_number", "license_id", "item_description", "hs_code",
    "item_serial_number", "condition_type", "purchase_status", "source_row_id",
    "authoritative_available_cif",
}


def boe_detail_url(boe_id, suffix=""):
    return f"{BOE_URL}{boe_id}/{suffix}"


class BoeApiFixtureMixin(BoeHideServiceFixtureMixin):
    """API-level helpers on top of the hide-service model fixtures."""

    def make_port(self):
        return PortModel.objects.create(code=str(uuid.uuid4().int)[:6], name="Test Port")

    def make_role_user(self, *roles, superuser=False):
        user = self.make_user("boe-" + ("-".join(roles).lower() or "noroles"))
        if superuser:
            user.is_superuser = True
            user.save(update_fields=["is_superuser"])
        for role in roles:
            group, _ = Group.objects.get_or_create(name=role)
            user.groups.add(group)
        return user

    def client_for(self, user, raise_request_exception=True):
        client = APIClient(raise_request_exception=raise_request_exception)
        client.force_authenticate(user=user)
        return client

    def make_allotment(self, company, item=None, cif_fc=Decimal("2000.00"), item_name="Test Allotment"):
        allotment = AllotmentModel.objects.create(
            company=company,
            item_name=item_name,
            exchange_rate=Decimal("84.500000"),
            required_quantity=Decimal("10.00"),
        )
        if item is not None:
            AllotmentItems.objects.create(
                item=item,
                allotment=allotment,
                cif_fc=cif_fc,
                cif_inr=cif_fc * Decimal("84.5"),
                qty=Decimal("10.000"),
            )
        return allotment

    def row_payload(self, item, cif_fc=Decimal("100.00"), qty=Decimal("10.000"), row_id=None):
        payload = {
            "sr_number": item.id,
            "cif_fc": str(cif_fc),
            "cif_inr": str((cif_fc * Decimal("84.5")).quantize(Decimal("0.01"))),
            "qty": str(qty),
        }
        if row_id is not None:
            payload["id"] = row_id
        return payload


@override_settings(CACHES=LOCMEM_CACHES)
class BoeCrudContractTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.manager = self.make_role_user("BOE_MANAGER")
        self.client = self.client_for(self.manager)
        self.company = self.make_company()
        self.port = self.make_port()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)

    def test_create_returns_201_with_exact_serializer_keys(self):
        response = self.client.post(BOE_URL, {
            "bill_of_entry_number": "7001001",
            "bill_of_entry_date": "2026-01-15",
            "port": self.port.id,
            "company": self.company.id,
            "exchange_rate": "84.5000",
            "item_details": [self.row_payload(self.item)],
        }, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(set(response.data.keys()), BOE_RESPONSE_KEYS_NO_PLAN)
        self.assertEqual(len(response.data["item_details"]), 1)
        # CURRENT BEHAVIOUR: row `hs_code` (sr_number.hs_code.hs_code) is
        # omitted, not null, when the import item has no HS code.
        self.assertEqual(set(response.data["item_details"][0].keys()), ROW_RESPONSE_KEYS - {"hs_code"})
        self.assertEqual(response.data["created_by"], self.manager.id)
        self.assertEqual(RowDetails.objects.filter(bill_of_entry_id=response.data["id"]).count(), 1)

    def test_partial_update_returns_200_with_exact_serializer_keys(self):
        boe = self.make_boe(self.company)
        response = self.client.patch(boe_detail_url(boe.id), {"comments": "pinned"}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(set(response.data.keys()), BOE_RESPONSE_KEYS_NO_PORT_NO_PLAN)
        self.assertEqual(response.data["comments"], "pinned")
        self.assertEqual(response.data["modified_by"], self.manager.id)

    def test_response_adds_allotments_key_only_when_linked(self):
        allotment = self.make_allotment(self.company)
        boe = self.make_boe(self.company)
        response = self.client.patch(boe_detail_url(boe.id), {"allotment": [allotment.id]}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(set(response.data.keys()), BOE_RESPONSE_KEYS_NO_PORT_NO_PLAN | {"allotments"})
        self.assertEqual(
            set(response.data["allotments"][0].keys()),
            {"id", "item_name", "invoice", "required_quantity", "estimated_arrival_date", "company"},
        )

    def test_delete_uninvoiced_boe_returns_204(self):
        boe = self.make_boe(self.company)
        response = self.client.delete(boe_detail_url(boe.id))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(BillOfEntryModel.objects.filter(id=boe.id).exists())

    def test_response_includes_display_keys_when_fks_set(self):
        from apps.core.models import ItemNameModel

        item_name = ItemNameModel.objects.create(name=f"Plan Target {uuid.uuid4().hex[:6]}")
        boe = self.make_boe(self.company)
        BillOfEntryModel.objects.filter(id=boe.id).update(port=self.port, planning_target_item=item_name)

        response = self.client.get(boe_detail_url(boe.id))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(BOE_RESPONSE_KEYS <= set(response.data.keys()))
        self.assertEqual(response.data["port_name"], "Test Port")
        self.assertEqual(response.data["planning_target_item_name"], item_name.name)

    def test_patch_planning_target_item_is_not_persisted(self):
        """CURRENT BEHAVIOUR (bug found by WS4, not in the escalation list):
        `BillOfEntrySerializer.update` pops `planning_target_item` and only
        derives `planning_mapping_status/source` from it -- it never assigns
        the FK itself. So a PATCH reports MAPPED_EXPLICIT while the stored
        target stays NULL. Pinned so a fix is a deliberate, visible change."""
        from apps.core.models import ItemNameModel

        item_name = ItemNameModel.objects.create(name=f"Plan Target {uuid.uuid4().hex[:6]}")
        boe = self.make_boe(self.company)

        response = self.client.patch(
            boe_detail_url(boe.id), {"planning_target_item": item_name.id}, format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        boe.refresh_from_db()
        self.assertIsNone(boe.planning_target_item_id)
        self.assertEqual(boe.planning_mapping_status, "MAPPED_EXPLICIT")
        self.assertEqual(boe.planning_mapping_source, "USER_SELECTED")
        self.assertIsNone(response.data["planning_target_item"])
        self.assertNotIn("planning_target_item_name", response.data)

    def test_delete_invoiced_boe_is_404_unless_is_invoice_all(self):
        boe = self.make_boe(self.company, invoice_no="INV-1")

        # The default `is_invoice=false` queryset filter hides invoiced BOEs
        # from destroy (and list), so DELETE answers 404.
        self.assertEqual(self.client.delete(boe_detail_url(boe.id)).status_code, 404)
        self.assertTrue(BillOfEntryModel.objects.filter(id=boe.id).exists())

        # ...but retrieve / update / partial_update return from get_queryset
        # BEFORE the is_invoice filter, so the same invoiced BOE is readable
        # and PATCHable without ?is_invoice=all (asymmetry pinned as-is).
        self.assertEqual(self.client.get(boe_detail_url(boe.id)).status_code, 200)
        self.assertEqual(
            self.client.patch(boe_detail_url(boe.id), {"comments": "x"}, format="json").status_code, 200,
        )

        response = self.client.delete(boe_detail_url(boe.id) + "?is_invoice=all")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(BillOfEntryModel.objects.filter(id=boe.id).exists())


@override_settings(CACHES=LOCMEM_CACHES)
class BoeRoleMatrixTests(BoeApiFixtureMixin, TestCase):
    """BOE_MANAGER writes; BOE_VIEWER / TL_GENERATE / ACCOUNT_ACCESS read
    only; update-invoice-no is gated by `AccountAccessPermission`."""

    READ_ONLY_ROLES = ("BOE_VIEWER", "TL_GENERATE", "ACCOUNT_ACCESS")

    def setUp(self):
        self.company = self.make_company()

    def _create_payload(self):
        return {
            "bill_of_entry_number": str(uuid.uuid4().int)[:9],
            "bill_of_entry_date": "2026-02-01",
            "company": self.company.id,
        }

    def test_manager_can_read_and_write(self):
        client = self.client_for(self.make_role_user("BOE_MANAGER"))
        boe = self.make_boe(self.company)

        self.assertEqual(client.get(BOE_URL).status_code, 200)
        self.assertEqual(client.get(boe_detail_url(boe.id)).status_code, 200)
        self.assertEqual(client.post(BOE_URL, self._create_payload(), format="json").status_code, 201)
        self.assertEqual(client.patch(boe_detail_url(boe.id), {"comments": "m"}, format="json").status_code, 200)
        self.assertEqual(client.delete(boe_detail_url(boe.id)).status_code, 204)

    def test_read_only_roles_can_read_but_not_write(self):
        for role in self.READ_ONLY_ROLES:
            with self.subTest(role=role):
                client = self.client_for(self.make_role_user(role))
                boe = self.make_boe(self.company)

                self.assertEqual(client.get(BOE_URL).status_code, 200)
                self.assertEqual(client.get(boe_detail_url(boe.id)).status_code, 200)
                self.assertEqual(client.post(BOE_URL, self._create_payload(), format="json").status_code, 403)
                self.assertEqual(
                    client.patch(boe_detail_url(boe.id), {"comments": "x"}, format="json").status_code, 403,
                )
                self.assertEqual(client.delete(boe_detail_url(boe.id)).status_code, 403)
                self.assertEqual(client.post(boe_detail_url(boe.id, "resolve-dispute/")).status_code, 403)
                self.assertEqual(
                    client.post(boe_detail_url(boe.id, "merge/"), {"source_boe_id": boe.id}, format="json").status_code,
                    403,
                )
                self.assertTrue(BillOfEntryModel.objects.filter(id=boe.id).exists())

    def test_user_without_boe_role_is_denied_reads(self):
        client = self.client_for(self.make_role_user("LICENSE_VIEWER"))
        self.assertEqual(client.get(BOE_URL).status_code, 403)

    def test_unauthenticated_is_denied(self):
        self.assertIn(APIClient().get(BOE_URL).status_code, (401, 403))

    def test_update_invoice_no_role_matrix(self):
        expected = {
            "BOE_MANAGER": 200,
            "ACCOUNT_ACCESS": 200,
            # CURRENT BEHAVIOUR — owner decision pending: PERMISSION / API CONTRACT
            # (AccountAccessPermission._roles lets read-only BOE_VIEWER POST
            # update-invoice-no; contradicts docstrings + frontend canEditInvoice).
            "BOE_VIEWER": 200,
            "TL_GENERATE": 403,
            "LICENSE_MANAGER": 403,
        }
        for role, status_code in expected.items():
            with self.subTest(role=role):
                boe = self.make_boe(self.company)
                client = self.client_for(self.make_role_user(role))
                response = client.post(
                    boe_detail_url(boe.id, "update-invoice-no/"), {"invoice_no": f"INV-{role}"}, format="json",
                )
                self.assertEqual(response.status_code, status_code)
                boe.refresh_from_db()
                if status_code == 200:
                    self.assertEqual(response.data, {"id": boe.id, "invoice_no": f"INV-{role}",
                                                     "message": "Invoice number updated"})
                    self.assertEqual(boe.invoice_no, f"INV-{role}")
                else:
                    self.assertEqual(boe.invoice_no, "")

    def test_update_invoice_no_strips_whitespace_and_reaches_invoiced_boe(self):
        boe = self.make_boe(self.company, invoice_no="OLD-1")
        client = self.client_for(self.make_role_user("ACCOUNT_ACCESS"))
        response = client.post(boe_detail_url(boe.id, "update-invoice-no/"), {"invoice_no": "  NEW-2  "}, format="json")

        # Uses get_object_or_404 on ALL BOEs (no is_invoice filter) -> 200.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["invoice_no"], "NEW-2")

    def test_update_invoice_no_unknown_boe_is_404(self):
        client = self.client_for(self.make_role_user("BOE_MANAGER"))
        response = client.post(boe_detail_url(999999999, "update-invoice-no/"), {"invoice_no": "X"}, format="json")
        self.assertEqual(response.status_code, 404)


@override_settings(CACHES=LOCMEM_CACHES)
class BoeFetchAllotmentDetailsContractTests(BoeApiFixtureMixin, TestCase):
    URL = BOE_URL + "fetch-allotment-details/"

    def setUp(self):
        self.client = self.client_for(self.make_role_user("BOE_MANAGER"))
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item_a = self.make_item(self.license, 1)
        self.item_b = self.make_item(self.license, 2)

    def test_returns_header_keys_and_item_keys(self):
        allotment = self.make_allotment(self.company, item=self.item_a, cif_fc=Decimal("1000.00"))
        AllotmentItems.objects.create(
            item=self.item_b, allotment=allotment, cif_fc=Decimal("500.00"),
            cif_inr=Decimal("42250.00"), qty=Decimal("5.000"),
        )

        response = self.client.get(self.URL, {"allotment_id": allotment.id})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            set(response.data.keys()),
            {"exchange_rate", "product_name", "port", "port_name", "company", "company_name", "item_details"},
        )
        self.assertEqual(response.data["company"], self.company.id)
        self.assertEqual(response.data["product_name"], "Test Allotment")
        self.assertEqual(len(response.data["item_details"]), 2)
        self.assertEqual(
            set(response.data["item_details"][0].keys()),
            {"sr_number", "license_number", "item_description", "hs_code", "qty", "cif_fc", "cif_inr"},
        )
        # Floats, not Decimal strings, today.
        self.assertIsInstance(response.data["exchange_rate"], float)

    def test_excludes_items_already_on_the_boe(self):
        allotment = self.make_allotment(self.company, item=self.item_a, cif_fc=Decimal("1000.00"))
        AllotmentItems.objects.create(
            item=self.item_b, allotment=allotment, cif_fc=Decimal("500.00"),
            cif_inr=Decimal("42250.00"), qty=Decimal("5.000"),
        )
        boe = self.make_boe(self.company)
        self.make_debit_row(boe, self.item_a, cif_fc=Decimal("10.00"))

        response = self.client.get(self.URL, {"allotment_id": allotment.id, "boe_id": boe.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["sr_number"] for row in response.data["item_details"]], [self.item_b.id])

    def test_missing_allotment_id_is_400(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "allotment_id is required"})

    def test_unknown_allotment_id_is_500(self):
        # CURRENT BEHAVIOUR — owner decision pending: API CONTRACT
        # (fetch-allotment-details maps every error to 500; proposal: 404 unknown).
        response = self.client.get(self.URL, {"allotment_id": 999999999})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {"error": "Failed to fetch allotment details"})

    def test_non_integer_allotment_id_is_500(self):
        # CURRENT BEHAVIOUR — owner decision pending: API CONTRACT
        # (proposal: 400 for a non-integer id, same {'error'} shape).
        response = self.client.get(self.URL, {"allotment_id": "abc"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {"error": "Failed to fetch allotment details"})


@override_settings(CACHES=LOCMEM_CACHES)
class BoeCustomActionPayloadTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.client = self.client_for(self.make_role_user("BOE_MANAGER"))
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)

    def test_resolve_dispute_payload(self):
        boe = self.make_boe(self.company, number="DISP001")
        row = self.make_debit_row(boe, self.item, cif_fc=Decimal("10.00"))
        RowDetails.objects.filter(id=row.id).update(is_dispute=True)

        response = self.client.post(boe_detail_url(boe.id, "resolve-dispute/"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {
            "success": True, "cleared": 1, "message": "Resolved 1 dispute row(s) on BOE DISP001",
        })
        self.assertFalse(RowDetails.objects.get(id=row.id).is_dispute)

        again = self.client.post(boe_detail_url(boe.id, "resolve-dispute/"))
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.data["cleared"], 0)

    def test_resolve_dispute_unknown_boe_is_404(self):
        self.assertEqual(self.client.post(boe_detail_url(999999999, "resolve-dispute/")).status_code, 404)

    def test_update_product_name_payloads(self):
        boe = self.make_boe(self.company)
        BillOfEntryModel.objects.filter(id=boe.id).update(product_name="")

        no_items = self.client.post(boe_detail_url(boe.id, "update-product-name/"))
        self.assertEqual(no_items.status_code, 400)
        self.assertEqual(no_items.data, {
            "success": False, "product_name": "", "message": "No items found to generate product name",
        })

        self.make_debit_row(boe, self.item, cif_fc=Decimal("10.00"))
        updated = self.client.post(boe_detail_url(boe.id, "update-product-name/"))
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["success"], True)
        self.assertEqual(updated.data["product_name"], self.item.description)
        self.assertEqual(set(updated.data.keys()), {"success", "product_name", "message"})

        skipped = self.client.post(boe_detail_url(boe.id, "update-product-name/"))
        self.assertEqual(skipped.status_code, 200)
        self.assertEqual(skipped.data["success"], False)
        self.assertTrue(skipped.data["message"].startswith("Product name already exists"))

    def test_bulk_update_product_names_payload(self):
        with_items = BillOfEntryModel.objects.create(
            company=self.company, bill_of_entry_number="BULK1", invoice_no=None, product_name="",
        )
        self.make_debit_row(with_items, self.item, cif_fc=Decimal("10.00"))
        BillOfEntryModel.objects.create(
            company=self.company, bill_of_entry_number="BULK2", invoice_no=None, product_name="",
        )
        # Blank-string invoice_no is NOT picked up (filter is invoice_no IS NULL).
        BillOfEntryModel.objects.create(
            company=self.company, bill_of_entry_number="BULK3", invoice_no="", product_name="",
        )

        response = self.client.post(BOE_URL + "bulk-update-product-names/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {
            "success": True, "total": 2, "updated": 1, "skipped": 1,
            "message": "Processed 2 BOEs: 1 updated, 1 skipped (no items found)",
        })
        with_items.refresh_from_db()
        self.assertEqual(with_items.product_name, self.item.description)


@override_settings(CACHES=LOCMEM_CACHES)
class BoeMergeEndpointContractTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.client = self.client_for(self.make_role_user("BOE_MANAGER"))
        self.company = self.make_company()
        self.license = self.make_license(self.company)
        self.item = self.make_item(self.license, 1)

    def test_missing_source_is_400_error_shape(self):
        target = self.make_boe(self.company)
        response = self.client.post(boe_detail_url(target.id, "merge/"), {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "source_boe_id is required"})

    def test_unknown_source_is_404_error_shape(self):
        target = self.make_boe(self.company)
        response = self.client.post(boe_detail_url(target.id, "merge/"), {"source_boe_id": 999999999}, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": "Source BOE with id=999999999 not found"})

    def test_self_merge_is_400_error_shape(self):
        target = self.make_boe(self.company)
        response = self.client.post(boe_detail_url(target.id, "merge/"), {"source_boe_id": target.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Cannot merge a BOE with itself"})

    def test_unknown_target_is_404(self):
        source = self.make_boe(self.company)
        response = self.client.post(boe_detail_url(999999999, "merge/"), {"source_boe_id": source.id}, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(BillOfEntryModel.objects.filter(id=source.id).exists())

    def test_protected_duplicate_is_400_error_shape(self):
        from apps.core.constants import DEC_0
        from apps.reconciliation.services.allocation_service import create_invoice_boe_allocation
        from apps.reconciliation.tests.test_reconciliation import ReconciliationFixtureMixin

        target = self.make_boe(self.company)
        source = self.make_boe(self.company)
        self.make_debit_row(target, self.item, cif_fc=Decimal("100.00"))
        protected = self.make_debit_row(source, self.item, cif_fc=Decimal("100.00"))
        helper = ReconciliationFixtureMixin()
        trade = helper.make_sale_trade(self.company)
        line = helper.make_trade_line(trade, self.item, cif_fc=Decimal("100.00"))
        create_invoice_boe_allocation(
            line, protected, qty=DEC_0, cif_fc=Decimal("100.00"), cif_inr=Decimal("8450.00"), user=None,
        )

        response = self.client.post(boe_detail_url(target.id, "merge/"), {"source_boe_id": source.id}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data.keys()), {"error"})
        self.assertIn(str(protected.id), response.data["error"])
        self.assertTrue(BillOfEntryModel.objects.filter(id=source.id).exists())

    def test_success_payload(self):
        target = self.make_boe(self.company)
        source = self.make_boe(self.company)
        self.make_debit_row(source, self.item, cif_fc=Decimal("100.00"))

        response = self.client.post(boe_detail_url(target.id, "merge/"), {"source_boe_id": source.id}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(set(response.data.keys()), {"success", "message", "boe"})
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "Merged successfully. 1 item(s) moved, 0 skipped (duplicate).")
        self.assertEqual(set(response.data["boe"].keys()), BOE_RESPONSE_KEYS_NO_PORT_NO_PLAN)
        self.assertFalse(BillOfEntryModel.objects.filter(id=source.id).exists())
