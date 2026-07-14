# accounts/serializers.py
"""
Serializers for the accounts app.

LoginSerializer       — validates username/password, returns tokens + user data
UserSerializer        — read-only snapshot for /me
TokenRefreshSerializer — thin wrapper; actual rotation handled by SimpleJWT
"""
from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    """Validate login credentials and return the authenticated User."""

    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")

        if not username or not password:
            raise serializers.ValidationError("Both username and password are required.")

        user = authenticate(
            request=self.context.get("request"),
            username=username,
            password=password,
        )

        if not user or not user.is_active:
            raise serializers.ValidationError("Invalid credentials.")

        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """Read-only snapshot of the authenticated user — used for /me and login response."""

    roles = serializers.SerializerMethodField()
    is_staff = serializers.BooleanField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "roles",
            "date_joined",
        )
        read_only_fields = ("id", "date_joined", "is_staff", "is_superuser", "roles")

    def get_roles(self, obj) -> list:
        return obj.get_role_codes()


class UsersListSerializer(serializers.ModelSerializer):
    """Serializer for the admin users list endpoint — includes role codes."""

    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "roles",
            "date_joined",
        )
        read_only_fields = fields

    def get_roles(self, obj) -> list:
        return obj.get_role_codes()
