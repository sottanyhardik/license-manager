import pytest
from django.db.models.signals import post_save

from apps.core import cache_signals
from apps.core.models import CompanyModel


@pytest.mark.django_db
def test_disable_cache_invalidation_temporarily_disconnects_registered_receivers(monkeypatch):
    invalidated_patterns = []

    monkeypatch.setattr(
        cache_signals,
        "invalidate_cache",
        invalidated_patterns.append,
    )

    company = CompanyModel(iec="IEC1234567", name="Acme")

    post_save.send(sender=CompanyModel, instance=company, created=True)
    assert invalidated_patterns == [
        "view:company*",
        "view:license*company*",
        "view:boe*company*",
        "view:allotment*company*",
    ]

    invalidated_patterns.clear()
    with cache_signals.disable_cache_invalidation():
        post_save.send(sender=CompanyModel, instance=company, created=False)
    assert invalidated_patterns == []

    post_save.send(sender=CompanyModel, instance=company, created=False)
    assert invalidated_patterns == [
        "view:company*",
        "view:license*company*",
        "view:boe*company*",
        "view:allotment*company*",
    ]
