from rest_framework import serializers

from .models import Company, ExchangeRate, MasterChange, Port


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = "__all__"


class PortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Port
        fields = "__all__"


class ExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRate
        fields = "__all__"


class MasterChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MasterChange
        fields = ["id", "model_label", "natural_key", "op", "at"]
