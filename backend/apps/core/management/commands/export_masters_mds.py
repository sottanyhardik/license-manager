"""
Export all 17 master/reference tables from the license-manager (`core`) DB into a
single JSON document that the Master-Data Service (MDS) `load_masters` command can
ingest to hydrate its own DB — WITHOUT ever transferring integer PKs.

Design (see docs/architecture/ADR-001-master-data-service.md):

- Read-only. Never writes to the source DB.
- Each row is emitted with:
    * its BUSINESS (natural) key value under "key" (omitted / null for the
      keyless masters — the loader synthesises a stable uuid5 for those), and
    * every data field under "data" (field names match MDS field names exactly),
    * every ForeignKey to another master expressed as the PARENT's natural key
      under "<fk>__<parent_natural_key_field>" so the loader can resolve the FK
      with no ids in play.
- The keyless masters (HeadSIONNorm, SIONExport, SIONImport, SIONNormNote,
  SIONNormCondition, ProductDescription, UnitPrice) have no business key. To let
  their *children* reference them, this exporter computes the SAME deterministic
  uuid5 the loader will assign (shared recipe in `mds_natural_key.py`-style logic
  duplicated here so the two commands stay independent) and emits it as the
  parent natural key on the child rows. HeadSIONNorm is the only keyless master
  that is itself a parent, so only its synthetic key must be reproduced here.

The 3 SION models the legacy `audit_masters` command misses
(HeadSIONNormsModel, SIONExportModel, SIONImportModel) are fully covered here.
"""
import json
import socket
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

# Canonical uid recipe shared with the consumer backfill (mds_client.keys).
# Falls back to a byte-identical inline copy if mds_client is not installed in
# this environment (e.g. running the exporter without the client package).
try:
    from mds_client.keys import (
        MDS_UUID_NAMESPACE,
        synthetic_uid as _canonical_synthetic_uid,
        sig_head_sion_norm,
        sig_sion_export,
        sig_sion_import,
        sig_sion_norm_note,
        sig_sion_norm_condition,
        sig_product_description,
        sig_unit_price,
    )
except ImportError:  # pragma: no cover - fallback keeps the exporter standalone
    import uuid as _uuid

    MDS_UUID_NAMESPACE = _uuid.UUID("6f1a9d2e-0c4b-5a7e-8b3f-2d9c1e4a7b60")

    def _ss(v):
        if v is None:
            return ""
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        if isinstance(v, Decimal):
            return str(v)
        return str(v)

    def _canonical_synthetic_uid(label, parent_nk, sig):
        name = f"{label}|{parent_nk or ''}|{sig or ''}"
        return str(_uuid.uuid5(MDS_UUID_NAMESPACE, name))

    def sig_head_sion_norm(name):
        return _ss(name)

    def sig_sion_export(description, quantity, unit):
        return "|".join([_ss(description), _ss(quantity), _ss(unit)])

    def sig_sion_import(serial_number, description, quantity, unit, condition, hs_code):
        return "|".join([str(serial_number), _ss(description), _ss(quantity), _ss(unit), _ss(condition), _ss(hs_code)])

    def sig_sion_norm_note(display_order, note_text):
        return "|".join([str(display_order), _ss(note_text)])

    def sig_sion_norm_condition(display_order, condition_text):
        return "|".join([str(display_order), _ss(condition_text)])

    def sig_product_description(product_description):
        return _ss(product_description)

    def sig_unit_price(name, unit_price, label):
        return "|".join([_ss(name), _ss(unit_price), _ss(label)])

from apps.core.models import (
    CompanyModel,
    ExchangeRateModel,
    HeadSIONNormsModel,
    HSCodeModel,
    ItemGroupModel,
    ItemHeadModel,
    ItemNameModel,
    NotificationNumber,
    PortModel,
    ProductDescriptionModel,
    SchemeCode,
    SionNormClassModel,
    SIONExportModel,
    SIONImportModel,
    SionNormCondition,
    SionNormNote,
    UnitPriceModel,
)

# Shared, canonical serialization/row logic (used by BOTH this exporter and the
# online write cutover in apps/core/views/master_view.py) so the offline export
# payload and the online write payload derive from ONE codepath.
from apps.core.mds_payload import _serialize_scalar as _serialize  # noqa: E402
from apps.core.mds_payload import build_export_record  # noqa: E402


def _synthetic_uid(mds_model_label: str, parent_natural_key: str, content_signature: str) -> str:
    """Deterministic synthetic natural key for a keyless master row.

    Thin wrapper over the canonical ``mds_client.keys.synthetic_uid`` so the
    exporter and the consumer backfill share ONE recipe (see module docstring).
    """
    return _canonical_synthetic_uid(mds_model_label, parent_natural_key, content_signature)


class Command(BaseCommand):
    help = "Export all 17 masters to JSON for MDS hydration (read-only, id-free)."

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True, help="Path to write the JSON export.")

    def handle(self, *args, **opts):
        tables = {}

        # ── ROOTS (business-keyed, no master FK) ──────────────────────────
        tables["Company"] = self._export_company()
        tables["Port"] = self._export_port()
        tables["ItemGroup"] = self._export_item_group()
        tables["HSCode"] = self._export_hs_code()
        tables["SchemeCode"] = self._export_scheme_code()
        tables["NotificationNumber"] = self._export_notification_number()
        tables["ExchangeRate"] = self._export_exchange_rate()
        tables["HeadSIONNorm"] = self._export_head_sion_norm()  # keyless root

        # ── LEVEL 1 (depend on HeadSIONNorm) ──────────────────────────────
        tables["SIONNormClass"] = self._export_sion_norm_class()

        # ── LEVEL 2 (depend on SIONNormClass / HSCode / ItemGroup) ────────
        tables["ItemHead"] = self._export_item_head()          # FK -> SIONNormClass
        tables["ItemName"] = self._export_item_name()          # FK -> ItemGroup, SIONNormClass
        tables["SIONExport"] = self._export_sion_export()      # FK -> SIONNormClass
        tables["SIONImport"] = self._export_sion_import()      # FK -> SIONNormClass, HSCode
        tables["SIONNormNote"] = self._export_sion_norm_note()  # FK -> SIONNormClass
        tables["SIONNormCondition"] = self._export_sion_norm_condition()  # FK -> SIONNormClass
        tables["ProductDescription"] = self._export_product_description()  # FK -> HSCode
        tables["UnitPrice"] = self._export_unit_price()        # keyless, no FK

        snapshot = {
            "source": socket.gethostname(),
            "generated_at": timezone.now().isoformat(timespec="seconds"),
            "tables": tables,
        }

        Path(opts["out"]).write_text(
            json.dumps(snapshot, indent=2, default=str),
            encoding="utf-8",
        )

        total = sum(t["count"] for t in tables.values())
        for name, t in tables.items():
            self.stdout.write(f"  {name:<20} {t['count']:>7}")
        self.stdout.write(self.style.SUCCESS(f"Exported {total} rows across {len(tables)} masters -> {opts['out']}"))

    # ── per-model exporters ───────────────────────────────────────────────

    def _rows(self, key_field, records):
        return {"key_field": key_field, "count": len(records), "records": records}

    # Business-keyed masters: the shared per-instance builder produces the exact
    # id-free row (FKs as parent natural keys, media as path string) — one recipe
    # shared with the online write cutover. `build_export_record` returns
    # {"key", "data"} in this exporter's contract shape.
    def _export_company(self):
        recs = [build_export_record(c) for c in CompanyModel.objects.all().iterator()]
        return self._rows("iec", recs)

    def _export_port(self):
        recs = [build_export_record(p) for p in PortModel.objects.all().iterator()]
        return self._rows("code", recs)

    def _export_item_group(self):
        recs = [build_export_record(g) for g in ItemGroupModel.objects.all().iterator()]
        return self._rows("name", recs)

    def _export_hs_code(self):
        recs = [build_export_record(h) for h in HSCodeModel.objects.all().iterator()]
        return self._rows("hs_code", recs)

    def _export_scheme_code(self):
        recs = [build_export_record(s) for s in SchemeCode.objects.all().iterator()]
        return self._rows("code", recs)

    def _export_notification_number(self):
        recs = [build_export_record(n) for n in NotificationNumber.objects.all().iterator()]
        return self._rows("code", recs)

    def _export_exchange_rate(self):
        recs = [build_export_record(r) for r in ExchangeRateModel.objects.all().iterator()]
        return self._rows("date", recs)

    def _export_head_sion_norm(self):
        # keyless: emit the synthetic uid so children can reference it.
        # Use .values() with EXPLICIT columns: the Phase-1 timestamp columns
        # (created_on/modified_on) may not yet be migrated onto the source DB,
        # and a default SELECT * would reference them. We only need `name`.
        recs = []
        for row in HeadSIONNormsModel.objects.values("name").iterator():
            recs.append({
                "key": _synthetic_uid("HeadSIONNorm", "", sig_head_sion_norm(row["name"])),
                "data": {"name": row["name"]},
            })
        return self._rows("uid", recs)

    def _export_sion_norm_class(self):
        # head_norm's synthetic uid needs the parent's `name`; pull it via
        # .values("head_norm__name") so we never SELECT HeadSIONNorm's
        # (possibly-unmigrated) timestamp columns.
        recs = []
        qs = SionNormClassModel.objects.values(
            "norm_class", "description", "is_active", "head_norm_id", "head_norm__name"
        ).iterator()
        for s in qs:
            data = {
                "norm_class": s["norm_class"],
                "description": s["description"],
                "is_active": s["is_active"],
                # FK head_norm -> HeadSIONNorm (keyless parent, synthetic uid)
                "head_norm__uid": (
                    _synthetic_uid("HeadSIONNorm", "", sig_head_sion_norm(s["head_norm__name"]))
                    if s["head_norm_id"] else None
                ),
            }
            recs.append({"key": s["norm_class"], "data": data})
        return self._rows("norm_class", recs)

    def _export_item_head(self):
        qs = ItemHeadModel.objects.select_related("restriction_norm").iterator()
        recs = [build_export_record(i) for i in qs]
        return self._rows("name", recs)

    def _export_item_name(self):
        qs = ItemNameModel.objects.select_related("group", "sion_norm_class").iterator()
        recs = [build_export_record(i) for i in qs]
        return self._rows("name", recs)

    def _export_sion_export(self):
        # keyless (SyncTimestampModel): use .values() with explicit columns so
        # the possibly-unmigrated timestamp columns are never selected.
        # signature = description + quantity + unit ; parent = norm_class.
        recs = []
        qs = SIONExportModel.objects.values(
            "description", "quantity", "unit", "norm_class_id", "norm_class__norm_class"
        ).iterator()
        for e in qs:
            parent_nk = e["norm_class__norm_class"] if e["norm_class_id"] else ""
            sig = sig_sion_export(e["description"], e["quantity"], e["unit"])
            uid = _synthetic_uid("SIONExport", parent_nk, sig)
            data = {
                "description": e["description"],
                "quantity": _serialize(e["quantity"]),
                "unit": e["unit"],
                "norm_class__norm_class": parent_nk or None,
            }
            recs.append({"key": uid, "data": data})
        return self._rows("uid", recs)

    def _export_sion_import(self):
        # keyless (SyncTimestampModel): explicit .values() columns only.
        recs = []
        qs = SIONImportModel.objects.values(
            "serial_number", "description", "quantity", "unit", "condition",
            "norm_class_id", "norm_class__norm_class", "hsn_code_id", "hsn_code__hs_code",
        ).iterator()
        for i in qs:
            parent_nk = i["norm_class__norm_class"] if i["norm_class_id"] else ""
            hs = i["hsn_code__hs_code"] if i["hsn_code_id"] else ""
            sig = sig_sion_import(
                i["serial_number"], i["description"], i["quantity"],
                i["unit"], i["condition"], hs,
            )
            uid = _synthetic_uid("SIONImport", parent_nk, sig)
            data = {
                "serial_number": i["serial_number"],
                "description": i["description"],
                "quantity": _serialize(i["quantity"]),
                "unit": i["unit"],
                "condition": i["condition"],
                "norm_class__norm_class": parent_nk or None,
                # FK hsn_code -> HSCode(hs_code) (nullable, SET_NULL)
                "hsn_code__hs_code": hs or None,
            }
            recs.append({"key": uid, "data": data})
        return self._rows("uid", recs)

    # These 4 keyless masters extend AuditModel (timestamps always migrated), so
    # the instance-based shared builder is safe. It reads the row's own `uid`
    # (set by SyntheticUidMixin.save via the SAME canonical recipe), so the key
    # is byte-identical to the inline computation these methods used before.
    def _export_sion_norm_note(self):
        qs = SionNormNote.objects.select_related("sion_norm").iterator()
        recs = [build_export_record(n) for n in qs]
        return self._rows("uid", recs)

    def _export_sion_norm_condition(self):
        qs = SionNormCondition.objects.select_related("sion_norm").iterator()
        recs = [build_export_record(c) for c in qs]
        return self._rows("uid", recs)

    def _export_product_description(self):
        qs = ProductDescriptionModel.objects.select_related("hs_code").iterator()
        recs = [build_export_record(p) for p in qs]
        return self._rows("uid", recs)

    def _export_unit_price(self):
        recs = [build_export_record(u) for u in UnitPriceModel.objects.all().iterator()]
        return self._rows("uid", recs)
