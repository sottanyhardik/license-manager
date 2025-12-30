# FILE: accounts/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from . import services
from .models import Role

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model"""
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ('id', 'code', 'name', 'description', 'is_active', 'user_count', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_user_count(self, obj):
        return obj.users.filter(is_active=True).count()


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
    roles = RoleSerializer(many=True, read_only=True)
    role_codes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "roles", "role_codes", "is_active", "is_superuser", "date_joined")
        read_only_fields = ("id", "date_joined", "is_superuser")

    def get_role_codes(self, obj):
        return obj.get_role_codes()


class UserManagementSerializer(serializers.ModelSerializer):
    """Serializer for admin user management"""
    password = serializers.CharField(write_only=True, required=False)
    roles = RoleSerializer(many=True, read_only=True)
    role_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of role IDs to assign to the user"
    )
    role_codes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "roles", "role_ids", "role_codes", "is_active", "is_staff", "is_superuser", "password", "date_joined")
        read_only_fields = ("id", "date_joined")

    def get_role_codes(self, obj):
        return obj.get_role_codes()

    def create(self, validated_data):
        role_ids = validated_data.pop('role_ids', [])
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()

        # Assign roles
        if role_ids:
            user.roles.set(role_ids)

        return user

    def update(self, instance, validated_data):
        role_ids = validated_data.pop('role_ids', None)
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()

        # Update roles if provided
        if role_ids is not None:
            instance.roles.set(role_ids)

        return instance


class UserRoleAssignmentSerializer(serializers.Serializer):
    """Serializer for assigning/removing roles from users"""
    user_id = serializers.IntegerField()
    role_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of role IDs to assign to the user"
    )

    def validate_user_id(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User not found")
        return value

    def validate_role_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one role must be provided")

        existing_roles = Role.objects.filter(id__in=value, is_active=True).count()
        if existing_roles != len(value):
            raise serializers.ValidationError("One or more roles are invalid or inactive")

        return value
