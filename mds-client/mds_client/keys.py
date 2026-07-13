"""
Canonical deterministic natural-key (``uid``) recipe for the 7 KEYLESS masters.

Why this module exists
----------------------
The keyless masters (HeadSIONNorm, SIONExport, SIONImport, SIONNormNote,
SIONNormCondition, ProductDescription, UnitPrice) have no business key, so the
MDS/consumer sync keys them on a synthetic ``uid`` (ADR-001 Decision 6). For a
row to CONVERGE across servers, every side must derive the *identical* uid from
the *same logical content*. Two independent computations happen in the backend:

  1. ``export_masters_mds`` — computes the uid emitted to MDS as ``r["key"]``
     (MDS stores it verbatim on ``SyntheticKeyMixin.uid``).
  2. the consumer ``backfill_master_uids`` data migration — computes the uid it
     writes onto the local mirror rows.

If (1) and (2) disagree by a single byte, the same logical row lands under two
different uids and the mirror sync creates a DUPLICATE instead of converging.
Centralising the recipe here (imported by BOTH) makes divergence impossible.

The recipe (DO NOT CHANGE — changing it re-keys every keyless row):

    uid = uuid5(MDS_UUID_NAMESPACE, "<mds_model_label>|<parent_natural_key>|<content_signature>")

where the content signature is a ``|``-joined, order-fixed string of the row's
identifying fields (see the per-model builders below). ``None`` is normalised to
the empty string; Decimals are stringified with :func:`serialize_scalar` so the
signature is stable regardless of Python object identity.

This module has NO Django import so it is safe to import from a data migration,
a management command, or plain tests.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

# Fixed namespace shared with the MDS loader/exporter so synthetic uids are
# reproducible on every side. DO NOT CHANGE — changing it re-keys every row.
MDS_UUID_NAMESPACE = uuid.UUID("6f1a9d2e-0c4b-5a7e-8b3f-2d9c1e4a7b60")


def serialize_scalar(value) -> str:
    """Stable string form of a scalar for use inside a content signature.

    ``None`` -> "" ; dates/datetimes -> ISO 8601 ; Decimal -> ``str`` (which
    preserves the stored scale, matching what the exporter emits). Everything
    else falls back to ``str``. This MUST match how ``export_masters_mds``
    serialises the same field, so the two signatures are byte-identical.
    """
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def synthetic_uid(mds_model_label: str, parent_natural_key, content_signature) -> str:
    """The canonical deterministic uid for a keyless master row.

    ``mds_model_label`` is the MDS class short name (e.g. "HeadSIONNorm",
    "SIONExport") — NOT the consumer label. ``parent_natural_key`` is the parent
    master's business key (or "" for roots). ``content_signature`` is the
    ``|``-joined identifying content (use the per-model builders below).
    """
    name = f"{mds_model_label}|{parent_natural_key or ''}|{content_signature or ''}"
    return str(uuid.uuid5(MDS_UUID_NAMESPACE, name))


# --- per-model content-signature builders ----------------------------------
# Each returns the content_signature string for one keyless master. The field
# order here is the CONTRACT — it must match export_masters_mds exactly.

def sig_head_sion_norm(name) -> str:
    return serialize_scalar(name)


def sig_sion_export(description, quantity, unit) -> str:
    return "|".join([
        serialize_scalar(description),
        serialize_scalar(quantity),
        serialize_scalar(unit),
    ])


def sig_sion_import(serial_number, description, quantity, unit, condition, hs_code) -> str:
    return "|".join([
        # serial_number is an int with a DB default of 0; str() (not
        # serialize_scalar) so a real 0 and a None both render as "0"/"None"
        # exactly as the exporter does via str(i["serial_number"]).
        str(serial_number),
        serialize_scalar(description),
        serialize_scalar(quantity),
        serialize_scalar(unit),
        serialize_scalar(condition),
        serialize_scalar(hs_code),
    ])


def sig_sion_norm_note(display_order, note_text) -> str:
    return "|".join([str(display_order), serialize_scalar(note_text)])


def sig_sion_norm_condition(display_order, condition_text) -> str:
    return "|".join([str(display_order), serialize_scalar(condition_text)])


def sig_product_description(product_description) -> str:
    return serialize_scalar(product_description)


def sig_unit_price(name, unit_price, label) -> str:
    return "|".join([
        serialize_scalar(name),
        serialize_scalar(unit_price),
        serialize_scalar(label),
    ])


# Convenience: the MDS model label used in the uid for each consumer model.
# Keyed by the consumer model class NAME (as it appears in apps.core.models).
KEYLESS_MDS_LABELS = {
    "HeadSIONNormsModel": "HeadSIONNorm",
    "SIONExportModel": "SIONExport",
    "SIONImportModel": "SIONImport",
    "SionNormNote": "SIONNormNote",
    "SionNormCondition": "SIONNormCondition",
    "ProductDescriptionModel": "ProductDescription",
    "UnitPriceModel": "UnitPrice",
}
