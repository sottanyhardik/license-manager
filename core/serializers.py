# core/serializers.py
from rest_framework import serializers
from .models import CompanyModel, PortModel
from core.models import HSCodeModel, ItemNameModel, SionNormClassModel

# Simple serializers for select endpoints


class CompanySimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyModel
        fields = ("id", "name")


class PortSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortModel
        fields = ("id", "code", "name")


class ItemNameSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemNameModel
        fields = ("id", "name")


class HSCodeSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = HSCodeModel
        fields = ("id", "hs_code", "product_description")


class NormClassSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SionNormClassModel
        fields = ("id", "norm_class", "description")
