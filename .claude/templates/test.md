# Template — Tests (pytest)

Config: `backend/pytest.ini`. Files `test_*.py`, classes `Test*`, functions `test_*`.
Mark appropriately (`unit`/`api`/`integration`/`database`/`slow`). Rule: `.claude/rules/testing.md`.

## API test

```python
import pytest

@pytest.mark.api
@pytest.mark.django_db
class TestWidgetEndpoints:
    def test_list_requires_auth(self, client):
        assert client.get("/api/widgets/").status_code in (401, 403)

    def test_create_widget(self, auth_client, company):
        resp = auth_client.post("/api/widgets/", {"name": "W1", "company": company.id})
        assert resp.status_code == 201
        assert resp.json()["name"] == "W1"

    def test_forbidden_role_blocked(self, low_priv_client):
        assert low_priv_client.post("/api/widgets/", {"name": "X"}).status_code == 403
```

## Unit / business-logic test

```python
import pytest

@pytest.mark.unit
@pytest.mark.django_db
class TestBalanceDebit:
    def test_debit_reduces_materialised_balance(self, license_with_balance):
        before = license_with_balance.balance.available
        debit_license(license_with_balance, amount=100)   # use the real recalc path
        license_with_balance.balance.refresh_from_db()
        assert license_with_balance.balance.available == before - 100

    def test_cannot_overdraw(self, license_with_balance):
        with pytest.raises(ValidationError):
            debit_license(license_with_balance, amount=10**9)
```

Regression tests for bug fixes: write the failing case first (see `.claude/prompts/bugfix.md`).
Reuse existing fixtures — grep `backend/tests/` and any `conftest.py` before defining new ones.
