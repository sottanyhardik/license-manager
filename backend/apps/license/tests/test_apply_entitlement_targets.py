"""apply_entitlement_targets: dry-run by default, audited, idempotent, never guesses."""
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.allotment.models import AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel
from apps.core.models import ActivityLog, ItemNameModel
from apps.license.tests.test_entitlement_planning_service import World, e126_rules  # noqa: F401  (fixture)
from apps.reconciliation.models import ReconciliationLog


def run(*args):
    out = StringIO()
    call_command("apply_entitlement_targets", *args, stdout=out)
    return out.getvalue()


def _world(sion):
    # Targets are only legitimate for items registered on the norm.
    for name in ("OLIVE OIL", "PALM KERNEL OIL"):
        ItemNameModel.objects.get(name=name).norms.add(sion)
    world = World(sion, "3411000201")
    world.boe("S1", world.veg, "100", "500", "SUNFLOWER SEED OIL")
    world.boe("P1", world.veg, "50", "90", "PALM KERNEL OIL")
    world.boe("X1", world.veg, "10", "30", "PKO / OLIVE OIL")  # ambiguous → never written
    allotment = world.allot(world.veg, "12311", "59092.80", "OLIVE OIL")
    world.boe("B9", world.veg, "12311", "58050.59", "OLIVE OIL")
    return world, allotment


@pytest.mark.django_db
class TestApplyEntitlementTargets:
    def test_dry_run_writes_nothing(self, e126_rules):  # noqa: F811
        sion, *_ = e126_rules
        _world(sion)
        out = run("--license", "3411000201")
        assert "Dry-run only" in out
        assert not BillOfEntryModel.objects.exclude(planning_target_item=None).exists()
        assert not ActivityLog.objects.filter(module="planning-target").exists()

    def test_apply_maps_sunflower_to_olive_pko_apart_and_skips_ambiguous(self, e126_rules):  # noqa: F811
        sion, *_ = e126_rules
        _world(sion)
        run("--license", "3411000201", "--apply")
        olive = ItemNameModel.objects.get(name="OLIVE OIL")
        pko = ItemNameModel.objects.get(name="PALM KERNEL OIL")
        assert BillOfEntryModel.objects.get(bill_of_entry_number="S1").planning_target_item == olive
        assert BillOfEntryModel.objects.get(bill_of_entry_number="P1").planning_target_item == pko
        ambiguous = BillOfEntryModel.objects.get(bill_of_entry_number="X1")
        assert ambiguous.planning_target_item is None
        assert ambiguous.planning_mapping_status == "UNMAPPED_AMBIGUOUS"
        assert ActivityLog.objects.filter(module="planning-target").count() == 4  # 3 BOEs (ambiguous X1 skipped) + 1 allotment

    def test_apply_is_idempotent(self, e126_rules):  # noqa: F811
        sion, *_ = e126_rules
        _world(sion)
        run("--license", "3411000201", "--apply")
        out = run("--license", "3411000201", "--apply")
        assert "Applied 0 target(s)" in out
        assert ActivityLog.objects.filter(module="planning-target").count() == 4

    def test_link_boe_to_allotment_is_audited_once(self, e126_rules):  # noqa: F811
        sion, *_ = e126_rules
        _world_, allotment = _world(sion)
        run("--license", "3411000201", "--link-boe", f"B9:{allotment.pk}", "--apply")
        boe = BillOfEntryModel.objects.get(bill_of_entry_number="B9")
        assert boe.allotment.filter(pk=allotment.pk).exists()
        assert AllotmentModel.objects.get(pk=allotment.pk).is_boe is True
        assert ReconciliationLog.objects.filter(action="LINK", bill_of_entry=boe).count() == 1
        out = run("--license", "3411000201", "--link-boe", f"B9:{allotment.pk}", "--apply")
        assert "ALREADY_LINKED" in out
        assert ReconciliationLog.objects.filter(action="LINK", bill_of_entry=boe).count() == 1

    def test_unknown_licence_is_an_error(self, e126_rules):  # noqa: F811
        with pytest.raises(CommandError):
            run("--license", "NOPE")
