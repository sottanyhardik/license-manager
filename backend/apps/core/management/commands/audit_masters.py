"""
Master Data Audit — exports a snapshot of all master tables for comparison
across servers.  Read-only; does not modify any data.

Usage (run on every server you want to audit):
    python manage.py audit_masters > audit-$(hostname)-$(date +%Y%m%d).json

Then diff the resulting JSON files on your local machine to see exactly which
records exist on which server.

Output format:
    {
      "server_name": "license-manager",
      "generated_at": "2026-05-14T10:00:00",
      "tables": {
        "core.companymodel": {
          "count": 152,
          "key_field": "iec",
          "records": [
            { "key": "ABCD1234", "id": 5, "data_hash": "a1b2…", "data": {...} },
            ...
          ]
        },
        ...
      }
    }
"""
import hashlib
import json
import socket
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import models


# ── Master models to audit (label, app_label.model_name, business_key_field(s)) ──
# Business key = the field(s) used to detect "this is the same record across servers"
MASTER_MODELS = [
    # (app_label.model_name,                 business_key)
    ("core.CompanyModel",                    "iec"),
    ("core.PortModel",                       "code"),
    ("core.ItemHeadModel",                   "name"),
    ("core.ItemGroupModel",                  "name"),
    ("core.ItemNameModel",                   "name"),
    ("core.HSCodeModel",                     "hs_code"),
    ("core.SionNormClassModel",              "norm_class"),
    ("core.SionNormNote",                    None),     # composite (FK + text); reported but not key-matched
    ("core.SionNormCondition",               None),     # composite
    ("core.ProductDescriptionModel",         None),     # FK-only; reviewed manually
    ("core.TransferLetterModel",             None),
    ("core.UnitPriceModel",                  None),
    ("core.ExchangeRateModel",               "date"),
    ("core.SchemeCode",                      "code"),
    ("core.NotificationNumber",              "code"),
]


def _serialize_value(value):
    """Make a value JSON-safe and stable for hashing."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, models.Model):
        return value.pk
    return value


def _record_to_dict(instance):
    """Convert a model instance to a flat dict of field name → JSON-safe value.
    Audit fields (created_*, modified_*) are kept but excluded from the hash.

    For ForeignKey fields, also exports `<fk_name>__<business_key>` so the
    importer can resolve FKs by business key on the destination server.
    """
    out = {}
    for field in instance._meta.fields:
        if field.is_relation and field.many_to_one:
            # ForeignKey — export the FK id AND a resolvable business key.
            # Use attname (e.g. "head_norm_id") to read the raw FK id without
            # triggering a DB fetch that can raise DoesNotExist on orphan FKs.
            fk_id = getattr(instance, field.attname, None)
            out[field.name] = fk_id
            if fk_id is not None:
                try:
                    related_obj = getattr(instance, field.name, None)
                except field.related_model.DoesNotExist:
                    related_obj = None
                if related_obj is not None:
                    for candidate in ("name", "code", "iec", "hs_code", "norm_class"):
                        if hasattr(related_obj, candidate):
                            val = getattr(related_obj, candidate, None)
                            if val:
                                out[f"{field.name}__{candidate}"] = str(val)
                                break
        else:
            out[field.name] = _serialize_value(getattr(instance, field.attname, None))
    return out


def _hash_record(data, exclude=("id", "created_on", "modified_on", "created_by", "modified_by")):
    """Hash the record's business data for diffing — exclude IDs and audit fields."""
    payload = {k: v for k, v in data.items() if k not in exclude}
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


class Command(BaseCommand):
    help = "Export a snapshot of master tables for cross-server comparison (read-only)"

    def add_arguments(self, parser):
        parser.add_argument("--out", default=None, help="Write JSON to file (default: stdout)")
        parser.add_argument("--server-name", default=None, help="Override hostname label")

    def handle(self, *args, **opts):
        server_name = opts.get("server_name") or socket.gethostname()
        snapshot = {
            "server_name": server_name,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "tables": {},
        }

        for label, key_field in MASTER_MODELS:
            try:
                Model = apps.get_model(label)
            except LookupError:
                snapshot["tables"][label.lower()] = {"error": "model not found"}
                continue

            qs = Model.objects.all()
            records = []
            for inst in qs.iterator():
                data = _record_to_dict(inst)
                if key_field:
                    key_val = data.get(key_field)
                    key = str(key_val) if key_val is not None else f"__null__{inst.pk}"
                else:
                    key = f"id={inst.pk}"
                records.append({
                    "key": key,
                    "id": inst.pk,
                    "data_hash": _hash_record(data),
                    "data": data,
                })

            snapshot["tables"][label.lower()] = {
                "count": len(records),
                "key_field": key_field,
                "records": records,
            }

        output = json.dumps(snapshot, indent=2, default=str)
        if opts.get("out"):
            Path(opts["out"]).write_text(output, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Wrote audit to {opts['out']}"))
        else:
            self.stdout.write(output)
