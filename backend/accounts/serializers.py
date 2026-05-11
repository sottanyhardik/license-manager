# FILE: accounts/serializers.py
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

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
    """Serializer for the /me endpoint — read-only snapshot of the current user."""
    roles = serializers.SerializerMethodField()
    is_staff = serializers.BooleanField(read_only=True)

    def get_roles(self, obj):
        return obj.get_role_codes()

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "first_name", "last_name",
            "is_active", "is_staff", "is_superuser", "roles", "date_joined",
        )
        read_only_fields = ("id", "date_joined", "is_superuser", "is_staff", "roles")


class UserManagementSerializer(serializers.ModelSerializer):
    """Serializer for admin user management — includes role assignment."""
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    roles = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of role-code strings (Group names) to assign to this user.",
    )

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "first_name", "last_name",
            "is_active", "is_staff", "is_superuser", "password", "roles", "date_joined",
        )
        read_only_fields = ("id", "date_joined", "is_superuser", "is_staff")

    def get_fields(self):
        """Make is_superuser and is_staff writable only for actual superusers."""
        fields = super().get_fields()
        request = self.context.get('request')
        if request and getattr(request.user, 'is_superuser', False):
            fields['is_superuser'].read_only = False
            fields['is_staff'].read_only = False
        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Replace the ListField write representation with the actual group names
        data['roles'] = instance.get_role_codes()
        return data

    def _sync_roles(self, user, role_codes):
        """Sync user's groups to exactly the given role codes."""
        groups = Group.objects.filter(name__in=role_codes)
        user.groups.set(groups)

    @staticmethod
    def _normalise(data):
        """Normalise fields before DB write — empty email → None (avoids unique constraint clash)."""
        if 'email' in data and not data['email']:
            data['email'] = None
        return data

    def create(self, validated_data):
        password   = validated_data.pop('password', None)
        role_codes = validated_data.pop('roles', None)

        self._normalise(validated_data)

        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()

        if role_codes is not None:
            self._sync_roles(user, role_codes)
        return user

    def update(self, instance, validated_data):
        password   = validated_data.pop('password', None)
        role_codes = validated_data.pop('roles', None)

        self._normalise(validated_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()

        if role_codes is not None:
            self._sync_roles(instance, role_codes)
        return instance
