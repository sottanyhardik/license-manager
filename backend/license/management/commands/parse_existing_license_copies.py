"""
Management command — parse saved LICENSE COPY PDFs and improve licence data.

Two passes per run:

Pass 1 – PDF parse (licenses that have a LICENSE COPY document attached)
  • Parses each PDF with the existing DFIA parser (digital / scanned / QR).
  • Updates blank fields: license_date, license_expiry_date, file_number,
    notification_number, condition_sheet, port, exporter (company).
  • Fills export-licence financials (cif_fc, cif_inr, fob_fc, fob_inr) when
    the row currently has all-zero values.
  • Creates import-item rows when the licence has NONE yet.
  • Stamps condition_type on existing import items that have a blank
    condition_type, when the parsed condition sheet provides one.

Pass 2 – Norm-to-description rule (ALL licences)
  • Sets export_licence.description based on norm_class when blank:
      E5   → "Biscuits"
      E1   → "Confectionery"
      E126 → "Pickle"
      E132 → "Namkeen"

Usage:
    python manage.py parse_existing_license_copies --list     # show status, no changes
    python manage.py parse_existing_license_copies --dry-run
    python manage.py parse_existing_license_copies --license-number 0311005034
    python manage.py parse_existing_license_copies --norm-desc-only
    python manage.py parse_existing_license_copies --parse-only
    python manage.py parse_existing_license_copies            # live run
"""
from __future__ import annotations

import logging
import traceback
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import CompanyModel, HSCodeModel, PortModel
from license.models import (
    LicenseDetailsModel,
    LicenseDocumentModel,
    LicenseExportItemModel,
    LicenseImportItemsModel,
)
from license.parsers.dfia_pdf import parse_dfia_pdf

# Silence pypdf's "Ignoring wrong pointing object" spam — these are harmless
# structural warnings emitted for many real-world DFIA PDFs.
logging.getLogger("pypdf").setLevel(logging.ERROR)

# ── Norm → product-description rule ─────────────────────────────────────────
NORM_DESCRIPTIONS: dict[str, str] = {
    "E5":  "Biscuits",
    "E1":  "Confectionery",
    "E126": "Pickle",
    "E132": "Namkeen",
}

DEC_0 = Decimal("0")


def _dec(val, default=DEC_0) -> Decimal:
    if val in (None, ""):
        return default
    try:
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return default


class Command(BaseCommand):
    help = "Parse saved LICENSE COPY PDFs to fill missing licence data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--list", action="store_true",
            help="Show licence status (copy exists, blanks, norm) — no changes made",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show what would be changed without saving anything",
        )
        parser.add_argument(
            "--license-number", type=str, default=None,
            help="Restrict to a single licence number",
        )
        parser.add_argument(
            "--norm-desc-only", action="store_true",
            help="Only run Pass 2 (norm→description update, no PDF parsing)",
        )
        parser.add_argument(
            "--parse-only", action="store_true",
            help="Only run Pass 1 (PDF parsing, skip norm→description update)",
        )

    # ── helpers ──────────────────────────────────────────────────────────────

    def _info(self, msg):  self.stdout.write(msg)
    def _ok(self,   msg):  self.stdout.write(self.style.SUCCESS(msg))
    def _warn(self, msg):  self.stdout.write(self.style.WARNING(msg))
    def _err(self,  msg):  self.stdout.write(self.style.ERROR(msg))

    def _handle_list(self, single):
        """Show per-licence status without changing anything."""
        # Licences with a LICENSE COPY document
        docs_qs = (
            LicenseDocumentModel.objects
            .filter(type="LICENSE COPY")
            .select_related("license", "license__exporter", "license__port")
            .exclude(file="")
            .order_by("license__license_number")
        )
        if single:
            docs_qs = docs_qs.filter(license__license_number=single)

        # Licences WITHOUT a copy
        all_lic_ids = set(
            LicenseDetailsModel.objects.values_list("id", flat=True)
        ) if not single else set()
        lic_with_copy = set()

        BLANK = "—"

        self._info(f"\n{'Licence No':<18} {'Has Copy':<9} {'Norm':<8} "
                   f"{'Export Desc':<18} {'File No':<14} "
                   f"{'Condition Sheet':<22} {'Import Items'}")
        self._info("-" * 105)

        count_with = count_without = 0

        for doc in docs_qs.iterator(chunk_size=200):
            lic = doc.license
            lic_with_copy.add(lic.id)
            count_with += 1

            # norm classes from export rows
            norms = list(
                lic.export_license
                   .filter(norm_class__isnull=False)
                   .values_list("norm_class__norm_class", "description")
            )
            norm_str = ", ".join(n for n, _ in norms) or BLANK
            exp_desc = ", ".join((d or BLANK) for _, d in norms) or BLANK

            import_count = lic.import_license.count()
            blanks = []
            if not lic.file_number:       blanks.append("file_no")
            if not lic.condition_sheet:   blanks.append("cond_sheet")
            if not lic.exporter_id:       blanks.append("exporter")
            if not lic.port_id:           blanks.append("port")

            line = (f"{lic.license_number:<18} {'YES':<9} {norm_str:<8} "
                    f"{exp_desc[:17]:<18} {(lic.file_number or BLANK)[:13]:<14} "
                    f"{(lic.condition_sheet or BLANK)[:21]:<22} {import_count}")
            if blanks:
                self._warn(line + f"  [blank: {', '.join(blanks)}]")
            else:
                self._info(line)

        # Licences with NO copy (summary count only unless single)
        if not single:
            no_copy_count = LicenseDetailsModel.objects.exclude(
                id__in=lic_with_copy
            ).count()
            self._info("-" * 105)
            self._info(f"\nTotal with LICENSE COPY  : {count_with}")
            self._info(f"Total WITHOUT copy       : {no_copy_count}")
        else:
            if count_with == 0:
                self._warn(f"No LICENSE COPY document found for {single}")


    # ── main ─────────────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        list_only = options["list"]
        dry = options["dry_run"] or list_only
        single = options["license_number"]
        norm_only = options["norm_desc_only"]
        parse_only = options["parse_only"]

        if list_only:
            return self._handle_list(single)

        if dry:
            self._warn("DRY-RUN — nothing will be saved.")

        stats = {
            "parsed": 0, "parse_fail": 0, "parse_skip": 0,
            "updated": 0, "items_created": 0, "cond_updated": 0,
            "norm_desc_updated": 0,
        }

        # ── Pass 1: PDF parse ────────────────────────────────────────────────
        if not norm_only:
            self._info("\n=== Pass 1: Parsing LICENSE COPY documents ===")

            docs_qs = (
                LicenseDocumentModel.objects
                .filter(type="LICENSE COPY")
                .select_related("license")
                .exclude(file="")
            )
            if single:
                docs_qs = docs_qs.filter(license__license_number=single)

            total = docs_qs.count()
            self._info(f"Found {total} LICENSE COPY document(s) to process.")

            for i, doc in enumerate(docs_qs.iterator(), 1):
                lic = doc.license
                prefix = f"[{i}/{total}] {lic.license_number}"
                try:
                    doc.file.open("rb")
                    parsed = parse_dfia_pdf(doc.file)
                    doc.file.close()
                except Exception as exc:
                    self._err(f"{prefix} — parse failed: {exc}")
                    stats["parse_fail"] += 1
                    continue

                if not parsed.get("license_number"):
                    self._warn(f"{prefix} — parser returned no license_number, skipping")
                    stats["parse_skip"] += 1
                    continue

                stats["parsed"] += 1
                changes = self._apply_parse(lic, parsed, dry, stats, prefix)
                if changes:
                    stats["updated"] += 1
                    self._ok(f"{prefix} — updated: {', '.join(changes)}")
                else:
                    self._info(f"{prefix} — nothing new to update")

        # ── Pass 2: norm → description ───────────────────────────────────────
        if not parse_only:
            self._info("\n=== Pass 2: Setting export-licence descriptions from norm ===")
            lic_qs = LicenseDetailsModel.objects.prefetch_related("export_license__norm_class")
            if single:
                lic_qs = lic_qs.filter(license_number=single)

            for lic in lic_qs.iterator(chunk_size=200):
                for exp in lic.export_license.all():
                    if exp.norm_class_id is None:
                        continue
                    norm_val = (exp.norm_class.norm_class or "").strip()
                    target_desc = NORM_DESCRIPTIONS.get(norm_val)
                    if not target_desc:
                        continue
                    if exp.description and exp.description.strip():
                        continue  # already set
                    self._ok(f"  {lic.license_number} export #{exp.pk}: "
                              f"norm {norm_val} → description = '{target_desc}'")
                    if not dry:
                        exp.description = target_desc
                        exp.save(update_fields=["description"])
                    stats["norm_desc_updated"] += 1

        # ── summary ──────────────────────────────────────────────────────────
        self._info("\n--- Summary ---")
        self._info(f"  PDFs parsed:             {stats['parsed']}")
        self._info(f"  Parse failures:          {stats['parse_fail']}")
        self._info(f"  Skipped (no lic. no.):   {stats['parse_skip']}")
        self._info(f"  Licences updated:        {stats['updated']}")
        self._info(f"  Import items created:    {stats['items_created']}")
        self._info(f"  Condition types stamped: {stats['cond_updated']}")
        self._info(f"  Norm desc. updated:      {stats['norm_desc_updated']}")
        if dry:
            self._warn("DRY-RUN — no changes were saved.")

    # ── apply parsed data to a single licence ────────────────────────────────

    @transaction.atomic
    def _apply_parse(self, lic, parsed, dry, stats, prefix) -> list[str]:
        changes = []

        # Top-level licence fields — only fill if blank/null
        simple_fields = [
            ("license_date",        parsed.get("license_date")),
            ("license_expiry_date", parsed.get("license_expiry_date")),
            ("file_number",         parsed.get("file_number")),
            ("notification_number", parsed.get("notification_number")),
            ("condition_sheet",     parsed.get("condition_sheet")),
        ]
        lic_dirty = []
        for field, value in simple_fields:
            if value and not getattr(lic, field):
                setattr(lic, field, value)
                lic_dirty.append(field)
                changes.append(field)

        # Port — match by code
        if parsed.get("port_code") and not lic.port_id:
            port = PortModel.objects.filter(code__iexact=parsed["port_code"]).first()
            if port:
                lic.port = port
                lic_dirty.append("port")
                changes.append(f"port={parsed['port_code']}")

        # Exporter — match by IEC (or name) if blank
        if not lic.exporter_id:
            iec = (parsed.get("iec") or "").strip()
            name = (parsed.get("company_name") or "").strip()
            company = None
            if iec:
                company = CompanyModel.objects.filter(iec=iec).first()
            if not company and name:
                company = CompanyModel.objects.filter(name__iexact=name).first()
            if company:
                lic.exporter = company
                lic_dirty.append("exporter")
                changes.append(f"exporter={company.name}")

        if lic_dirty and not dry:
            lic.save(update_fields=lic_dirty)

        # Export-licence financials — update when all zeros
        cif_fc = _dec(parsed.get("cif_fc"))
        cif_inr = _dec(parsed.get("cif_inr"))
        fob_fc  = _dec(parsed.get("fob_inr"))   # parser key is "fob_inr"
        for exp in lic.export_license.all():
            exp_dirty = []
            if cif_fc and exp.cif_fc == DEC_0:
                exp.cif_fc = cif_fc; exp_dirty.append("cif_fc")
            if cif_inr and exp.cif_inr == DEC_0:
                exp.cif_inr = cif_inr; exp_dirty.append("cif_inr")
            if fob_fc and exp.fob_inr == DEC_0:
                exp.fob_inr = fob_fc; exp_dirty.append("fob_inr")
            if exp_dirty:
                changes.append(f"export_financials({','.join(exp_dirty)})")
                if not dry:
                    exp.save(update_fields=exp_dirty)

        # Import items — create only if licence has none yet
        parsed_items = parsed.get("items") or []
        existing_count = lic.import_license.count()
        if parsed_items and existing_count == 0:
            for row in parsed_items:
                sr = int(row.get("sr_no") or 0)
                hsn_str = (row.get("hsn") or "").strip()
                hs_obj = HSCodeModel.objects.filter(hs_code=hsn_str).first() if hsn_str else None
                qty = _dec(row.get("quantity"), Decimal("0.000"))
                unit = (row.get("unit") or "KG").upper()[:10]
                desc = (row.get("description") or "")[:255]
                if not dry:
                    imp = LicenseImportItemsModel.objects.create(
                        license=lic,
                        serial_number=sr,
                        hs_code=hs_obj,
                        description=desc,
                        quantity=qty,
                        available_quantity=qty,
                        unit=unit,
                    )
                    # link item name via auto-link (ignore errors)
                    try:
                        from license.utils.item_matcher import auto_link_license_item
                        auto_link_license_item(imp)
                    except Exception:
                        pass
                stats["items_created"] += 1
            changes.append(f"{len(parsed_items)} import items created")

        # Condition types — stamp on existing items where blank.
        # The parser may return a dict {serial: cond} or a list of
        # [{"serial_number": N, "condition": "AU"}, ...] — normalise to dict.
        raw_conds = parsed.get("item_conditions") or {}
        if isinstance(raw_conds, list):
            item_conditions = {}
            for entry in raw_conds:
                if isinstance(entry, dict):
                    k = entry.get("serial_number") or entry.get("serial") or entry.get("sr_no")
                    v = entry.get("condition") or entry.get("condition_type")
                    if k is not None and v:
                        item_conditions[int(k)] = v
                        item_conditions[str(k)] = v
        else:
            item_conditions = {k: v for k, v in raw_conds.items()} if raw_conds else {}

        if item_conditions:
            for imp in lic.import_license.all():
                if imp.condition_type:
                    continue
                cond = item_conditions.get(imp.serial_number) or item_conditions.get(str(imp.serial_number))
                if cond:
                    if not dry:
                        imp.condition_type = cond
                        imp.is_restricted = bool(cond.strip())
                        imp.save(update_fields=["condition_type", "is_restricted"])
                    stats["cond_updated"] += 1
                    changes.append(f"condition_type[{imp.serial_number}]={cond}")

        if dry and changes:
            # Roll back the atomic savepoint
            transaction.set_rollback(True)

        return changes
