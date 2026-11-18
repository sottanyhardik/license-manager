"""`/api/bill-of-entries/?allotment=<id>` — additive read-only list filter used by
the allotment workspace's BOE tab. BOE permissions are unchanged."""
from django.test import TestCase, override_settings

from apps.bill_of_entry.models import BillOfEntryModel
from apps.bill_of_entry.tests.test_boe_api_contract import BOE_URL, LOCMEM_CACHES, BoeApiFixtureMixin


@override_settings(CACHES=LOCMEM_CACHES)
class BoeAllotmentFilterTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.company = self.make_company()
        self.allotment = self.make_allotment(self.company)
        self.other = self.make_allotment(self.company, item_name="Other")
        self.linked = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number="LINKED1")
        self.linked.allotment.add(self.allotment, self.other)
        self.unlinked = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number="NOTLINKED")
        self.only_other = BillOfEntryModel.objects.create(company=self.company, bill_of_entry_number="OTHER1")
        self.only_other.allotment.add(self.other)

    def _numbers(self, response):
        rows = response.data.get("results", response.data)
        return sorted(row["bill_of_entry_number"] for row in rows)

    def test_filters_to_boes_linked_to_the_allotment_once_each(self):
        client = self.client_for(self.make_role_user("BOE_VIEWER"))
        response = client.get(BOE_URL, {"allotment": self.allotment.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._numbers(response), ["LINKED1"])
        response = client.get(BOE_URL, {"allotment": self.other.pk})
        self.assertEqual(self._numbers(response), ["LINKED1", "OTHER1"])

    def test_boe_permission_still_applies(self):
        client = self.client_for(self.make_role_user("ALLOTMENT_VIEWER"), raise_request_exception=False)
        self.assertEqual(client.get(BOE_URL, {"allotment": self.allotment.pk}).status_code, 403)
