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
import hashlib
import json
import socket
import uuid
from datetime import date, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

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

# Fixed namespace shared with the MDS loader so synthetic uids are reproducible
# on both sides. DO NOT CHANGE — changing it re-keys every keyless row.
MDS_UUID_NAMESPACE = uuid.UUID("6f1a9d2e-0c4b-5a7e-8b3f-2d9c1e4a7b60")


def _serialize(value):
    """JSON-safe, stable representation of a scalar field value."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _synthetic_uid(mds_model_label: str, parent_natural_key: str, content_signature: str) -> str:
    """Deterministic synthetic natural key for a keyless master row.

    MUST match master-data-service load_masters._synthetic_uid exactly:
        uuid5(NAMESPACE, "<mds_model_label>|<parent_natural_key>|<content_signature>")
    """
    name = f"{mds_model_label}|{parent_natural_key or ''}|{content_signature or ''}"
    return str(uuid.uuid5(MDS_UUID_NAMESPACE, name))


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

        with open(opts["out"], "w") as fh:
            json.dump(snapshot, fh, indent=2, default=str)

        total = sum(t["count"] for t in tables.values())
        for name, t in tables.items():
            self.stdout.write(f"  {name:<20} {t['count']:>7}")
        self.stdout.write(self.style.SUCCESS(f"Exported {total} rows across {len(tables)} masters -> {opts['out']}"))

    # ── per-model exporters ───────────────────────────────────────────────

    def _rows(self, key_field, records):
        return {"key_field": key_field, "count": len(records), "records": records}

    def _export_company(self):
        recs = []
        for c in CompanyModel.objects.all().iterator():
            recs.append({
                "key": c.iec,
                "data": {
                    "iec": c.iec,
                    "pan": c.pan,
                    "gst_number": c.gst_number,
                    "name": c.name,
                    "contact_person": c.contact_person,
                    "phone_number": c.phone_number,
                    "email": c.email,
                    "address_line_1": c.address_line_1,
                    "address_line_2": c.address_line_2,
                    # ImageField -> stored path string (MDS CharField)
                    "logo": c.logo.name if c.logo else "",
                    "signature": c.signature.name if c.signature else "",
                    "stamp": c.stamp.name if c.stamp else "",
                    "bill_colour": c.bill_colour,
                    "bank_account_number": c.bank_account_number,
                    "bank_name": c.bank_name,
                    "ifsc_code": c.ifsc_code,
                    "account_type": c.account_type,
                },
            })
        return self._rows("iec", recs)

    def _export_port(self):
        recs = [{
            "key": p.code,
            "data": {"code": p.code, "name": p.name},
        } for p in PortModel.objects.all().iterator()]
        return self._rows("code", recs)

    def _export_item_group(self):
        recs = [{
            "key": g.name,
            "data": {"name": g.name},
        } for g in ItemGroupModel.objects.all().iterator()]
        return self._rows("name", recs)

    def _export_hs_code(self):
        recs = [{
            "key": h.hs_code,
            "data": {
                "hs_code": h.hs_code,
                "product_description": h.product_description,
                "unit_price": _serialize(h.unit_price),
                "basic_duty": h.basic_duty,
                "unit": h.unit,
                "policy": h.policy,
                "note": h.note,
            },
        } for h in HSCodeModel.objects.all().iterator()]
        return self._rows("hs_code", recs)

    def _export_scheme_code(self):
        recs = [{
            "key": s.code,
            "data": {"code": s.code, "label": s.label},
        } for s in SchemeCode.objects.all().iterator()]
        return self._rows("code", recs)

    def _export_notification_number(self):
        recs = [{
            "key": n.code,
            "data": {"code": n.code, "label": n.label},
        } for n in NotificationNumber.objects.all().iterator()]
        return self._rows("code", recs)

    def _export_exchange_rate(self):
        recs = [{
            "key": r.date.isoformat(),
            "data": {
                "date": r.date.isoformat(),
                "usd": _serialize(r.usd),
                "euro": _serialize(r.euro),
                "pound_sterling": _serialize(r.pound_sterling),
                "chinese_yuan": _serialize(r.chinese_yuan),
            },
        } for r in ExchangeRateModel.objects.all().iterator()]
        return self._rows("date", recs)

    def _export_head_sion_norm(self):
        # keyless: emit the synthetic uid so children can reference it.
        # Use .values() with EXPLICIT columns: the Phase-1 timestamp columns
        # (created_on/modified_on) may not yet be migrated onto the source DB,
        # and a default SELECT * would reference them. We only need `name`.
        recs = []
        for row in HeadSIONNormsModel.objects.values("name").iterator():
            recs.append({
                "key": _synthetic_uid("HeadSIONNorm", "", row["name"] or ""),
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
                    _synthetic_uid("HeadSIONNorm", "", s["head_norm__name"] or "")
                    if s["head_norm_id"] else None
                ),
            }
            recs.append({"key": s["norm_class"], "data": data})
        return self._rows("norm_class", recs)

    def _export_item_head(self):
        recs = []
        qs = ItemHeadModel.objects.select_related("restriction_norm").iterator()
        for i in qs:
            data = {
                "name": i.name,
                "unit_rate": _serialize(i.unit_rate),
                "is_restricted": i.is_restricted,
                "restriction_percentage": _serialize(i.restriction_percentage),
                "dict_key": i.dict_key,
                # FK restriction_norm -> SIONNormClass(norm_class)
                "restriction_norm__norm_class": i.restriction_norm.norm_class if i.restriction_norm_id else None,
            }
            recs.append({"key": i.name, "data": data})
        return self._rows("name", recs)

    def _export_item_name(self):
        recs = []
        qs = ItemNameModel.objects.select_related("group", "sion_norm_class").iterator()
        for i in qs:
            data = {
                "name": i.name,
                "is_active": i.is_active,
                "restriction_percentage": _serialize(i.restriction_percentage),
                "display_order": i.display_order,
                # FK group -> ItemGroup(name)
                "group__name": i.group.name if i.group_id else None,
                # FK sion_norm_class -> SIONNormClass(norm_class)
                "sion_norm_class__norm_class": i.sion_norm_class.norm_class if i.sion_norm_class_id else None,
            }
            recs.append({"key": i.name, "data": data})
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
            sig = "|".join([
                str(e["description"] or ""),
                _serialize(e["quantity"]) or "",
                str(e["unit"] or ""),
            ])
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
            sig = "|".join([
                str(i["serial_number"]),
                str(i["description"] or ""),
                _serialize(i["quantity"]) or "",
                str(i["unit"] or ""),
                str(i["condition"] or ""),
                str(hs),
            ])
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

    def _export_sion_norm_note(self):
        recs = []
        qs = SionNormNote.objects.select_related("sion_norm").iterator()
        for n in qs:
            parent_nk = n.sion_norm.norm_class if n.sion_norm_id else ""
            sig = "|".join([str(n.display_order), str(n.note_text or "")])
            uid = _synthetic_uid("SIONNormNote", parent_nk, sig)
            data = {
                "note_text": n.note_text,
                "display_order": n.display_order,
                "sion_norm__norm_class": parent_nk or None,
            }
            recs.append({"key": uid, "data": data})
        return self._rows("uid", recs)

    def _export_sion_norm_condition(self):
        recs = []
        qs = SionNormCondition.objects.select_related("sion_norm").iterator()
        for c in qs:
            parent_nk = c.sion_norm.norm_class if c.sion_norm_id else ""
            sig = "|".join([str(c.display_order), str(c.condition_text or "")])
            uid = _synthetic_uid("SIONNormCondition", parent_nk, sig)
            data = {
                "condition_text": c.condition_text,
                "display_order": c.display_order,
                "sion_norm__norm_class": parent_nk or None,
            }
            recs.append({"key": uid, "data": data})
        return self._rows("uid", recs)

    def _export_product_description(self):
        recs = []
        qs = ProductDescriptionModel.objects.select_related("hs_code").iterator()
        for p in qs:
            parent_nk = p.hs_code.hs_code if p.hs_code_id else ""
            sig = str(p.product_description or "")
            uid = _synthetic_uid("ProductDescription", parent_nk, sig)
            data = {
                "product_description": p.product_description,
                "hs_code__hs_code": parent_nk or None,
            }
            recs.append({"key": uid, "data": data})
        return self._rows("uid", recs)

    def _export_unit_price(self):
        # keyless, no FK: content signature = name + unit_price + label
        recs = []
        for u in UnitPriceModel.objects.all().iterator():
            sig = "|".join([str(u.name or ""), _serialize(u.unit_price) or "", str(u.label or "")])
            uid = _synthetic_uid("UnitPrice", "", sig)
            data = {
                "name": u.name,
                "unit_price": _serialize(u.unit_price),
                "label": u.label,
            }
            recs.append({"key": uid, "data": data})
        return self._rows("uid", recs)
