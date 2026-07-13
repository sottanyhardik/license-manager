"""
Shared MDS-row builder for the 17 masters (ADR-001, Phase 6 write cutover).

ONE place that turns a local master instance into the flat, id-free dict the
Master-Data Service expects on ``bulk_upsert`` / ``delete_by_key``. It is used by
BOTH:

  1. ``export_masters_mds`` — the offline hydration exporter (builds the same row
     wrapped as ``{"key": ..., "data": ...}``), and
  2. ``MasterViewSet.perform_create/perform_update`` — the online write cutover,
     which POSTs the flat row straight to MDS.

Keeping the row shape in one function guarantees the online write payload is
byte-identical to what the offline exporter/loader already proved works — the
same natural key, the same FKs-as-parent-natural-keys, the same media-as-path,
and the same deterministic ``uid`` for the keyless masters.

Row shape (see MDS ``masters/serializers.py`` + ``bulk_upsert``):
- Every data field is at the TOP LEVEL of the dict (no nested ``data``).
- The natural key is present at the top level under its field name
  (``iec``/``code``/``hs_code``/``norm_class``/``name``/``date``, or ``uid`` for
  the 7 keyless masters).
- Each ForeignKey to ANOTHER registered master is emitted as
  ``<fk_name>: <parent's natural-key value>`` (a scalar), because the MDS
  serializer resolves FKs via ``SlugRelatedField(slug_field=<parent_nk>)`` — ids
  diverge across servers so only natural keys are portable (ADR Decision 2).
- Media (``ImageField``/``FileField``) is emitted as its stored path string
  (``FieldFile.name``), matching MDS's ``CharField`` media columns.
- Integer PKs, audit user FKs (``created_by``/``modified_by``), and timestamps
  are NEVER emitted (server-managed / non-portable).

The mapping of a consumer model_label -> (endpoint, natural_key, mds_model_label,
parent natural keys) comes from mds_client's ``DEFAULT_MDS_MODELS`` (a plain dict,
no Django import). It is read directly — NOT from ``settings.MDS_MODELS`` — because
the offline exporter (``export_masters_mds``) must build these rows even when
``MDS_ENABLED`` is false and ``MDS_MODELS`` is therefore unset. When the client
package is not installed, a byte-identical fallback mapping is used so ``core``
stays importable without it (mirroring the pattern in ``core/models.py``).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Tuple

from django.db import models

# Source of truth for the model_label -> {natural_key, endpoint, mds_model_label}
# mapping. Prefer the installed client's copy; fall back to a minimal inline map
# so the offline exporter works without mds_client (ADR-001; matches the tolerant
# import in apps/core/models.py).
try:  # pragma: no cover - exercised in both installed/uninstalled envs
    from mds_client.model_map import DEFAULT_MDS_MODELS as _MDS_MODELS
except ImportError:  # pragma: no cover - fallback keeps core importable w/o client
    # Minimal natural-key mapping for all 17 masters. Kept byte-identical to
    # mds_client.model_map.DEFAULT_MDS_MODELS for the fields this module reads.
    _MDS_MODELS = {
        "core.CompanyModel": {"natural_key": "iec"},
        "core.PortModel": {"natural_key": "code"},
        "core.ItemHeadModel": {"natural_key": "name"},
        "core.ItemGroupModel": {"natural_key": "name"},
        "core.ItemNameModel": {"natural_key": "name"},
        "core.HSCodeModel": {"natural_key": "hs_code"},
        "core.SionNormClassModel": {"natural_key": "norm_class"},
        "core.SchemeCode": {"natural_key": "code"},
        "core.NotificationNumber": {"natural_key": "code"},
        "core.ExchangeRateModel": {"natural_key": "date"},
        "core.HeadSIONNormsModel": {"natural_key": "uid"},
        "core.SIONExportModel": {"natural_key": "uid"},
        "core.SIONImportModel": {"natural_key": "uid"},
        "core.SionNormNote": {"natural_key": "uid"},
        "core.SionNormCondition": {"natural_key": "uid"},
        "core.ProductDescriptionModel": {"natural_key": "uid"},
        "core.UnitPriceModel": {"natural_key": "uid"},
    }


# Fields that are server-managed / non-portable and must never be sent to MDS.
# (MDS keeps its own PK + timestamps; audit user FKs point at a different, local
# user table that does not exist on MDS.)
_SKIP_FIELDS = frozenset(
    {
        "id",
        "pk",
        "created_by",
        "modified_by",
        "created_on",
        "modified_on",
    }
)


def _serialize_scalar(value: Any) -> Any:
    """JSON-safe, stable representation of a scalar field value.

    Matches ``export_masters_mds._serialize`` and ``mds_client.keys.serialize_scalar``
    so the online write payload equals the offline export payload byte-for-byte:
    dates/datetimes -> ISO 8601; Decimal -> ``str`` (preserves scale); else as-is.
    """
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _mds_models() -> Dict[str, dict]:
    """The model_label -> config mapping for all 17 masters (always available)."""
    return _MDS_MODELS


def _config_for_label(model_label: str) -> dict:
    cfg = _mds_models().get(model_label)
    if cfg is None:
        raise KeyError(
            f"{model_label!r} is not one of the 17 MDS masters; "
            "cannot build an MDS payload for it."
        )
    return cfg


def local_model_label(model: type[models.Model]) -> str:
    """The ``<app_label>.<ModelName>`` label used as the MDS_MODELS key."""
    return f"{model._meta.app_label}.{model.__name__}"


def _parent_natural_key_field(parent_model: type[models.Model]) -> str | None:
    """Natural-key field for a parent master, from MDS_MODELS, or None if the
    parent isn't a registered master (then the FK is left out of the payload —
    exactly as the exporter does, which only expresses FKs to OTHER masters)."""
    cfg = _mds_models().get(local_model_label(parent_model))
    return cfg.get("natural_key") if cfg else None


def build_row(instance: models.Model) -> Tuple[str, str, Dict[str, Any]]:
    """Build the flat MDS row for one local master instance.

    Returns ``(mds_model_label, natural_key_field, row)`` where:
    - ``mds_model_label`` is the model_label to pass to ``write_master`` /
      ``client.bulk_upsert`` (the mds_client resolves it to the endpoint), i.e.
      the CONSUMER model_label (mds_client keys its config off that);
    - ``natural_key_field`` is the field name of the natural key in ``row``;
    - ``row`` is the flat, id-free dict described in the module docstring.

    The natural key is always included (for keyless masters it is the instance's
    deterministic ``uid``, which ``SyntheticUidMixin.save`` has already computed).
    """
    model = type(instance)
    label = local_model_label(model)
    cfg = _config_for_label(label)
    natural_key = cfg["natural_key"]

    row: Dict[str, Any] = {}
    for field in model._meta.get_fields():
        if not getattr(field, "concrete", False):
            continue  # reverse relations, m2m handled elsewhere / not on masters
        name = field.name
        if name in _SKIP_FIELDS:
            continue

        if field.is_relation and field.many_to_one:
            # FK: emit the PARENT's natural-key value (scalar) under the FK name.
            parent_model = field.related_model
            parent_nk = _parent_natural_key_field(parent_model)
            if parent_nk is None:
                # Parent isn't a registered master (e.g. an audit user FK caught
                # above, or a non-master relation) — skip, like the exporter.
                continue
            parent_id = getattr(instance, field.attname)  # <fk>_id, no DB hit
            if parent_id is None:
                row[name] = None
            else:
                parent = getattr(instance, name)
                row[name] = getattr(parent, parent_nk)
            continue

        if isinstance(field, (models.ImageField, models.FileField)):
            fieldfile = getattr(instance, name)
            row[name] = fieldfile.name if fieldfile else ""
            continue

        row[name] = _serialize_scalar(getattr(instance, name))

    # Guarantee the natural key is present (uid for keyless masters lives in the
    # loop above already; this is belt-and-braces for any edge case).
    if natural_key not in row:
        row[natural_key] = _serialize_scalar(getattr(instance, natural_key))

    return label, natural_key, row


def natural_key_value(instance: models.Model) -> Tuple[str, str, Any]:
    """``(mds_model_label, natural_key_field, natural_key_value)`` for delete."""
    model = type(instance)
    label = local_model_label(model)
    cfg = _config_for_label(label)
    natural_key = cfg["natural_key"]
    value = _serialize_scalar(getattr(instance, natural_key))
    return label, natural_key, value


def build_export_record(instance: models.Model) -> Dict[str, Any]:
    """Build the offline-export record ``{"key": <nk>, "data": {...}}`` for one
    instance, reusing :func:`build_row` so the offline JSON and the online write
    payload derive from ONE codepath (identical scalar/media/FK handling).

    The only difference from the online row is key SHAPE: the offline
    ``load_masters`` loader reads FKs under ``<fk>__<parent_natural_key>`` (it
    resolves them manually), whereas the online MDS serializer reads the plain
    ``<fk>`` field. So here we rename each FK field to the ``__``-suffixed form
    and lift the natural key out into ``"key"`` — preserving the export contract
    that ``export_masters_mds`` / ``load_masters`` and their tests already rely on.
    """
    label, natural_key, row = build_row(instance)
    model = type(instance)

    # Map FK field name -> its ``<fk>__<parent_nk>`` export key.
    fk_rename: Dict[str, str] = {}
    for field in model._meta.get_fields():
        if getattr(field, "concrete", False) and field.is_relation and field.many_to_one:
            parent_nk = _parent_natural_key_field(field.related_model)
            if parent_nk is not None:
                fk_rename[field.name] = f"{field.name}__{parent_nk}"

    key_value = row.get(natural_key)
    data: Dict[str, Any] = {}
    for name, value in row.items():
        if name == natural_key and natural_key == "uid":
            # keyless masters carry the uid as the record "key", not in "data".
            continue
        data[fk_rename.get(name, name)] = value

    return {"key": key_value, "data": data}
