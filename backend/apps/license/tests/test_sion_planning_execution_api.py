"""Request-boundary contracts for the canonical SION planning endpoint."""
import pytest

from apps.license.views.sion_planning_rule import SionPlanRequestSerializer


@pytest.mark.parametrize("mode", ["NEW", "ALL"])
def test_plan_sion_request_accepts_only_canonical_modes(mode):
    serializer = SionPlanRequestSerializer(data={"sion_id": 1, "mode": mode})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.parametrize("mode", ["", "FORCE", "DELETE"])
def test_plan_sion_request_rejects_unsafe_modes(mode):
    serializer = SionPlanRequestSerializer(data={"sion_id": 1, "mode": mode})
    assert not serializer.is_valid()
