"""sion-classes / item-names master lists must have page-size-independent query counts."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.core.models import (
    HeadSIONNormsModel, ItemNameModel, SIONExportModel, SIONImportModel,
    SionNormClassModel, SionNormCondition, SionNormNote,
)


class MastersQueryCountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(username="m_admin", password="x", email="m@example.com")
        cls.head = HeadSIONNormsModel.objects.create(name="Head QC")
        cls.n = 0

    def _norms(self, count):
        out = []
        for _ in range(count):
            type(self).n += 1
            norm = SionNormClassModel.objects.create(
                norm_class=f"Q{self.n:03d}", head_norm=self.head, description="d", is_active=True)
            SIONExportModel.objects.create(norm_class=norm, description="e", quantity=1)
            SIONImportModel.objects.create(norm_class=norm, serial_number=1, description="i", quantity=1)
            SionNormNote.objects.create(sion_norm=norm, note_text="n", display_order=1)
            SionNormCondition.objects.create(sion_norm=norm, condition_text="c", display_order=1)
            out.append(norm)
        return out

    def _items(self, norms, count):
        for i in range(count):
            item = ItemNameModel.objects.create(name=f"QC Item {ItemNameModel.objects.count()}", sion_norm_class=norms[0])
            item.norms.set(norms)

    def _count(self, url):
        client = APIClient()
        client.force_authenticate(self.user)
        with CaptureQueriesContext(connection) as ctx:
            resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        return resp.json()["results"], len(ctx)

    def test_sion_classes_constant(self):
        self._norms(2)
        _, small = self._count("/api/masters/sion-classes/?page_size=50")
        self._norms(8)
        rows, large = self._count("/api/masters/sion-classes/?page_size=50")
        self.assertGreaterEqual(len(rows), 10)
        self.assertLessEqual(large, small + 1, f"N+1 regression: {small} -> {large}")

    def test_item_names_constant_and_norm_details_sorted(self):
        norms = self._norms(3)
        self._items(norms, 2)
        _, small = self._count("/api/masters/item-names/?page_size=50")
        self._items(norms, 8)
        rows, large = self._count("/api/masters/item-names/?page_size=50")
        self.assertGreaterEqual(len(rows), 10)
        self.assertLessEqual(large, small + 1, f"N+1 regression: {small} -> {large}")
        expected = ", ".join(sorted(n.norm_class for n in norms))
        mine = [r for r in rows if r["name"].startswith("QC Item")]
        self.assertEqual(len(mine), 10)
        self.assertTrue(all(r["norm_details"] == expected for r in mine))
