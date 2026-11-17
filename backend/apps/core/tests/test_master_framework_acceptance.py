"""Acceptance gate for the generic master framework (``MasterViewSet.create_viewset``).

One contract, proven on structurally different masters through the real API and
database:

* Port            — code + name, delete-protected when a licence references it
* PurchaseStatus  — 2-char code, boolean ``is_active`` filter, ``display_order`` ordering
* SchemeCode      — detail lookup by ``code`` (not pk)
* NotificationNumber — detail lookup by ``code``; real codes contain ``/`` (``025/2023``)

Permissions (``MasterDataPermission``): any authenticated user reads; only a
superuser or ``USER_MANAGER`` writes; anonymous is refused.
"""
from urllib.parse import quote

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import NotificationNumber, PortModel, PurchaseStatus, SchemeCode
from apps.license.models import LicenseDetailsModel

User = get_user_model()
BASE = "/api/masters"


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


@pytest.fixture
def manager(db):
    user = User.objects.create_user(username="master-acceptance-manager", password="x-Acceptance-1")
    user.groups.add(Group.objects.get_or_create(name="USER_MANAGER")[0])
    return _client(user)


@pytest.fixture
def reader(db):
    user = User.objects.create_user(username="master-acceptance-reader", password="x-Acceptance-1")
    user.groups.add(Group.objects.get_or_create(name="LICENSE_VIEWER")[0])
    return _client(user)


@pytest.mark.django_db
class TestPortContract:
    def test_create_edit_delete_persist(self, manager):
        created = manager.post(f"{BASE}/ports/", {"code": "INZZA1", "name": "Acceptance Port"}, format="json")
        assert created.status_code == 201, created.content
        pk = created.json()["id"]
        assert PortModel.objects.get(pk=pk).name == "Acceptance Port"

        edited = manager.patch(f"{BASE}/ports/{pk}/", {"name": "Renamed Port"}, format="json")
        assert edited.status_code == 200, edited.content
        assert PortModel.objects.get(pk=pk).name == "Renamed Port"

        assert manager.delete(f"{BASE}/ports/{pk}/").status_code == 204
        assert not PortModel.objects.filter(pk=pk).exists()

    def test_duplicate_code_is_rejected(self, manager):
        PortModel.objects.create(code="INZZA2", name="First")
        response = manager.post(f"{BASE}/ports/", {"code": "INZZA2", "name": "Second"}, format="json")
        assert response.status_code == 400
        assert PortModel.objects.filter(code="INZZA2").count() == 1

    def test_referenced_port_cannot_be_deleted(self, manager):
        port = PortModel.objects.create(code="INZZA3", name="Used")
        LicenseDetailsModel.objects.create(license_number="0399999001", port=port)
        response = manager.delete(f"{BASE}/ports/{port.pk}/")
        assert response.status_code == 400
        assert PortModel.objects.filter(pk=port.pk).exists()

    def test_search_and_pagination(self, reader):
        for i in range(30):
            PortModel.objects.create(code=f"INQQ{i:02d}", name=f"Acceptance Harbour {i:02d}")
        PortModel.objects.create(code="INXX99", name="Other")

        page1 = reader.get(f"{BASE}/ports/", {"search": "acceptance harbour", "page_size": 25})
        assert page1.status_code == 200
        body = page1.json()
        assert body["count"] == 30
        assert len(body["results"]) == 25
        page2 = reader.get(f"{BASE}/ports/", {"search": "acceptance harbour", "page_size": 25, "page": 2})
        assert len(page2.json()["results"]) == 5


@pytest.mark.django_db
class TestPurchaseStatusContract:
    def test_validation_max_length_and_required(self, manager):
        too_long = manager.post(f"{BASE}/purchase-statuses/", {"code": "ABC", "label": "Too long"}, format="json")
        assert too_long.status_code == 400
        assert "code" in too_long.json()
        missing = manager.post(f"{BASE}/purchase-statuses/", {"code": "QZ"}, format="json")
        assert missing.status_code == 400
        assert not PurchaseStatus.objects.filter(code__in=["ABC", "QZ"]).exists()

    def test_boolean_filter_and_ordering(self, reader):
        PurchaseStatus.objects.create(code="Q1", label="Acceptance B", display_order=902, is_active=True)
        PurchaseStatus.objects.create(code="Q2", label="Acceptance A", display_order=901, is_active=True)
        PurchaseStatus.objects.create(code="Q3", label="Acceptance Off", display_order=900, is_active=False)

        inactive = reader.get(f"{BASE}/purchase-statuses/", {"is_active": "false", "search": "acceptance"})
        assert [row["code"] for row in inactive.json()["results"]] == ["Q3"]

        ordered = reader.get(f"{BASE}/purchase-statuses/", {"search": "acceptance", "ordering": "-display_order"})
        assert [row["code"] for row in ordered.json()["results"]] == ["Q1", "Q2", "Q3"]

    def test_toggle_active_persists(self, manager):
        status = PurchaseStatus.objects.create(code="Q4", label="Toggle", is_active=True)
        response = manager.patch(f"{BASE}/purchase-statuses/{status.pk}/", {"is_active": False}, format="json")
        assert response.status_code == 200
        status.refresh_from_db()
        assert status.is_active is False


@pytest.mark.django_db
class TestCodeKeyedMasters:
    def test_scheme_code_detail_edit_delete_by_code(self, manager):
        SchemeCode.objects.create(code="ZQ", label="Acceptance scheme")
        assert manager.get(f"{BASE}/scheme-codes/ZQ/").json()["label"] == "Acceptance scheme"
        assert manager.patch(f"{BASE}/scheme-codes/ZQ/", {"label": "Renamed"}, format="json").status_code == 200
        assert SchemeCode.objects.get(code="ZQ").label == "Renamed"
        assert manager.delete(f"{BASE}/scheme-codes/ZQ/").status_code == 204
        assert not SchemeCode.objects.filter(code="ZQ").exists()

    def test_notification_number_with_slash_is_addressable(self, manager):
        """Real notification codes look like ``025/2023``; the UI sends them URL-encoded."""
        NotificationNumber.objects.create(code="099/2099", label="Acceptance notification")
        url = f"{BASE}/notification-numbers/{quote('099/2099', safe='')}/"

        detail = manager.get(url)
        assert detail.status_code == 200, detail.content
        assert detail.json()["code"] == "099/2099"

        assert manager.patch(url, {"label": "Renamed"}, format="json").status_code == 200
        assert NotificationNumber.objects.get(code="099/2099").label == "Renamed"

        assert manager.delete(url).status_code == 204
        assert not NotificationNumber.objects.filter(code="099/2099").exists()

    def test_plain_notification_code_still_resolves(self, manager):
        NotificationNumber.objects.create(code="RODZZ", label="Plain")
        assert manager.get(f"{BASE}/notification-numbers/RODZZ/").status_code == 200


@pytest.mark.django_db
class TestMasterPermissions:
    @pytest.mark.parametrize("entity", ["ports", "purchase-statuses", "scheme-codes", "notification-numbers"])
    def test_reader_can_list_but_not_write(self, reader, entity):
        assert reader.get(f"{BASE}/{entity}/").status_code == 200
        response = reader.post(f"{BASE}/{entity}/", {"code": "Q9", "label": "x", "name": "x"}, format="json")
        assert response.status_code == 403

    def test_reader_cannot_edit_or_delete(self, reader):
        port = PortModel.objects.create(code="INZZA4", name="Locked")
        assert reader.patch(f"{BASE}/ports/{port.pk}/", {"name": "x"}, format="json").status_code == 403
        assert reader.delete(f"{BASE}/ports/{port.pk}/").status_code == 403
        assert PortModel.objects.get(pk=port.pk).name == "Locked"

    def test_anonymous_is_refused(self, db):
        assert _client().get(f"{BASE}/ports/").status_code == 401


@pytest.mark.django_db
class TestRecordHistory:
    """`/api/masters/activity-logs/?endpoint=…&changes_only=1` — a record's successful writes only."""

    URL = f"{BASE}/activity-logs/"

    def _log(self, action, endpoint, status=200):
        from apps.core.models import ActivityLog

        return ActivityLog.objects.create(
            username="someone", action=action, module="masters", endpoint=endpoint, method="PATCH", status_code=status,
        )

    def test_changes_for_one_record(self, manager):
        self._log("UPDATE", "/api/masters/ports/5/")
        self._log("DELETE", "/api/masters/ports/5/", status=204)
        self._log("VIEW", "/api/masters/ports/5/")
        self._log("UPDATE", "/api/masters/ports/5/", status=400)
        self._log("UPDATE", "/api/masters/ports/50/")
        self._log("UPDATE", "/api/masters/notification-numbers/025/2023/")

        rows = manager.get(self.URL, {"endpoint": "/api/masters/ports/5/", "changes_only": "1"}).json()
        assert sorted(r["action"] for r in rows) == ["DELETE", "UPDATE"]
        assert all(r["endpoint"] == "/api/masters/ports/5/" for r in rows)

        no_slash = manager.get(self.URL, {"endpoint": "/api/masters/ports/5", "changes_only": "true"}).json()
        assert len(no_slash) == 2

        coded = manager.get(self.URL, {"endpoint": "/api/masters/notification-numbers/025/2023/", "changes_only": "1"}).json()
        assert [r["endpoint"] for r in coded] == ["/api/masters/notification-numbers/025/2023/"]

    def test_without_new_params_behaviour_is_unchanged(self, manager):
        self._log("VIEW", "/api/masters/ports/5/")
        self._log("UPDATE", "/api/masters/ports/5/")
        assert len(manager.get(self.URL).json()) == 2

    def test_history_stays_user_manager_only(self, reader):
        assert reader.get(self.URL, {"endpoint": "/api/masters/ports/5/", "changes_only": "1"}).status_code == 403
