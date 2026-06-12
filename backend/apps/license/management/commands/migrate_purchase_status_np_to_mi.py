"""
Migrate `PurchaseStatus` code from 'NP' to 'MI'.

Background
----------
The `MI` constant in `apps/core/constants.py` was historically set to the
literal string ``"NP"``, while every PurchaseStatus row in production is
keyed as ``code='MI'``. Queries that filter on the constant (e.g. the
item-pivot report's `purchase_status__code__in=[GE, MI, CO]`) therefore
miss every "MITC" licence in the database.

This command resolves the mismatch by consolidating any ``code='NP'``
PurchaseStatus row into the existing ``code='MI'`` row. It is idempotent:

  * If only an ``NP`` row exists  → rename it to ``MI``.
  * If only an ``MI`` row exists  → no-op (reports the situation).
  * If BOTH rows exist             → reassign every licence (and any other
    FK referencing the NP row) to ``MI``, then delete the NP row.

The command runs inside a transaction. Pass ``--dry-run`` to preview the
plan without writing anything.

Usage
-----
    python manage.py migrate_purchase_status_np_to_mi --dry-run
    python manage.py migrate_purchase_status_np_to_mi --confirm
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from apps.core.models import PurchaseStatus
from apps.license.models import LicenseDetailsModel


SRC_CODE = "NP"
DST_CODE = "MI"
DST_LABEL_FALLBACK = "MITC"  # only used if we have to CREATE the dst row


class Command(BaseCommand):
    help = "Consolidate PurchaseStatus code 'NP' into 'MI' (matches the existing master row)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing anything.",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Required to actually apply the migration when not in --dry-run.",
        )

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]
        confirm = opts["confirm"]

        # ── Snapshot current state ─────────────────────────────────────────
        src = PurchaseStatus.objects.filter(code=SRC_CODE).first()
        dst = PurchaseStatus.objects.filter(code=DST_CODE).first()
        src_n = LicenseDetailsModel.objects.filter(purchase_status=src).count() if src else 0
        dst_n = LicenseDetailsModel.objects.filter(purchase_status=dst).count() if dst else 0

        self.stdout.write(self.style.NOTICE("Current state:"))
        self.stdout.write(f"  PurchaseStatus[code={SRC_CODE!r}] = "
                          f"{'EXISTS (label=%r, id=%s, %d licenses)' % (src.label, src.id, src_n) if src else 'MISSING'}")
        self.stdout.write(f"  PurchaseStatus[code={DST_CODE!r}] = "
                          f"{'EXISTS (label=%r, id=%s, %d licenses)' % (dst.label, dst.id, dst_n) if dst else 'MISSING'}")

        # ── Decide what to do ─────────────────────────────────────────────
        if not src and dst:
            self.stdout.write(self.style.SUCCESS(
                f"\nNothing to do — only '{DST_CODE}' exists; '{SRC_CODE}' is already absent."
            ))
            return

        if not src and not dst:
            self.stdout.write(self.style.WARNING(
                f"\nNeither '{SRC_CODE}' nor '{DST_CODE}' exists. Run setup first."
            ))
            return

        if src and not dst:
            plan = f"RENAME PurchaseStatus(code={SRC_CODE!r}) → code={DST_CODE!r}  ({src_n} licenses unaffected)"
        else:
            # Both exist — merge: reassign every licence from src→dst, then delete src.
            plan = (
                f"REASSIGN {src_n} licenses from PurchaseStatus(id={src.id}, code={SRC_CODE!r}) "
                f"→ PurchaseStatus(id={dst.id}, code={DST_CODE!r}); then DELETE the {SRC_CODE!r} row."
            )

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Plan:"))
        self.stdout.write(f"  {plan}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n--dry-run — no changes written."))
            return

        if not confirm:
            self.stdout.write(self.style.ERROR(
                "\nRefusing to write without --confirm. Re-run with --confirm to apply."
            ))
            return

        # ── Apply, atomically ─────────────────────────────────────────────
        with transaction.atomic():
            if src and not dst:
                # Simple rename. The model's `code` is unique so no collision.
                src.code = DST_CODE
                # If the existing row had a placeholder label, give it the
                # canonical MITC label.
                if not src.label or src.label.strip().upper() == SRC_CODE:
                    src.label = DST_LABEL_FALLBACK
                src.save(update_fields=["code", "label"])
                self.stdout.write(self.style.SUCCESS(
                    f"  Renamed PurchaseStatus(id={src.id}) → code={DST_CODE!r}, label={src.label!r}."
                ))
            else:
                # Merge. First reassign every licence, then delete the src.
                updated = LicenseDetailsModel.objects.filter(purchase_status=src).update(purchase_status=dst)
                self.stdout.write(self.style.SUCCESS(
                    f"  Reassigned {updated} licenses from id={src.id} → id={dst.id}."
                ))
                # Safety: any other FK still pointing at src would block delete.
                blockers = self._other_fk_blockers(src)
                if blockers:
                    raise RuntimeError(
                        f"Refusing to delete PurchaseStatus(id={src.id}): still referenced by "
                        f"{blockers}. Re-point those FKs first."
                    )
                src_id = src.id
                src.delete()
                self.stdout.write(self.style.SUCCESS(f"  Deleted PurchaseStatus(id={src_id})."))

        # ── Post-state report ─────────────────────────────────────────────
        post = PurchaseStatus.objects.filter(code__in=(SRC_CODE, DST_CODE)).annotate(
            n=Count("licensedetailsmodel"),
        )
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Post-migration state:"))
        for ps in post:
            self.stdout.write(f"  PurchaseStatus(id={ps.id}, code={ps.code!r}, label={ps.label!r}) — {ps.n} licenses")
        self.stdout.write(self.style.SUCCESS("\nDone."))

    @staticmethod
    def _other_fk_blockers(ps):
        """Count FKs pointing at this PurchaseStatus from any model other than
        LicenseDetailsModel (which we've already reassigned). Returns a dict
        of {model_label: count} when any are found."""
        blockers = {}
        for rel in ps._meta.model._meta.get_fields():
            if not rel.is_relation or not rel.auto_created or rel.concrete:
                continue
            related_model = rel.related_model
            if related_model is LicenseDetailsModel:
                continue
            fk_name = rel.field.name
            count = related_model._default_manager.filter(**{fk_name: ps}).count()
            if count:
                blockers[f"{related_model._meta.label}.{fk_name}"] = count
        return blockers
