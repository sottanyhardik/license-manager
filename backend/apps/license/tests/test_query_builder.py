from __future__ import annotations

import datetime as real_dt

import pytest
from django.db.models import Q

from apps.license.utils import query_builder
from apps.license.utils.query_builder import DateRangeHandler, LicenseQueryBuilder, QueryFilterBuilder


class FixedDateTime(real_dt.datetime):
    @classmethod
    def today(cls):
        return cls(2026, 7, 16, 12, 30, 45)


@pytest.fixture
def fixed_today(monkeypatch):
    monkeypatch.setattr(query_builder.dt, "datetime", FixedDateTime)
    return FixedDateTime.today()


def test_query_filter_builder_combines_and_or_and_exclude_filters():
    q_object = (
        QueryFilterBuilder()
        .add_and_filters({"purchase_status": "GE", "is_au": False})
        .add_or_filters({"exporter__name__icontains": ["Parle", "Britannia"]})
        .add_exclude_filters({"export_license__old_quantity": 0})
        .build()
    )

    expected = (
        Q(purchase_status="GE")
        & Q(is_au=False)
        & (Q(exporter__name__icontains="Parle") | Q(exporter__name__icontains="Britannia"))
        & ~Q(export_license__old_quantity=0)
    )

    assert q_object == expected


def test_query_filter_builder_or_falls_back_to_and_for_scalar_values():
    q_object = QueryFilterBuilder().add_or_filters({"purchase_status": "GE"}).build()

    assert q_object == Q(purchase_status="GE")


def test_query_filter_builder_excludes_multiple_icontains_values():
    q_object = (
        QueryFilterBuilder()
        .add_exclude_filters({"exporter__name__icontains": ["Demo", "Sample"]})
        .build()
    )

    assert q_object == ~(Q(exporter__name__icontains="Demo") | Q(exporter__name__icontains="Sample"))


def test_query_filter_builder_combines_and_groups_with_or():
    q_object = QueryFilterBuilder().add_and_or_filters([
        {"purchase_status": "GE", "is_au": False},
        {"purchase_status": "MI", "is_au": True},
    ]).build()

    expected = (
        (Q(purchase_status="GE") & Q(is_au=False))
        | (Q(purchase_status="MI") & Q(is_au=True))
    )

    assert q_object == expected


def test_empty_list_filters_are_noops():
    q_object = (
        QueryFilterBuilder()
        .add_or_filters({"exporter__name__icontains": []})
        .add_exclude_filters({"exporter__name__icontains": []})
        .build()
    )

    assert q_object == Q()


def test_date_range_parses_trimmed_boundaries():
    filters = DateRangeHandler.parse_date_range(
        {"start": " 2026-07-01 ", "end": "2026-07-31 "},
        field_name="license_date",
    )

    assert filters == {
        "license_date__gte": real_dt.datetime(2026, 7, 1),
        "license_date__lte": real_dt.datetime(2026, 7, 31),
    }


def test_date_range_ignores_blank_boundaries():
    assert DateRangeHandler.parse_date_range({"start": " ", "end": ""}) == {}


def test_date_range_preserves_invalid_date_failure():
    with pytest.raises(ValueError, match="does not match format"):
        DateRangeHandler.parse_date_range({"start": "2026-99-99"})


def test_date_range_default_uses_configured_offset(fixed_today):
    filters = DateRangeHandler.parse_date_range(default_offset_days=10)

    assert filters == {
        "license_expiry_date__gte": fixed_today - real_dt.timedelta(days=10),
    }


def test_expiry_filters_use_single_today_and_allow_zero_day_override(fixed_today):
    filters = DateRangeHandler.get_expiry_filters(expiry_days=0)

    assert filters == {
        "license_expiry_date__gte": fixed_today,
    }


def test_expired_filters_cover_sixty_day_window(fixed_today):
    filters = DateRangeHandler.get_expiry_filters(is_expired=True, expiry_days=15)

    assert filters == {
        "license_expiry_date__gte": fixed_today - real_dt.timedelta(days=60),
        "license_expiry_date__lte": fixed_today - real_dt.timedelta(days=15),
    }


class FakeQuerySet:
    def __init__(self):
        self.filtered_q_object = None
        self.ordering = None
        self.distinct_called = False

    def filter(self, q_object):
        self.filtered_q_object = q_object
        return self

    def order_by(self, *fields):
        self.ordering = fields
        return self

    def distinct(self):
        self.distinct_called = True
        return self


class FakeManager:
    def __init__(self):
        self.queryset = FakeQuerySet()

    def filter(self, q_object):
        return self.queryset.filter(q_object)


class FakeLicenseModel:
    objects = FakeManager()


def fresh_fake_license_model():
    FakeLicenseModel.objects = FakeManager()
    return FakeLicenseModel


def test_license_query_builder_applies_common_filters_ordering_and_distinct(fixed_today):
    fake_model = fresh_fake_license_model()

    queryset = (
        LicenseQueryBuilder(fake_model)
        .with_norm_class("E5")
        .with_purchase_status("GE")
        .with_is_au(False)
        .with_date_range({"start": "2026-07-01", "end": "2026-07-31"})
        .with_party(["Parle", "Britannia"])
        .exclude_party(["Blocked"])
        .order_by("license_expiry_date", "license_date")
        .build()
    )

    expected_filter = (
        Q(export_license__norm_class__norm_class="E5")
        & Q(purchase_status="GE")
        & Q(is_au=False)
        & Q(license_expiry_date__gte=real_dt.datetime(2026, 7, 1))
        & Q(license_expiry_date__lte=real_dt.datetime(2026, 7, 31))
        & (Q(exporter__name__icontains="Parle") | Q(exporter__name__icontains="Britannia"))
        & ~Q(exporter__name__icontains="Blocked")
    )

    assert queryset is fake_model.objects.queryset
    assert queryset.filtered_q_object == expected_filter
    assert queryset.ordering == ("license_expiry_date", "license_date")
    assert queryset.distinct_called is True


def test_license_query_builder_applies_base_and_expiry_filters(fixed_today, settings):
    settings.EXPIRY_DAY = 20
    fake_model = fresh_fake_license_model()

    queryset = (
        LicenseQueryBuilder(fake_model)
        .with_base_filters(is_active=True)
        .with_expiry_filters(is_expired=True, field_name="license_expiry_date")
        .build()
    )

    expected_filter = (
        Q(is_active=True)
        & Q(license_expiry_date__gte=fixed_today - real_dt.timedelta(days=60))
        & Q(license_expiry_date__lte=fixed_today - real_dt.timedelta(days=20))
    )

    assert queryset.filtered_q_object == expected_filter
    assert queryset.distinct_called is True
