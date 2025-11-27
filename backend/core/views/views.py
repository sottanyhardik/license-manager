from typing import List

from django.db import models as dj_models

from .master_view import MasterViewSet
from ..models import (
    CompanyModel,
    PortModel,
    HSCodeModel,
    HeadSIONNormsModel,
    SionNormClassModel,
    SIONExportModel,
    SIONImportModel,
    ProductDescriptionModel,
    UnitPriceModel,
    ItemNameModel,
    ItemHeadModel,
)
from ..serializers import (
    CompanySerializer,
    PortSerializer,
    HSCodeSerializer,
    HeadSIONNormsSerializer,
    SionNormClassNestedSerializer,
    SIONExportSerializer,
    SIONImportSerializer,
    ProductDescriptionSerializer,
    UnitPriceSerializer,
    ItemNameSerializer,
    ItemHeadSerializer,
)

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
    raw_name = getattr(rel_model._meta, "model_name", None) or getattr(rel_model._meta, "object_name",
                                                                       None) or rel_model.__name__
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


def enhance_config_with_fk(model_cls, config=None):
    """
    Inspect model_cls for ForeignKey fields and populate config['field_meta']
    with select metadata for each FK. Also annotate nested_field_defs entries
    with fk_endpoint(s) & label_field when field names match.

    Accepts (via `config` dict) optional keys:
      - api_prefix: string override for base API prefix (defaults to module-level API_PREFIX)
      - fk_endpoint_overrides: { fk_name: endpoint_string | [endpoint_strings] }
      - label_field_overrides: { fk_name: label_field_string }
      - ignore_fk_names: iterable of fk names to ignore (defaults to {'created_by','modified_by'})

    Returns a shallow-copied config dict with 'field_meta' added/updated.
    """
    cfg = dict(config) if config is not None else {}
    field_meta = dict(cfg.get("field_meta", {}))
    nested_defs = dict(cfg.get("nested_field_defs", {}))

    # customizable options
    api_prefix = cfg.get("api_prefix", API_PREFIX)
    fk_overrides = cfg.get("fk_endpoint_overrides", {}) or {}
    label_overrides = cfg.get("label_field_overrides", {}) or {}
    ignore_fk_names = set(cfg.get("ignore_fk_names", {"created_by", "modified_by"}))

    def build_candidates_for_rel(rel_model):
        """
        Local wrapper so api_prefix in config is honored.
        """
        raw_name = getattr(rel_model._meta, "model_name", None) or getattr(rel_model._meta, "object_name",
                                                                           None) or rel_model.__name__
        raw_name = str(raw_name).lower()
        plural = raw_name if raw_name.endswith("s") else f"{raw_name}s"
        kebab = raw_name.replace("_", "-")
        kebab_plural = kebab if kebab.endswith("s") else f"{kebab}s"

        candidates = [
            f"{api_prefix}{raw_name}/",
            f"{api_prefix}{plural}/",
            f"{api_prefix}{kebab}/",
            f"{api_prefix}{kebab_plural}/",
        ]

        seen = set()
        out = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    for f in model_cls._meta.get_fields():
        if not isinstance(f, dj_models.ForeignKey):
            continue

        fk_name = f.name

        # Skip any explicitly ignored audit (or other) fields
        if fk_name in ignore_fk_names:
            continue

        rel_model = f.remote_field.model

        # label field override or auto-choose
        label_field = label_overrides.get(fk_name) or choose_label_field(rel_model)

        # endpoint override handling (string or list)
        if fk_name in fk_overrides:
            override = fk_overrides[fk_name]
            if isinstance(override, (list, tuple)):
                endpoints = list(override)
            else:
                endpoints = [str(override)]
            preferred = endpoints[0] if endpoints else None
        else:
            endpoints = build_candidates_for_rel(rel_model)
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
                    # Use setdefault so explicit nested defs in config are preserved
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
CompanyViewSet = MasterViewSet.create_viewset(
    CompanyModel,
    CompanySerializer,
    config=enhance_config_with_fk(
        CompanyModel,
        {
            "search": ["iec", "name", "gst_number", "pan"],
            "filter": {
                "created_on": {"type": "date_range"},
            },
            "list_display": ["modified_on", "iec", "name", "pan", "gst_number", "address_line_1", "address_line_2"],
            "form_fields": [
                "name",
                "iec",
                "pan",
                "gst_number",
                "address",
                "address_line_1",
                "address_line_2",
                "logo",
                "signature",
                "stamp",
                "bill_colour",
                "bank_account_number",
                "bank_name",
                "ifsc_code",
                "account_type"
            ],
            "field_meta": {
                "account_type": {
                    "type": "select",
                    "choices": [
                        ("SAVINGS", "Savings"),
                        ("CURRENT", "Current"),
                        ("OD", "Overdraft"),
                    ]
                }
            }
        },
    ),
)

PortViewSet = MasterViewSet.create_viewset(
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

HSCodeViewSet = MasterViewSet.create_viewset(
    HSCodeModel,
    HSCodeSerializer,
    config=enhance_config_with_fk(
        HSCodeModel,
        {
            "search": ["hs_code", "product_description"],
            "filter": {
                "unit_price": {"type": "range"},
            },
            "list_display": ["hs_code", "product_description", "unit_price", "unit"],
            "form_fields": ["hs_code", "product_description", "unit_price", "basic_duty", "unit", "policy"],
        },
    ),
)

HeadSIONNormsViewSet = MasterViewSet.create_viewset(
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

# Example nested defs — we explicitly mark hs_code as a select and point it at /api/head-norms/
example_nested_field_defs = {
    "export_norm": [
        {"name": "id", "type": "integer", "label": "ID", "required": True},
        {"name": "description", "type": "string", "label": "Description", "required": True},
        {"name": "quantity", "type": "number", "label": "Quantity", "required": True},
        {"name": "unit", "type": "string", "label": "Unit", "required": True},
    ],
    "import_norm": [
        {"name": "id", "type": "integer", "label": "ID", "required": True},
        {"name": "serial_number", "type": "number", "label": "Serial Number", "required": True},
        {"name": "description", "type": "string", "label": "Description", "required": True},
        {"name": "quantity", "type": "number", "label": "Quantity", "required": True},
        {"name": "unit", "type": "string", "label": "Unit", "required": True},
        # <-- explicit override: treat hsn_code as FK select pointing to hs-codes router
        {
            "name": "hsn_code",
            "type": "string",
            "label": "HSN Code",
            "required": False,
            "fk_endpoint": f"{API_PREFIX}hs-codes/",  # preferred single endpoint
            "endpoints": [f"{API_PREFIX}hs-codes/"],  # alternatives (here only one)
            "label_field": "hs_code",  # Use hs_code field as label, not id
        },
    ],
}

SionNormClassViewSet = MasterViewSet.create_viewset(
    SionNormClassModel,
    SionNormClassNestedSerializer,
    config=enhance_config_with_fk(
        SionNormClassModel,
        {
            "search": ["norm_class", "description", "import_norm__description", "export_norm__description"],
            "filter": {
                "head_norm": {"type": "fk", "fk_endpoint": "/masters/head-norms/", "label_field": "name"},
                "is_active": {"type": "boolean", "default": True},
            },
            "list_display": ["norm_class", "description", "head_norm_name", "is_active"],
            "form_fields": ["norm_class", "description", "head_norm", "is_active"],
            "fk_endpoint_overrides": {
                "head_norm": "/masters/head-norms/"
            },
            "nested_field_defs": example_nested_field_defs,
            "default_filters": {"is_active": True},
        },
    ),
)

SIONExportViewSet = MasterViewSet.create_viewset(
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

SIONImportViewSet = MasterViewSet.create_viewset(
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

ProductDescriptionViewSet = MasterViewSet.create_viewset(
    ProductDescriptionModel,
    ProductDescriptionSerializer,
    config=enhance_config_with_fk(
        ProductDescriptionModel,
        {
            "form_fields": ["product_description"],
            "search": ["product_description"],
            "filter": {
                "hs_code": {"type": "exact"},
                "product_description": {"type": "icontains"},
            }
        }
    ),
)

UnitPriceViewSet = MasterViewSet.create_viewset(
    UnitPriceModel,
    UnitPriceSerializer,
    config=enhance_config_with_fk(UnitPriceModel, {"form_fields": ["name", "label"]}),
)

ItemHeadViewSet = MasterViewSet.create_viewset(
    ItemHeadModel,
    ItemHeadSerializer,
    config=enhance_config_with_fk(
        ItemHeadModel,
        {

            "search": ["name"],
            "filter": {
                "is_restricted": {"type": "exact"},
            },
            "list_display": ["name", "unit_rate", "is_restricted", "restriction_norm", "restriction_percentage"],
            "form_fields": ["name", "unit_rate", "is_restricted", "restriction_norm", "restriction_percentage", "dict_key"],
            "fk_endpoint_overrides": {
                "restriction_norm": "/masters/sion-classes/"
            },
            "label_field_overrides": {
                "restriction_norm": "norm_class"
            },
        }
    ),
)

ItemNameViewSet = MasterViewSet.create_viewset(
    ItemNameModel,
    ItemNameSerializer,
    config=enhance_config_with_fk(
        ItemNameModel,
        {
            "search": ["name", "head__name", "sion_norm_class__norm_class"],
            "filter": {
                "head": {"type": "fk", "fk_endpoint": "/masters/item-heads/", "label_field": "name"},
                "is_active": {"type": "exact"},
                "sion_norm_class": {
                    "type": "fk",
                    "fk_endpoint": "/masters/sion-classes/?is_active=true",
                    "label_field": "norm_class",
                    "display_field": "label",
                    "async": True
                },
            },
            "list_display": ["head__name", "name", "unit_price", "sion_norm_class_label", "restriction_percentage"],
            "form_fields": ["head", "name", "unit_price", "is_active", "sion_norm_class", "restriction_percentage"],
            "fk_endpoint_overrides": {
                "head": "/masters/item-heads/",
                "sion_norm_class": "/masters/sion-classes/?is_active=true"
            },
            "label_field_overrides": {
                "sion_norm_class": "norm_class"
            },
            "ordering": ["head__name", "name"]
        }
    ),
)
