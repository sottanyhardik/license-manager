from rest_framework import serializers

from .models import MASTER_REGISTRY, MasterChange


def _make_serializer(model):
    meta = type("Meta", (), {"model": model, "fields": "__all__"})
    return type(f"{model.__name__}Serializer", (serializers.ModelSerializer,), {"Meta": meta})


# One ModelSerializer per master, generated from the registry.
SERIALIZERS = {model: _make_serializer(model) for model, _, _ in MASTER_REGISTRY}


class MasterChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MasterChange
        fields = ["id", "model_label", "natural_key", "op", "at"]
