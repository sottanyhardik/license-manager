from rest_framework import serializers

from .models import MASTER_REGISTRY, MasterChange

# model -> its natural-key field, from the registry (drives FK-by-natural-key).
_NATURAL_KEY_BY_MODEL = {model: nk for model, nk, _ in MASTER_REGISTRY}


def _fk_natural_key_fields(model):
    """For each ForeignKey on ``model`` whose TARGET is itself a registered
    master, build a ``SlugRelatedField`` that reads/writes the parent by its
    NATURAL KEY instead of its raw integer id.

    Why: ids diverge across servers (ADR-001 Decision 2), so a mirror consumer
    must resolve FKs by the parent's stable business key, never by id. Emitting
    FKs as natural keys makes the payload portable and lets the consumer sync
    resolve them locally. Nullable FKs stay ``allow_null``.
    """
    extra = {}
    for field in model._meta.get_fields():
        if not (field.is_relation and field.many_to_one and field.concrete):
            continue
        parent = field.related_model
        parent_nk = _NATURAL_KEY_BY_MODEL.get(parent)
        if not parent_nk:
            continue  # target isn't a registered master — leave as default
        extra[field.name] = serializers.SlugRelatedField(
            slug_field=parent_nk,
            queryset=parent.objects.all(),
            required=not field.null,
            allow_null=field.null,
        )
    return extra


def _make_serializer(model):
    meta = type("Meta", (), {"model": model, "fields": "__all__"})
    attrs = {"Meta": meta, **_fk_natural_key_fields(model)}
    # Keyless masters key on `uid`, which is model-level editable=False (so the
    # ORM never lets a user edit it). But the DETERMINISTIC uid MUST be written
    # through the API verbatim (it is the natural key that drives convergence —
    # ADR-001 Decision 6), so expose it as a writable serializer field for the
    # models that use it as their natural key. Not required on update.
    if _NATURAL_KEY_BY_MODEL.get(model) == "uid":
        attrs["uid"] = serializers.UUIDField(required=False)
    return type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), attrs)


# One ModelSerializer per master, generated from the registry.
SERIALIZERS = {model: _make_serializer(model) for model, _, _ in MASTER_REGISTRY}


class MasterChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MasterChange
        fields = ["id", "model_label", "natural_key", "op", "at"]
