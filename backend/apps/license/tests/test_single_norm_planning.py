"""Single/multi-SION selection contracts for the canonical planner."""
import pytest

from apps.license.services.sion_planning_execution import normalize_plan_mode


@pytest.mark.parametrize(("supplied", "expected"), [(None, "NEW"), ("NEW", "NEW"), ("ALL", "ALL")])
def test_execution_mode_is_shared_by_single_and_multi_sion_callers(supplied, expected):
    assert normalize_plan_mode(supplied) == expected


def test_execution_mode_cannot_silently_become_force_all():
    with pytest.raises(ValueError):
        normalize_plan_mode("FORCE_ALL")
