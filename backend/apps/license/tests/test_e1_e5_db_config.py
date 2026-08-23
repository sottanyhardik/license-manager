"""Persisted planner profile contract shared by E1, E5, and future SIONs."""
import pytest

from apps.core.models import HeadSIONNormsModel, SionNormClassModel
from apps.license.models import SionPlanningRule
from apps.license.services.sion_planner_config.importer import import_e1_e5_profiles
from apps.license.services.sion_planning_execution import SionPlanningExecutionService


@pytest.mark.django_db
def test_imported_e1_e5_profiles_resolve_through_one_configuration_contract():
    head = HeadSIONNormsModel.objects.create(name="Current planner config")
    sions = [SionNormClassModel.objects.create(head_norm=head, norm_class=code) for code in ("E1", "E5")]
    import_e1_e5_profiles(activate=True)
    for sion in sions:
        SionPlanningRule.objects.filter(sion=sion).update(is_active=True)
        config = SionPlanningExecutionService.resolve_configuration(sion)
        assert config.rules
        assert all(rule.execution_output for rule in config.rules)
