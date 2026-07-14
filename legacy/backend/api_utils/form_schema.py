# api_utils/form_schema.py
from typing import Dict, Any, List
from django.db import models

FIELD_TYPE_MAP = {
    models.CharField: "text",
    models.TextField: "textarea",
    models.IntegerField: "number",
    models.FloatField: "number",
    models.DecimalField: "number",
    models.BooleanField: "checkbox",
    models.DateField: "date",
    models.DateTimeField: "datetime",
    models.ForeignKey: "select",
    models.ManyToManyField: "multiselect",
}


def resolve_field_type(field: models.Field) -> str:
    for django_field, form_type in FIELD_TYPE_MAP.items():
        if isinstance(field, django_field):
            return form_type
    return "text"


def collect_choices(field: models.Field) -> List[Dict[str, Any]]:
    if getattr(field, "choices", None):
        return [{"value": c[0], "label": c[1]} for c in field.choices]
    return []


def model_to_form_schema(model_cls, include: list = None, exclude: list = None) -> Dict[str, Any]:
    exclude = exclude or []
    include = include or None
    meta = model_cls._meta
    schema = {"model": f"{meta.app_label}.{meta.object_name}", "fields": []}
    for field in meta.get_fields():
        if getattr(field, "auto_created", False) and not getattr(field, "concrete", True):
            continue
        name = getattr(field, "name", None)
        if not name:
            continue
        if include is not None and name not in include:
            continue
        if name in exclude:
            continue
        if getattr(field, "one_to_many", False) and getattr(field, "auto_created", False):
            continue

        field_type = resolve_field_type(field)
        required = not (getattr(field, "null", False) or getattr(field, "blank", False))
        entry = {
            "name": name,
            "label": str(getattr(field, "verbose_name", name)).title(),
            "type": field_type,
            "required": required,
            "help_text": getattr(field, "help_text", ""),
            "choices": collect_choices(field),
        }

        if field_type in ("select", "multiselect"):
            rel = getattr(field, "related_model", None)
            if rel is not None:
                entry["related_model"] = f"{rel._meta.app_label}.{rel._meta.object_name}"
                entry["options_endpoint"] = f"/core/{rel._meta.model_name}s/"
        schema["fields"].append(entry)
    return schema
