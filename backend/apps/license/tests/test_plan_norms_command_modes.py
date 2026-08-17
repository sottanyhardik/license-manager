from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.core.models import HeadSIONNormsModel, SionNormClassModel


class PlanNormsCommandModeTests(TestCase):
    def setUp(self):
        head = HeadSIONNormsModel.objects.create(name="CLI canonical service")
        self.sion = SionNormClassModel.objects.create(head_norm=head, norm_class="E1")
        self.result = {
            "summary": {"rules": 2, "eligible_licenses": 3, "matched_items": 4},
            "planned_licenses": 2,
            "already_planned": 1,
            "shortages": 0,
        }

    @patch("apps.license.management.commands.plan_norms.SionPlanningExecutionService.plan_sion")
    def test_positional_default_is_new_and_persists(self, plan_sion):
        plan_sion.return_value = self.result
        out = StringIO()

        call_command("plan_norms", "E1", stdout=out)

        plan_sion.assert_called_once_with(
            self.sion, license_ids=None, persist=True, mode="NEW",
        )
        self.assertIn("Mode                : NEW", out.getvalue())

    @patch("apps.license.management.commands.plan_norms.SionPlanningExecutionService.plan_sion")
    def test_sion_all_uses_same_service_in_all_mode(self, plan_sion):
        plan_sion.return_value = self.result
        out = StringIO()

        call_command("plan_norms", "--sion", "E1", "--all", stdout=out)

        plan_sion.assert_called_once_with(
            self.sion, license_ids=None, persist=True, mode="ALL",
        )
        self.assertIn("Mode                : FORCE ALL", out.getvalue())

    @patch("apps.license.management.commands.plan_norms.SionPlanningExecutionService.plan_sion")
    def test_explicit_new_dry_run_uses_canonical_preview(self, plan_sion):
        plan_sion.return_value = self.result

        call_command("plan_norms", "--sion", "E1", "--new", "--dry-run")

        plan_sion.assert_called_once_with(
            self.sion, license_ids=None, persist=False, mode="NEW",
        )

    def test_unknown_sion_is_rejected(self):
        with self.assertRaisesMessage(CommandError, "Unknown SION"):
            call_command("plan_norms", "--sion", "UNKNOWN")

    def test_conflicting_positional_and_option_are_rejected(self):
        with self.assertRaisesMessage(CommandError, "Conflicting SION values"):
            call_command("plan_norms", "E1", "--sion", "E5")
