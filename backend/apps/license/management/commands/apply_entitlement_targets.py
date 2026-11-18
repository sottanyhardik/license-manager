"""Persist owner-approved explicit planning targets for ONE licence's actual usage.

Auto Plan's reconciliation (``planning_usage_reconciliation``) deliberately
never infers a split child from product names: a BOE debit / unlinked
allotment counts toward a split child only through its persisted
``planning_target_item``.  This command lets the owner approve such targets in
bulk for one licence:

* proposals come from the norm's configured product → entitlement mapping
  (``sion_planner_config.entitlement_profiles``, e.g. Sunflower → Olive Oil);
* every proposal is validated with ``validate_explicit_target`` against EVERY
  licence row the BOE header debits (a BOE target is header-level);
* ambiguous / unmapped / illegitimate records are reported and never written;
* records that already carry a valid explicit target are left untouched.

Dry-run by default; ``--apply`` writes inside one transaction and records
every change (before/after) in ``ActivityLog``.  ``--link-boe BOE:ALLOTMENT``
links a BOE to an allotment with the same semantics as the BOE service
(M2M add + ``allotment.is_boe = True``) and a ``ReconciliationLog`` LINK row.

Never touches quantities, CIF, plans or balances directly; balance refresh
follows the existing m2m signals.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.models import ActivityLog, ItemNameModel
from apps.license.models import LicenseDetailsModel
from apps.license.services.entitlement_planning import MAPPED
from apps.license.services.entitlement_planning_service import resolve_entitlement
from apps.license.services.item_usage import eligible_boe_debits_for_license
from apps.license.services.planning_actual_target_mapping import validate_explicit_target
from apps.license.services.sion_planner_config.entitlement_profiles import entitlement_profile

STATUS = "MAPPED_EXPLICIT"
SOURCE = "OWNER_APPROVED_PRODUCT_MAP"
UNMAPPED_STATES = {"INVALID_PERSISTED_TARGET", "UNMAPPED_AMBIGUOUS", "UNMAPPED_NO_TARGET"}


class Command(BaseCommand):
    help = "Dry-run (default) or apply owner-approved planning targets for one licence's BOEs/allotments."

    def add_arguments(self, parser):
        parser.add_argument("--license", required=True, help="Exact licence number.")
        parser.add_argument("--apply", action="store_true", help="Persist. Default is dry-run.")
        parser.add_argument("--link-boe", action="append", default=[], metavar="BOE_NUMBER:ALLOTMENT_ID",
                            help="Link a BOE to an allotment (repeatable).")
        parser.add_argument("--reason", default="Owner-approved entitlement target mapping")

    def handle(self, *args, **opts):
        licence = self._licence(opts["license"])
        norm = self._norm(licence)
        products, targets = self._catalogue(norm)
        plan = self._proposals(licence, products, targets)
        links = [self._link_plan(spec) for spec in opts["link_boe"]]

        for row in plan:
            self.stdout.write(" | ".join(str(row[k]) for k in (
                "kind", "ref", "text", "proposed", "verdict", "current")))
        for link in links:
            self.stdout.write(f"LINK | BOE {link['boe'].bill_of_entry_number} -> allotment {link['allotment'].pk} | {link['verdict']}")
        writable = [r for r in plan if r["verdict"] == "WRITE"]
        self.stdout.write(f"{len(writable)} target(s) to write, {len([r for r in plan if r['verdict'] not in ('WRITE', 'ALREADY_SET')])} skipped.")
        if not opts["apply"]:
            self.stdout.write("Dry-run only. Re-run with --apply to persist.")
            return
        with transaction.atomic():
            for row in writable:
                self._write_target(row, opts["reason"])
            for link in links:
                if link["verdict"] == "LINK":
                    self._write_link(link, opts["reason"])
        self.stdout.write(self.style.SUCCESS(f"Applied {len(writable)} target(s) and "
                                             f"{sum(1 for x in links if x['verdict'] == 'LINK')} link(s)."))

    # -- inputs ---------------------------------------------------------------
    @staticmethod
    def _licence(number):
        matches = list(LicenseDetailsModel.objects.filter(license_number=number)[:2])
        if len(matches) != 1:
            raise CommandError(f"Licence {number!r} must match exactly one record (found {len(matches)}).")
        return matches[0]

    @staticmethod
    def _norm(licence):
        norms = set(licence.export_license.exclude(norm_class__isnull=True)
                    .values_list("norm_class__norm_class", flat=True))
        if len(norms) != 1:
            raise CommandError(f"Licence {licence.license_number} must carry exactly one SION norm (found {sorted(norms)}).")
        return norms.pop()

    @staticmethod
    def _catalogue(norm):
        products, names = [], set()
        for group in entitlement_profile(norm).get("groups", []):
            products.extend(group.get("products", []))
            names.update(p["entitlement"] for p in group.get("products", []))
        if not products:
            raise CommandError(f"No product → entitlement mapping is configured for {norm}.")
        targets = {n: ItemNameModel.objects.get(name=n) for n in names}
        return products, targets

    # -- proposals ------------------------------------------------------------
    def _proposals(self, licence, products, targets):
        rows, seen = [], set()
        keys = list(targets)
        for debit in eligible_boe_debits_for_license(licence).select_related("bill_of_entry", "sr_number"):
            boe = debit.bill_of_entry
            if boe.pk in seen:
                continue
            seen.add(boe.pk)
            status, ent = resolve_entitlement([boe.product_name], products, keys)
            sources = [r.sr_number for r in RowDetails.objects.filter(bill_of_entry=boe, transaction_type="D")
                       .select_related("sr_number")]
            rows.append(self._judge("BOE", boe, boe.bill_of_entry_number, boe.product_name, status, ent, targets, sources))
        allotments = (AllotmentItems.objects.filter(item__license=licence, allotment__bill_of_entry__isnull=True,
                                                    allotment__is_boe=False, is_boe=False)
                      .select_related("allotment", "item"))
        for item in allotments:
            allotment = item.allotment
            if ("A", allotment.pk) in seen:
                continue
            seen.add(("A", allotment.pk))
            status, ent = resolve_entitlement([allotment.item_name], products, keys)
            sources = [x.item for x in allotment.allotment_details.select_related("item")]
            rows.append(self._judge("ALLOTMENT", allotment, allotment.pk, allotment.item_name, status, ent, targets, sources))
        return rows

    @staticmethod
    def _judge(kind, obj, ref, text, status, ent, targets, sources):
        current = f"{obj.planning_mapping_status}/{obj.planning_target_item_id}"
        row = {"kind": kind, "obj": obj, "ref": ref, "text": text, "proposed": ent or status, "current": current,
               "target": targets.get(ent)}
        if obj.planning_target_item_id and obj.planning_mapping_status not in UNMAPPED_STATES:
            row["verdict"] = "ALREADY_SET"
        elif status != MAPPED:
            row["verdict"] = f"SKIP_{status}"
        else:
            try:
                for source in sources:
                    validate_explicit_target(source, row["target"].pk)
                row["verdict"] = "WRITE"
            except ValueError:
                row["verdict"] = "SKIP_NOT_LEGITIMATE_FOR_ALL_ROWS"
        return row

    @staticmethod
    def _link_plan(spec):
        try:
            boe_number, allotment_id = spec.split(":", 1)
            boe = BillOfEntryModel.objects.get(bill_of_entry_number=boe_number.strip())
            allotment = AllotmentModel.objects.get(pk=int(allotment_id))
        except (ValueError, BillOfEntryModel.DoesNotExist, BillOfEntryModel.MultipleObjectsReturned,
                AllotmentModel.DoesNotExist) as exc:
            raise CommandError(f"--link-boe {spec!r}: {exc}") from exc
        if boe.allotment.filter(pk=allotment.pk).exists():
            verdict = "ALREADY_LINKED"
        elif allotment.bill_of_entry.exists():
            verdict = "SKIP_ALLOTMENT_ALREADY_HAS_BOE"
        elif boe.company_id != allotment.company_id:
            verdict = "SKIP_COMPANY_MISMATCH"
        else:
            verdict = "LINK"
        return {"boe": boe, "allotment": allotment, "verdict": verdict}

    # -- writes ---------------------------------------------------------------
    @staticmethod
    def _write_target(row, reason):
        obj = row["obj"]
        before = {"planning_target_item_id": obj.planning_target_item_id,
                  "planning_mapping_status": obj.planning_mapping_status,
                  "planning_mapping_source": obj.planning_mapping_source}
        obj.planning_target_item = row["target"]
        obj.planning_mapping_status = STATUS
        obj.planning_mapping_source = SOURCE
        obj.save(update_fields=["planning_target_item", "planning_mapping_status", "planning_mapping_source"])
        ActivityLog.objects.create(
            username="apply_entitlement_targets", action=ActivityLog.ACTION_UPDATE,
            module="planning-target", resource_id=f"{row['kind']}:{obj.pk}"[:60],
            description=f"{row['kind']} {row['ref']} target -> {row['target'].name}"[:500],
            extra={"before": before, "after": {"planning_target_item_id": row["target"].pk,
                                               "planning_mapping_status": STATUS,
                                               "planning_mapping_source": SOURCE},
                   "text": row["text"], "reason": reason})

    @staticmethod
    def _write_link(link, reason):
        from apps.reconciliation.models import ReconciliationLog

        boe, allotment = link["boe"], link["allotment"]
        before = {"allotment_ids": list(boe.allotment.values_list("id", flat=True)), "allotment_is_boe": allotment.is_boe}
        boe.allotment.add(allotment)
        allotment.is_boe = True
        allotment.save(update_fields=["is_boe"])
        after = {"allotment_ids": list(boe.allotment.values_list("id", flat=True)), "allotment_is_boe": True}
        ReconciliationLog.objects.create(action=ReconciliationLog.ACTION_LINK, bill_of_entry=boe,
                                         before=before, after=after,
                                         reason=f"{reason}: BOE {boe.bill_of_entry_number} ↔ allotment {allotment.pk}")
