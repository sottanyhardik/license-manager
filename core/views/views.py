# core/views.py
from .master_view import MasterViewSet
from ..models import (
    CompanyModel,
    PortModel,
    HSCodeModel,
    HeadSIONNormsModel,
    SionNormClassModel,
    SIONExportModel,
    SIONImportModel,
    HSCodeDutyModel,
    ProductDescriptionModel,
    UnitPriceModel,
)
from ..serializers import (
    CompanySerializer,
    PortSerializer,
    HSCodeSerializer,
    HeadSIONNormsSerializer,
    SionNormClassNestedSerializer,
    SIONExportSerializer,
    SIONImportSerializer,
    HSCodeDutySerializer,
    ProductDescriptionSerializer,
    UnitPriceSerializer,
)
from django.db import models as dj_models
from typing import List

# Base API prefix used to construct select endpoints (adjust if needed).
API_PREFIX = "/masters/"


def choose_label_field(related_model):
    """
    Pick a sensible display field for a related model.
    Preference order: name, title, label, display, id
    """
    candidates = ["name", "title", "label", "display", "id"]
    model_fields = {f.name for f in related_model._meta.get_fields()}
    for c in candidates:
        if c in model_fields:
            return c
    return "id"


def to_kebab(s: str) -> str:
    """
    Convert snake_case or underscores to kebab-case.
    """
    return s.replace("_", "-").lower()


def build_endpoint_candidates(rel_model) -> List[str]:
    """
    Return a list of plausible endpoints (strings ending with '/')
    for a related model, ordered by preference.
    """
    raw_name = getattr(rel_model._meta, "model_name", None) or getattr(rel_model._meta, "object_name", None) or rel_model.__name__
    raw_name = str(raw_name).lower()
    plural = raw_name if raw_name.endswith("s") else f"{raw_name}s"
    kebab = to_kebab(raw_name)
    kebab_plural = kebab if kebab.endswith("s") else f"{kebab}s"

    candidates = [
        f"{API_PREFIX}{raw_name}/",
        f"{API_PREFIX}{plural}/",
        f"{API_PREFIX}{kebab}/",
        f"{API_PREFIX}{kebab_plural}/",
    ]

    # remove duplicates preserving order
    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def enhance_config_with_fk(model_cls, config):
    """
    Inspect model_cls for ForeignKey fields and populate config['field_meta']
    with select metadata for each FK. Also annotate nested_field_defs entries
    with fk_endpoint(s) & label_field when field names match.

    Returns a shallow-copied config dict with 'field_meta' added/updated.
    """
    cfg = dict(config) if config is not None else {}
    field_meta = dict(cfg.get("field_meta", {}))
    nested_defs = dict(cfg.get("nested_field_defs", {}))

    for f in model_cls._meta.get_fields():
        if not isinstance(f, dj_models.ForeignKey):
            continue

        fk_name = f.name
        rel_model = f.remote_field.model
        label_field = choose_label_field(rel_model)
        endpoints = build_endpoint_candidates(rel_model)
        preferred = endpoints[0] if endpoints else None

        # Provide both a preferred 'endpoint' and an 'endpoints' list for robustness
        field_meta[fk_name] = {
            "type": "select",
            "endpoint": preferred,
            "endpoints": endpoints,
            "label_field": label_field,
        }

        # Annotate nested_field_defs entries that reference this fk_name
        for nd_key, nd_list in nested_defs.items():
            if not isinstance(nd_list, list):
                continue
            new_list = []
            changed = False
            for entry in nd_list:
                entry_copy = dict(entry)
                if entry_copy.get("name") == fk_name:
                    # Use setdefault so explicit nested defs in config (like our hsn_code override) are preserved
                    entry_copy.setdefault("fk_endpoint", preferred)
                    entry_copy.setdefault("endpoints", endpoints)
                    entry_copy.setdefault("label_field", label_field)
                    changed = True
                new_list.append(entry_copy)
            if changed:
                nested_defs[nd_key] = new_list

    cfg["field_meta"] = field_meta
    if nested_defs:
        cfg["nested_field_defs"] = nested_defs

    return cfg


# ------------------------------
# ViewSet registrations
# ------------------------------
CompanyViewSet = MasterViewSet.create(
    CompanyModel,
    CompanySerializer,
    config=enhance_config_with_fk(
        CompanyModel,
        {
            "search": ["iec", "name"],
            "filter": ["iec", "gst_number"],
            "list_display": ["iec", "name", "gst_number"],
            "form_fields": ["iec", "name", "gst_number", "email"],
        },
    ),
)

PortViewSet = MasterViewSet.create(
    PortModel,
    PortSerializer,
    config=enhance_config_with_fk(
        PortModel,
        {
            "search": ["code", "name"],
            "filter": [],
            "list_display": ["code", "name"],
            "form_fields": ["code", "name"],
        },
    ),
)

HSCodeViewSet = MasterViewSet.create(
    HSCodeModel,
    HSCodeSerializer,
    config=enhance_config_with_fk(
        HSCodeModel,
        {
            "search": ["hs_code", "product_description"],
            "filter": [],
            "list_display": ["hs_code", "product_description", "unit_price", "unit"],
            "form_fields": ["hs_code", "product_description", "unit_price", "basic_duty", "unit", "policy"],
        },
    ),
)

HeadSIONNormsViewSet = MasterViewSet.create(
    HeadSIONNormsModel,
    HeadSIONNormsSerializer,
    config=enhance_config_with_fk(
        HeadSIONNormsModel,
        {
            "search": ["name"],
            "list_display": ["id", "name"],
            "form_fields": ["name"],
        },
    ),
)


# Example nested defs — we explicitly mark hsn_code as a select and point it at /api/head-norms/
example_nested_field_defs = {
    "export_norm": [
        {"name": "id", "type": "integer", "label": "ID", "required": True},
        {"name": "description", "type": "string", "label": "Description", "required": True},
        {"name": "quantity", "type": "number", "label": "Quantity", "required": True},
        {"name": "unit", "type": "string", "label": "Unit", "required": True},
    ],
    "import_norm": [
        {"name": "id", "type": "integer", "label": "ID", "required": True},
        {"name": "description", "type": "string", "label": "Description", "required": True},
        {"name": "quantity", "type": "number", "label": "Quantity", "required": True},
        {"name": "unit", "type": "string", "label": "Unit", "required": True},
        # <-- explicit override: treat hsn_code as FK select pointing to head-norms router
        {
            "name": "hsn_code",
            "type": "string",
            "label": "HSN Code",
            "required": False,
            "fk_endpoint": f"{API_PREFIX}hs-codes/",               # preferred single endpoint
            "endpoints": [f"{API_PREFIX}hs-codes/"],               # alternatives (here only one)
            "label_field": "hsn_code",
        },
    ],
}

SionNormClassViewSet = MasterViewSet.create(
    SionNormClassModel,
    SionNormClassNestedSerializer,
    config=enhance_config_with_fk(
        SionNormClassModel,
        {
            "search": ["norm_class", "description"],
            "filter": [],
            "list_display": ["norm_class", "description", "head_norm_name"],
            "form_fields": ["norm_class", "description", "head_norm"],
            "nested_field_defs": example_nested_field_defs,
        },
    ),
)


SIONExportViewSet = MasterViewSet.create(
    SIONExportModel,
    SIONExportSerializer,
    config=enhance_config_with_fk(
        SIONExportModel,
        {
            "search": [],
            "filter": [],
            "list_display": ["id"],
            "form_fields": [],
        },
    ),
)


SIONImportViewSet = MasterViewSet.create(
    SIONImportModel,
    SIONImportSerializer,
    config=enhance_config_with_fk(
        SIONImportModel,
        {
            "search": [],
            "filter": [],
            "list_display": ["id"],
            "form_fields": [],
        },
    ),
)


HSCodeDutyViewSet = MasterViewSet.create(
    HSCodeDutyModel,
    HSCodeDutySerializer,
    config=enhance_config_with_fk(HSCodeDutyModel, {"form_fields": ["hs_code"]}),
)

ProductDescriptionViewSet = MasterViewSet.create(
    ProductDescriptionModel,
    ProductDescriptionSerializer,
    config=enhance_config_with_fk(ProductDescriptionModel, {"form_fields": ["product_description"]}),
)

UnitPriceViewSet = MasterViewSet.create(
    UnitPriceModel,
    UnitPriceSerializer,
    config=enhance_config_with_fk(UnitPriceModel, {"form_fields": ["name", "label"]}),
)
