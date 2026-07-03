"""
Hydrate the Master-Data Service DB from a JSON export produced by the
license-manager `export_masters_mds` command.

Idempotent & resumable (ADR-001):
- Business-keyed masters (Company/Port/ItemGroup/HSCode/SchemeCode/
  NotificationNumber/ExchangeRate/SIONNormClass/ItemHead/ItemName): upsert with
  `update_or_create` keyed on the natural-key field. Re-running converges.
- Keyless masters (HeadSIONNorm/SIONExport/SIONImport/SIONNormNote/
  SIONNormCondition/ProductDescription/UnitPrice): the exporter emits a
  deterministic uuid5 as the row "key"; we upsert on `uid`. The uuid5 is derived
  from (model + parent natural key + content), so the same source row always maps
  to the same uid — re-running is idempotent and does not duplicate.
- FKs are resolved by the PARENT's natural key carried in the export as
  "<fk>__<parent_natural_key_field>". A row whose parent cannot be resolved is
  WARNED and SKIPPED (never silently dropped, never written with a dangling FK).

Load order is topological so every parent exists before its children.
Each model loads inside its own transaction; per-model created/updated/skipped
counts are printed. Read of the file only; writes go to the MDS DB.
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from masters.models import (
    Company,
    ExchangeRate,
    HeadSIONNorm,
    HSCode,
    ItemGroup,
    ItemHead,
    ItemName,
    NotificationNumber,
    Port,
    ProductDescription,
    SchemeCode,
    SIONExport,
    SIONImport,
    SIONNormClass,
    SIONNormCondition,
    SIONNormNote,
    UnitPrice,
)

# Topological order: roots first, then dependents.
LOAD_ORDER = [
    "HeadSIONNorm",
    "ItemGroup",
    "Company",
    "Port",
    "HSCode",
    "SchemeCode",
    "NotificationNumber",
    "ExchangeRate",
    "SIONNormClass",
    "ItemHead",
    "ItemName",
    "SIONExport",
    "SIONImport",
    "SIONNormNote",
    "SIONNormCondition",
    "ProductDescription",
    "UnitPrice",
]


class Command(BaseCommand):
    help = "Hydrate the MDS DB from an export_masters_mds JSON file (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--in", dest="infile", required=True, help="Path to the export JSON.")

    def handle(self, *args, **opts):
        try:
            with open(opts["infile"]) as fh:
                snapshot = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read export file: {exc}")

        tables = snapshot.get("tables", {})
        self.stdout.write(f"Source: {snapshot.get('source')}  generated_at: {snapshot.get('generated_at')}")

        # dispatch table: model name -> loader method
        loaders = {
            "HeadSIONNorm": self._load_head_sion_norm,
            "ItemGroup": self._load_item_group,
            "Company": self._load_company,
            "Port": self._load_port,
            "HSCode": self._load_hs_code,
            "SchemeCode": self._load_scheme_code,
            "NotificationNumber": self._load_notification_number,
            "ExchangeRate": self._load_exchange_rate,
            "SIONNormClass": self._load_sion_norm_class,
            "ItemHead": self._load_item_head,
            "ItemName": self._load_item_name,
            "SIONExport": self._load_sion_export,
            "SIONImport": self._load_sion_import,
            "SIONNormNote": self._load_sion_norm_note,
            "SIONNormCondition": self._load_sion_norm_condition,
            "ProductDescription": self._load_product_description,
            "UnitPrice": self._load_unit_price,
        }

        grand_created = grand_updated = grand_skipped = 0
        self.stdout.write(f"{'model':<20}{'in':>8}{'created':>9}{'updated':>9}{'skipped':>9}")
        for name in LOAD_ORDER:
            table = tables.get(name)
            if table is None:
                self.stdout.write(self.style.WARNING(f"  {name}: not in export — skipped"))
                continue
            records = table.get("records", [])
            with transaction.atomic():
                created, updated, skipped = loaders[name](records)
            grand_created += created
            grand_updated += updated
            grand_skipped += skipped
            style = self.style.SUCCESS if skipped == 0 else self.style.WARNING
            self.stdout.write(style(f"  {name:<18}{len(records):>8}{created:>9}{updated:>9}{skipped:>9}"))

        self.stdout.write(self.style.SUCCESS(
            f"Done. created={grand_created} updated={grand_updated} skipped={grand_skipped}"
        ))

    # ── FK-resolution caches (natural key -> instance) ────────────────────
    # Built lazily per model load so parents are already present.

    def _warn_skip(self, model_name, key, reason):
        self.stderr.write(f"  SKIP {model_name}[{key}]: {reason}")

    # ── business-keyed roots ──────────────────────────────────────────────

    def _load_company(self, records):
        created = updated = 0
        for r in records:
            d = r["data"]
            _, was_created = Company.objects.update_or_create(
                iec=d["iec"],
                defaults={k: v for k, v in d.items() if k != "iec"},
            )
            created += was_created
            updated += not was_created
        return created, updated, 0

    def _load_port(self, records):
        created = updated = 0
        for r in records:
            d = r["data"]
            _, was_created = Port.objects.update_or_create(
                code=d["code"], defaults={"name": d.get("name", "")}
            )
            created += was_created
            updated += not was_created
        return created, updated, 0

    def _load_item_group(self, records):
        created = updated = 0
        for r in records:
            d = r["data"]
            _, was_created = ItemGroup.objects.update_or_create(name=d["name"], defaults={})
            created += was_created
            updated += not was_created
        return created, updated, 0

    def _load_hs_code(self, records):
        created = updated = 0
        for r in records:
            d = r["data"]
            _, was_created = HSCode.objects.update_or_create(
                hs_code=d["hs_code"],
                defaults={k: v for k, v in d.items() if k != "hs_code"},
            )
            created += was_created
            updated += not was_created
        return created, updated, 0

    def _load_scheme_code(self, records):
        created = updated = 0
        for r in records:
            d = r["data"]
            _, was_created = SchemeCode.objects.update_or_create(
                code=d["code"], defaults={"label": d.get("label", "")}
            )
            created += was_created
            updated += not was_created
        return created, updated, 0

    def _load_notification_number(self, records):
        created = updated = 0
        for r in records:
            d = r["data"]
            _, was_created = NotificationNumber.objects.update_or_create(
                code=d["code"], defaults={"label": d.get("label", "")}
            )
            created += was_created
            updated += not was_created
        return created, updated, 0

    def _load_exchange_rate(self, records):
        created = updated = 0
        for r in records:
            d = r["data"]
            _, was_created = ExchangeRate.objects.update_or_create(
                date=d["date"],
                defaults={k: v for k, v in d.items() if k != "date"},
            )
            created += was_created
            updated += not was_created
        return created, updated, 0

    def _load_head_sion_norm(self, records):
        # keyless root: upsert on uid (carried as r["key"])
        created = updated = 0
        for r in records:
            _, was_created = HeadSIONNorm.objects.update_or_create(
                uid=r["key"], defaults={"name": r["data"].get("name", "")}
            )
            created += was_created
            updated += not was_created
        return created, updated, 0

    # ── level 1: depend on HeadSIONNorm ───────────────────────────────────

    def _load_sion_norm_class(self, records):
        created = updated = skipped = 0
        heads = {str(h.uid): h for h in HeadSIONNorm.objects.all()}
        for r in records:
            d = r["data"]
            parent_uid = d.get("head_norm__uid")
            head = heads.get(str(parent_uid)) if parent_uid else None
            if head is None:
                # head_norm is a required FK in MDS — cannot write a valid row.
                self._warn_skip("SIONNormClass", d.get("norm_class"),
                                f"missing HeadSIONNorm uid={parent_uid}")
                skipped += 1
                continue
            _, was_created = SIONNormClass.objects.update_or_create(
                norm_class=d["norm_class"],
                defaults={
                    "description": d.get("description"),
                    "is_active": d.get("is_active", False),
                    "head_norm": head,
                },
            )
            created += was_created
            updated += not was_created
        return created, updated, skipped

    # ── level 2 ───────────────────────────────────────────────────────────

    def _load_item_head(self, records):
        created = updated = skipped = 0
        norms = {n.norm_class: n for n in SIONNormClass.objects.all()}
        for r in records:
            d = r["data"]
            nk = d.get("restriction_norm__norm_class")
            norm = norms.get(nk) if nk else None
            if nk and norm is None:
                # restriction_norm is SET_NULL / nullable — warn but keep the row.
                self._warn_skip("ItemHead", d.get("name"),
                                f"restriction_norm '{nk}' not found; setting NULL")
            _, was_created = ItemHead.objects.update_or_create(
                name=d["name"],
                defaults={
                    "unit_rate": d.get("unit_rate", 0),
                    "is_restricted": d.get("is_restricted", False),
                    "restriction_percentage": d.get("restriction_percentage", 0),
                    "dict_key": d.get("dict_key"),
                    "restriction_norm": norm,
                },
            )
            created += was_created
            updated += not was_created
        return created, updated, skipped

    def _load_item_name(self, records):
        created = updated = skipped = 0
        groups = {g.name: g for g in ItemGroup.objects.all()}
        norms = {n.norm_class: n for n in SIONNormClass.objects.all()}
        for r in records:
            d = r["data"]
            gk = d.get("group__name")
            group = groups.get(gk) if gk else None
            if gk and group is None:
                self._warn_skip("ItemName", d.get("name"), f"group '{gk}' not found; setting NULL")
            nk = d.get("sion_norm_class__norm_class")
            norm = norms.get(nk) if nk else None
            if nk and norm is None:
                self._warn_skip("ItemName", d.get("name"),
                                f"sion_norm_class '{nk}' not found; setting NULL")
            _, was_created = ItemName.objects.update_or_create(
                name=d["name"],
                defaults={
                    "is_active": d.get("is_active", True),
                    "restriction_percentage": d.get("restriction_percentage", 0),
                    "display_order": d.get("display_order", 1),
                    "group": group,
                    "sion_norm_class": norm,
                },
            )
            created += was_created
            updated += not was_created
        return created, updated, skipped

    def _load_sion_export(self, records):
        created = updated = skipped = 0
        norms = {n.norm_class: n for n in SIONNormClass.objects.all()}
        for r in records:
            d = r["data"]
            nk = d.get("norm_class__norm_class")
            norm = norms.get(nk) if nk else None
            if norm is None:  # required FK
                self._warn_skip("SIONExport", r["key"], f"missing SIONNormClass '{nk}'")
                skipped += 1
                continue
            _, was_created = SIONExport.objects.update_or_create(
                uid=r["key"],
                defaults={
                    "description": d.get("description"),
                    "quantity": d.get("quantity", 0),
                    "unit": d.get("unit"),
                    "norm_class": norm,
                },
            )
            created += was_created
            updated += not was_created
        return created, updated, skipped

    def _load_sion_import(self, records):
        created = updated = skipped = 0
        norms = {n.norm_class: n for n in SIONNormClass.objects.all()}
        hscodes = {h.hs_code: h for h in HSCode.objects.all()}
        for r in records:
            d = r["data"]
            nk = d.get("norm_class__norm_class")
            norm = norms.get(nk) if nk else None
            if norm is None:  # required FK
                self._warn_skip("SIONImport", r["key"], f"missing SIONNormClass '{nk}'")
                skipped += 1
                continue
            hk = d.get("hsn_code__hs_code")
            hsn = hscodes.get(hk) if hk else None
            if hk and hsn is None:  # nullable SET_NULL — warn but keep row
                self._warn_skip("SIONImport", r["key"], f"hsn_code '{hk}' not found; setting NULL")
            _, was_created = SIONImport.objects.update_or_create(
                uid=r["key"],
                defaults={
                    "serial_number": d.get("serial_number", 0),
                    "description": d.get("description"),
                    "quantity": d.get("quantity", 0),
                    "unit": d.get("unit"),
                    "condition": d.get("condition"),
                    "norm_class": norm,
                    "hsn_code": hsn,
                },
            )
            created += was_created
            updated += not was_created
        return created, updated, skipped

    def _load_sion_norm_note(self, records):
        created = updated = skipped = 0
        norms = {n.norm_class: n for n in SIONNormClass.objects.all()}
        for r in records:
            d = r["data"]
            nk = d.get("sion_norm__norm_class")
            norm = norms.get(nk) if nk else None
            if norm is None:  # required FK
                self._warn_skip("SIONNormNote", r["key"], f"missing SIONNormClass '{nk}'")
                skipped += 1
                continue
            _, was_created = SIONNormNote.objects.update_or_create(
                uid=r["key"],
                defaults={
                    "note_text": d.get("note_text", ""),
                    "display_order": d.get("display_order", 0),
                    "sion_norm": norm,
                },
            )
            created += was_created
            updated += not was_created
        return created, updated, skipped

    def _load_sion_norm_condition(self, records):
        created = updated = skipped = 0
        norms = {n.norm_class: n for n in SIONNormClass.objects.all()}
        for r in records:
            d = r["data"]
            nk = d.get("sion_norm__norm_class")
            norm = norms.get(nk) if nk else None
            if norm is None:  # required FK
                self._warn_skip("SIONNormCondition", r["key"], f"missing SIONNormClass '{nk}'")
                skipped += 1
                continue
            _, was_created = SIONNormCondition.objects.update_or_create(
                uid=r["key"],
                defaults={
                    "condition_text": d.get("condition_text", ""),
                    "display_order": d.get("display_order", 0),
                    "sion_norm": norm,
                },
            )
            created += was_created
            updated += not was_created
        return created, updated, skipped

    def _load_product_description(self, records):
        created = updated = skipped = 0
        hscodes = {h.hs_code: h for h in HSCode.objects.all()}
        for r in records:
            d = r["data"]
            hk = d.get("hs_code__hs_code")
            hsn = hscodes.get(hk) if hk else None
            if hsn is None:  # PROTECT FK — required
                self._warn_skip("ProductDescription", r["key"], f"missing HSCode '{hk}'")
                skipped += 1
                continue
            _, was_created = ProductDescription.objects.update_or_create(
                uid=r["key"],
                defaults={
                    "product_description": d.get("product_description", ""),
                    "hs_code": hsn,
                },
            )
            created += was_created
            updated += not was_created
        return created, updated, skipped

    def _load_unit_price(self, records):
        created = updated = 0
        for r in records:
            d = r["data"]
            _, was_created = UnitPrice.objects.update_or_create(
                uid=r["key"],
                defaults={
                    "name": d.get("name", ""),
                    "unit_price": d.get("unit_price", 0),
                    "label": d.get("label", ""),
                },
            )
            created += was_created
            updated += not was_created
        return created, updated, 0
