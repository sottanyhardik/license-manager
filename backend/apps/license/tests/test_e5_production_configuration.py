from django.core.management import call_command
import pytest

from apps.core.models import HeadSIONNormsModel, SionNormClassModel
from apps.license.models import SionPlanningProfile, SionPlanningRule
from apps.license.services.e5_planner_seed import E5ConfigurationConflict, ensure_canonical_e5_configuration
from apps.license.services.sion_planning_execution import SionPlanningExecutionService


@pytest.fixture
def e5_sion(db):
    return SionNormClassModel.objects.create(
        head_norm=HeadSIONNormsModel.objects.create(name="E5 production seed"), norm_class="E5", is_active=True,
    )


@pytest.mark.django_db
def test_e5_seed_creates_active_canonical_configuration_and_generic_resolver(e5_sion):
    result = ensure_canonical_e5_configuration()
    assert result.status == "created"
    assert result.profile.is_active
    assert SionPlanningRule.objects.filter(sion=e5_sion, is_active=True).count() == 9
    assert SionPlanningExecutionService.resolve_configuration(e5_sion).rules


@pytest.mark.django_db
def test_e5_seed_is_idempotent_and_preserves_equivalent_configuration(e5_sion):
    first = ensure_canonical_e5_configuration()
    second = ensure_canonical_e5_configuration()
    assert second.status == "preserved_equivalent"
    assert second.profile.pk == first.profile.pk
    assert SionPlanningProfile.objects.filter(sion=e5_sion).count() == 1
    assert SionPlanningRule.objects.filter(sion=e5_sion).count() == 9


@pytest.mark.django_db
def test_e5_seed_reports_divergent_existing_configuration_without_overwrite(e5_sion):
    profile = ensure_canonical_e5_configuration().profile
    profile.config = {"different": True}
    profile.save(update_fields=["config"])
    with pytest.raises(E5ConfigurationConflict, match="differ"):
        ensure_canonical_e5_configuration()
    assert SionPlanningProfile.objects.get(pk=profile.pk).config == {"different": True}


@pytest.mark.django_db
def test_e5_management_seed_uses_guarded_path(e5_sion, capsys):
    call_command("migrate_sion_planners_to_db", "--sion", "E5", "--apply")
    assert "created" in capsys.readouterr().out
