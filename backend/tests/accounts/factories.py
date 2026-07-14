# tests/accounts/factories.py
"""
factory_boy factories for the accounts app test suite.

UserFactory creates an active, ordinary user by default.
Specialised traits: staff, superuser, inactive.
"""
import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Default: active, non-staff, non-superuser."""

    class Meta:
        model = User
        skip_postgeneration_save = True  # factory_boy >= 3.3

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    is_staff = False
    is_superuser = False
    password = factory.PostGenerationMethodCall("set_password", "testpassword123")

    class Params:
        staff = factory.Trait(is_staff=True)
        superuser = factory.Trait(is_staff=True, is_superuser=True)
        inactive = factory.Trait(is_active=False)


class GroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Group
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"ROLE_{n}")
