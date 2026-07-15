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


class UserManagementSerializer(serializers.ModelSerializer):
    """
    Full read/write serializer for admin user management.

    Supports:
    - Role assignment via list of role-code strings (Group names).
    - Password set on create; password update is opt-in on edit.
    - is_superuser / is_staff are writable only for actual superusers (enforced
      via get_fields).
    """

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    roles = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of role-code strings (Group names) to assign to this user.",
    )

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
            "password",
            "roles",
            "date_joined",
            "last_login",
        )
        read_only_fields = ("id", "date_joined", "last_login", "is_superuser", "is_staff")

    def get_fields(self):
        """Make is_superuser and is_staff writable only for actual superusers."""
        fields = super().get_fields()
        request = self.context.get("request")
        if request and getattr(request.user, "is_superuser", False):
            fields["is_superuser"].read_only = False
            fields["is_staff"].read_only = False
        return fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Replace the ListField write representation with the actual group names
        data["roles"] = instance.get_role_codes()
        return data

    def _sync_roles(self, user, role_codes):
        """Sync user's groups to exactly the given role codes."""
        from django.contrib.auth.models import Group
        groups = Group.objects.filter(name__in=role_codes)
        user.groups.set(groups)

    @staticmethod
    def _normalise(data):
        """Normalise fields before DB write — empty email → None (avoids unique constraint clash)."""
        if "email" in data and not data["email"]:
            data["email"] = None
        return data

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        role_codes = validated_data.pop("roles", None)

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
        password = validated_data.pop("password", None)
        role_codes = validated_data.pop("roles", None)

        self._normalise(validated_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()

        if role_codes is not None:
            self._sync_roles(instance, role_codes)
        return instance
