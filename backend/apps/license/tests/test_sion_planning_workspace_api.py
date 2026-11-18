"""Read-only /planning workspace endpoints: norm-summary and norm-configuration."""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import ActivityLog, HeadSIONNormsModel, SionNormClassModel
from apps.license.models import SionPlanningRule

pytestmark = pytest.mark.django_db

EXPR = {"operator": "AND", "conditions": [{"field": "HSN", "comparator": "STARTS_WITH", "value": "1701"}]}


def _client(role="LICENSE_MANAGER", username="ws-user"):
    user = get_user_model().objects.create_user(username=username)
    if role:
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.add(group)
    client = APIClient()
    client.force_authenticate(user)
    return client, user


@pytest.fixture
def norms():
    head = HeadSIONNormsModel.objects.create(name="Workspace")
    active = SionNormClassModel.objects.create(head_norm=head, norm_class="W1", is_active=True)
    unconfigured = SionNormClassModel.objects.create(head_norm=head, norm_class="W9", is_active=False)
    e126 = SionNormClassModel.objects.get_or_create(norm_class="E126", defaults={"head_norm": head, "is_active": False})[0]
    v1 = SionPlanningRule.objects.create(
        sion=active, name="Sugar", unit="kg", max_unit_price=Decimal("2.50"), priority=1,
        expression=EXPR, stable_key="W1:RULE:001", version=1, is_active=False,
    )
    v2 = SionPlanningRule.objects.create(
        sion=active, name="Sugar v2", unit="kg", max_unit_price=Decimal("2.60"), priority=1,
        expression=EXPR, stable_key="W1:RULE:001", version=2, is_active=True,
    )
    return active, unconfigured, e126, v1, v2


def test_norm_summary_lists_active_and_configured_norms_only(norms):
    active, unconfigured, e126, *_ = norms
    client, _ = _client()
    response = client.get("/api/sion-planning-rules/norm-summary/")
    assert response.status_code == 200
    by_norm = {row["norm_class"]: row for row in response.json()}
    assert "W9" not in by_norm
    assert by_norm["W1"]["active_rule_count"] == 1
    assert by_norm["W1"]["rule_version_count"] == 2
    assert by_norm["W1"]["max_rule_version"] == 2
    # A rule without an explicit split strategy is never counted as a split.
    assert by_norm["W1"]["split_rule_count"] == 0
    assert by_norm["W1"]["profile_split_count"] == 0
    # E126 is inactive here but carries the registry split + entitlement profile.
    assert by_norm["E126"]["is_active"] is False
    assert by_norm["E126"]["registry_split_count"] == 1
    assert by_norm["E126"]["has_entitlement_profile"] is True


def test_norm_configuration_reads_actual_e126_split_and_mapping(norms):
    e126 = norms[2]
    client, _ = _client()
    data = client.get("/api/sion-planning-rules/norm-configuration/", {"sion": e126.pk}).json()
    split = [a for a in data["registry"]["actions"] if a["action_type"] == "SPLIT"]
    assert split == [{
        "stable_key": "E126:ACTION:002:SPLIT", "priority": 2, "action_type": "SPLIT",
        "config": {"source_output": "PKO_OLIVE_SPLIT", "basis": "RECORD_AVAILABLE_QUANTITY",
                   "targets": {"PKO": "0.5", "OLIVE": "0.5"}},
    }]
    group = next(g for g in data["entitlement_profile"]["groups"] if g["key"] == "VEGETABLE_OIL")
    assert {p["name"]: p["entitlement"] for p in group["products"]} == {
        "Sunflower Oil": "OLIVE OIL", "Olive Oil": "OLIVE OIL", "PKO": "PALM KERNEL OIL",
    }


def test_norm_configuration_returns_every_rule_version_and_audit(norms):
    active, *_ = norms
    client, user = _client()
    ActivityLog.objects.create(
        user=user, username=user.username, action=ActivityLog.ACTION_UPDATE, module="SION_PLANNING",
        description="RULE_UPDATED", extra={"event": "RULE_UPDATED", "sion_id": active.pk, "rule_id": 5, "rule_version": 2},
    )
    ActivityLog.objects.create(
        user=user, username=user.username, action=ActivityLog.ACTION_UPDATE, module="SION_PLANNING",
        description="RULE_UPDATED", extra={"event": "RULE_UPDATED", "sion_id": active.pk + 999},
    )
    data = client.get("/api/sion-planning-rules/norm-configuration/", {"sion": active.pk}).json()
    assert [(r["version"], r["is_active"]) for r in data["rule_versions"]] == [(2, True), (1, False)]
    assert data["registry"] is None and data["entitlement_profile"] is None
    assert [(a["event"], a["rule_version"]) for a in data["audit"]] == [("RULE_UPDATED", 2)]


def test_norm_configuration_validates_sion_param(norms):
    client, _ = _client()
    assert client.get("/api/sion-planning-rules/norm-configuration/").status_code == 400
    assert client.get("/api/sion-planning-rules/norm-configuration/", {"sion": 987654}).status_code == 404


def test_workspace_endpoints_keep_licence_permission(norms):
    client, _ = _client(role=None, username="no-role")
    assert client.get("/api/sion-planning-rules/norm-summary/").status_code == 403
    viewer, _ = _client(role="LICENSE_VIEWER", username="viewer")
    assert viewer.get("/api/sion-planning-rules/norm-summary/").status_code == 200
    # Read-only users still cannot write rules.
    assert viewer.post("/api/sion-planning-rules/", {}, format="json").status_code == 403


def test_rule_list_exposes_read_only_stable_key(norms):
    active, *_ = norms
    client, _ = _client()
    rows = client.get("/api/sion-planning-rules/", {"sion": active.pk, "is_active": True}).json()
    rows = rows.get("results", rows)
    assert rows[0]["stable_key"] == "W1:RULE:001"
