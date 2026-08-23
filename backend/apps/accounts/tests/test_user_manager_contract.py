"""Regression coverage for the retired account/company relationship."""

import pytest

from apps.accounts.models import User
from apps.core.models import CompanyModel


@pytest.mark.django_db
def test_user_manager_rejects_retired_company_keyword():
    """Accounts migration 0004 removed ``User.company`` permanently.

    Accepting and silently discarding the keyword would make callers believe
    they had created a company-scoped account when no such authorization
    relation exists.
    """
    company = CompanyModel.objects.create(iec="9000000099", name="Retired relation test")

    with pytest.raises(TypeError, match="unexpected keyword arguments: 'company'"):
        User.objects.create_user(username="retired-company-keyword", company=company)
