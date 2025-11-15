# FILE: accounts/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from . import services

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "password_confirm", "first_name", "last_name")

    def validate(self, attrs):
        pwd = attrs.get("password")
        pwdc = attrs.pop("password_confirm", None)
        if pwdc is not None and pwd != pwdc:
            raise serializers.ValidationError({"password_confirm": "Password confirmation does not match."})
        validate_password(pwd)
        return attrs

    def create(self, validated_data):
        return services.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "role", "is_staff", "is_superuser")
        read_only_fields = ("id", "username")

    def get_role(self, obj):
        """Determine user role based on permissions"""
        if obj.is_superuser:
            return "admin"
        elif obj.is_staff:
            return "manager"
        return "viewer"
