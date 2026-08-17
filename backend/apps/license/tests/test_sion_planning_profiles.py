from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.models import HeadSIONNormsModel, SionNormClassModel
from apps.license.models import (
    SionPlanningAction, SionPlanningOutputMapping, SionPlanningProfile,
    SionPlanningRun,
)
from apps.license.services.sion_planning_profile import SionPlanningProfileService

pytestmark = pytest.mark.django_db


@pytest.fixture
def profile():
    head = HeadSIONNormsModel.objects.create(name="Configured planner")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class="CFG1", is_active=True)
    value = SionPlanningProfile.objects.create(
        sion=sion, stable_key="CFG1:PROFILE", config={"allocation": {"mode": "WATERFALL"}},
    )
    SionPlanningAction.objects.create(
        profile=value, stable_key="CFG1:ACTION:001", action_type="ALLOCATE",
        priority=1, config={"mode": "SEQUENTIAL_WATERFALL"},
    )
    return value


def test_profile_activation_is_unique_and_snapshot_is_json_safe(profile):
    active = SionPlanningProfileService.activate(profile)
    assert active.is_active
    snapshot = SionPlanningProfileService.snapshot(active)
    assert snapshot["actions"][0]["type"] == "ALLOCATE"
    assert snapshot["profile"]["uid"] == str(active.uid)

    replacement = SionPlanningProfile.objects.create(
        sion=profile.sion, stable_key="CFG1:PROFILE:V2", version=2,
    )
    SionPlanningAction.objects.create(
        profile=replacement, stable_key="CFG1:ACTION:V2:001", action_type="ROUND",
        priority=1, config={"precision": 3, "rounding": "FLOOR"},
    )
    SionPlanningProfileService.activate(replacement)
    profile.refresh_from_db()
    assert not profile.is_active


def test_action_priority_and_stable_keys_are_database_protected(profile):
    with pytest.raises(IntegrityError), transaction.atomic():
        SionPlanningAction.objects.create(
            profile=profile, stable_key="CFG1:ACTION:002", action_type="PRICE",
            priority=1, config={},
        )


def test_configuration_rejects_unsafe_formula_and_cross_sion_mapping(profile):
    action = SionPlanningAction(
        profile=profile, stable_key="BAD", action_type="PRICE", priority=2,
        config={"formula": {"operation": "PYTHON", "arguments": []}},
    )
    with pytest.raises(ValidationError, match="Unsupported structured formula"):
        action.full_clean()

    action.config = {"formula": {
        "operation": "WEIGHTED_AVERAGE", "numerator": "cif_fc",
        "denominator": "quantity",
    }}
    action.full_clean()

    other = SionNormClassModel.objects.create(
        head_norm=profile.sion.head_norm, norm_class="CFG2", is_active=True,
    )
    other_profile = SionPlanningProfile.objects.create(sion=other, stable_key="CFG2:PROFILE")
    mapping = SionPlanningOutputMapping(
        profile=other_profile, stable_key="CFG2:MAP:001", source_rule=None,
        conversion_factor=Decimal("1.25000000"), unit="kg", config={},
    )
    mapping.full_clean()


def test_run_validates_profile_identity_version_and_lifecycle(profile):
    run = SionPlanningRun(
        profile=profile, sion=profile.sion, profile_version=profile.version,
        config_snapshot=SionPlanningProfileService.snapshot(profile), result_summary={},
        started_at=timezone.now(), completed_at=timezone.now() + timedelta(seconds=1),
        status="COMPLETED",
    )
    run.full_clean()
    run.save()

    run.profile_version += 1
    with pytest.raises(ValidationError, match="Profile version"):
        run.full_clean()


def test_output_mapping_decimal_precision_is_preserved(profile):
    mapping = SionPlanningOutputMapping.objects.create(
        profile=profile, stable_key="CFG1:MAP:001", conversion_factor=Decimal("0.33333333"),
        rate=Decimal("24.00000000"), unit="kg", priority=1,
    )
    mapping.refresh_from_db()
    assert mapping.conversion_factor == Decimal("0.33333333")
    assert mapping.rate == Decimal("24.00000000")
