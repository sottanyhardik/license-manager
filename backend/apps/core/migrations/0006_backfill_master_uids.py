"""Backfill deterministic `uid`s onto the 7 keyless masters (ADR-001 Decision 6).

Uses the canonical recipe in ``mds_client.keys`` (byte-identical fallback if the
client is not installed) so the uid written here MATCHES the uid the MDS export
assigned for the same logical row — that is what lets the mirror sync converge
by ``uid`` without creating duplicates.

Set-based: FK parent natural keys are resolved via ``.values(...)`` joins rather
than row-by-row FK loads. Only rows with a NULL uid are touched, so re-running is
idempotent. Reverse simply nulls the uids back out.
"""

from django.db import migrations

# Canonical recipe — shared with the exporter/loader; inline fallback keeps the
# migration runnable in environments without the mds_client package installed.
try:
    from mds_client.keys import (
        synthetic_uid,
        sig_head_sion_norm,
        sig_sion_export,
        sig_sion_import,
        sig_sion_norm_note,
        sig_sion_norm_condition,
        sig_product_description,
        sig_unit_price,
    )
except ImportError:  # pragma: no cover
    import uuid
    from datetime import date, datetime
    from decimal import Decimal

    _NS = uuid.UUID("6f1a9d2e-0c4b-5a7e-8b3f-2d9c1e4a7b60")

    def _ss(v):
        if v is None:
            return ""
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        if isinstance(v, Decimal):
            return str(v)
        return str(v)

    def synthetic_uid(label, parent_nk, sig):
        return str(uuid.uuid5(_NS, f"{label}|{parent_nk or ''}|{sig or ''}"))

    def sig_head_sion_norm(name):
        return _ss(name)

    def sig_sion_export(description, quantity, unit):
        return "|".join([_ss(description), _ss(quantity), _ss(unit)])

    def sig_sion_import(serial_number, description, quantity, unit, condition, hs_code):
        return "|".join([str(serial_number), _ss(description), _ss(quantity),
                         _ss(unit), _ss(condition), _ss(hs_code)])

    def sig_sion_norm_note(display_order, note_text):
        return "|".join([str(display_order), _ss(note_text)])

    def sig_sion_norm_condition(display_order, condition_text):
        return "|".join([str(display_order), _ss(condition_text)])

    def sig_product_description(product_description):
        return _ss(product_description)

    def sig_unit_price(name, unit_price, label):
        return "|".join([_ss(name), _ss(unit_price), _ss(label)])


def _bulk_set(Model, rows):
    """rows: iterable of (pk, uid). Update in one batch."""
    objs = []
    for pk, uid in rows:
        obj = Model(pk=pk)
        obj.uid = uid
        objs.append(obj)
    if objs:
        Model.objects.bulk_update(objs, ["uid"], batch_size=1000)


def backfill(apps, schema_editor):
    Head = apps.get_model("core", "HeadSIONNormsModel")
    Export = apps.get_model("core", "SIONExportModel")
    Import = apps.get_model("core", "SIONImportModel")
    Note = apps.get_model("core", "SionNormNote")
    Cond = apps.get_model("core", "SionNormCondition")
    ProdDesc = apps.get_model("core", "ProductDescriptionModel")
    Unit = apps.get_model("core", "UnitPriceModel")

    # HeadSIONNorm (root, sig = name)
    _bulk_set(Head, (
        (r["pk"], synthetic_uid("HeadSIONNorm", "", sig_head_sion_norm(r["name"])))
        for r in Head.objects.filter(uid__isnull=True).values("pk", "name")
    ))

    # SIONExport (parent = norm_class.norm_class)
    _bulk_set(Export, (
        (
            r["pk"],
            synthetic_uid(
                "SIONExport",
                r["norm_class__norm_class"] if r["norm_class_id"] else "",
                sig_sion_export(r["description"], r["quantity"], r["unit"]),
            ),
        )
        for r in Export.objects.filter(uid__isnull=True).values(
            "pk", "description", "quantity", "unit", "norm_class_id", "norm_class__norm_class"
        )
    ))

    # SIONImport (parent = norm_class; hs from hsn_code.hs_code)
    _bulk_set(Import, (
        (
            r["pk"],
            synthetic_uid(
                "SIONImport",
                r["norm_class__norm_class"] if r["norm_class_id"] else "",
                sig_sion_import(
                    r["serial_number"], r["description"], r["quantity"], r["unit"],
                    r["condition"], r["hsn_code__hs_code"] if r["hsn_code_id"] else "",
                ),
            ),
        )
        for r in Import.objects.filter(uid__isnull=True).values(
            "pk", "serial_number", "description", "quantity", "unit", "condition",
            "norm_class_id", "norm_class__norm_class", "hsn_code_id", "hsn_code__hs_code",
        )
    ))

    # SIONNormNote (parent = sion_norm.norm_class)
    _bulk_set(Note, (
        (
            r["pk"],
            synthetic_uid(
                "SIONNormNote",
                r["sion_norm__norm_class"] if r["sion_norm_id"] else "",
                sig_sion_norm_note(r["display_order"], r["note_text"]),
            ),
        )
        for r in Note.objects.filter(uid__isnull=True).values(
            "pk", "display_order", "note_text", "sion_norm_id", "sion_norm__norm_class"
        )
    ))

    # SIONNormCondition (parent = sion_norm.norm_class)
    _bulk_set(Cond, (
        (
            r["pk"],
            synthetic_uid(
                "SIONNormCondition",
                r["sion_norm__norm_class"] if r["sion_norm_id"] else "",
                sig_sion_norm_condition(r["display_order"], r["condition_text"]),
            ),
        )
        for r in Cond.objects.filter(uid__isnull=True).values(
            "pk", "display_order", "condition_text", "sion_norm_id", "sion_norm__norm_class"
        )
    ))

    # ProductDescription (parent = hs_code.hs_code)
    _bulk_set(ProdDesc, (
        (
            r["pk"],
            synthetic_uid(
                "ProductDescription",
                r["hs_code__hs_code"] if r["hs_code_id"] else "",
                sig_product_description(r["product_description"]),
            ),
        )
        for r in ProdDesc.objects.filter(uid__isnull=True).values(
            "pk", "product_description", "hs_code_id", "hs_code__hs_code"
        )
    ))

    # UnitPrice (root, sig = name|unit_price|label)
    _bulk_set(Unit, (
        (r["pk"], synthetic_uid("UnitPrice", "", sig_unit_price(r["name"], r["unit_price"], r["label"])))
        for r in Unit.objects.filter(uid__isnull=True).values("pk", "name", "unit_price", "label")
    ))


def unbackfill(apps, schema_editor):
    for model_name in (
        "HeadSIONNormsModel", "SIONExportModel", "SIONImportModel", "SionNormNote",
        "SionNormCondition", "ProductDescriptionModel", "UnitPriceModel",
    ):
        apps.get_model("core", model_name).objects.update(uid=None)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_add_uid_to_keyless_masters"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
