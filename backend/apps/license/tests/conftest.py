"""
SION-specific fixtures for planning tests.

Provides reusable database configurations, profiles, rules, and import items
for all planning-related tests. Enables conversion from legacy planner tests
to generic engine tests.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.core.models import CompanyModel, HSCodeModel, PortModel, SionNormClassModel
from apps.license.models import (
    LicenseDetailsModel,
    LicenseImportItemsModel,
    SionPlanningProfile,
    SionPlanningRule,
)
from apps.license.services.sion_planner_config.importer import import_e1_e5_profiles


# ============================================================================
# SION Norm Fixtures
# ============================================================================


@pytest.fixture
def e1_sion(db):
    """Fetch or create the E1 SION norm class."""
    sion, _ = SionNormClassModel.objects.get_or_create(
        code="E1",
        defaults={"name": "E1 - Confectionery", "is_active": True},
    )
    return sion


@pytest.fixture
def e5_sion(db):
    """Fetch or create the E5 SION norm class."""
    sion, _ = SionNormClassModel.objects.get_or_create(
        code="E5",
        defaults={"name": "E5 - Milk Products", "is_active": True},
    )
    return sion


@pytest.fixture
def e126_sion(db):
    """Fetch or create the E126 SION norm class."""
    sion, _ = SionNormClassModel.objects.get_or_create(
        code="E126",
        defaults={"name": "E126 - Other", "is_active": True},
    )
    return sion


@pytest.fixture
def e132_sion(db):
    """Fetch or create the E132 SION norm class."""
    sion, _ = SionNormClassModel.objects.get_or_create(
        code="E132",
        defaults={"name": "E132 - Coal", "is_active": True},
    )
    return sion


@pytest.fixture
def a3627_sion(db):
    """Fetch or create the A3627 SION norm class."""
    sion, _ = SionNormClassModel.objects.get_or_create(
        code="A3627",
        defaults={"name": "A3627 - Minerals", "is_active": True},
    )
    return sion


# ============================================================================
# E1 Fixtures
# ============================================================================


@pytest.fixture
def e1_profile(db, e1_sion):
    """Create or fetch E1 planning profile."""
    import_e1_e5_profiles(activate=True)
    profile = SionPlanningProfile.objects.filter(sion=e1_sion).first()
    if not profile:
        profile = SionPlanningProfile.objects.create(
            sion=e1_sion,
            name="E1 Test Profile",
            version=1,
            is_active=True,
        )
    return profile


@pytest.fixture
def e1_rules(db, e1_sion):
    """Get or create active E1 planning rules."""
    import_e1_e5_profiles(activate=True)
    rules = SionPlanningRule.objects.filter(sion=e1_sion, is_active=True).order_by(
        "priority"
    )
    if not rules.exists():
        # Fallback: create basic E1 rules
        rules = [
            SionPlanningRule.objects.create(
                sion=e1_sion,
                name="Other Confectionery",
                expression={"field": "DESCRIPTION", "operator": "CONTAINS", "value": "Confectionery"},
                max_unit_price=Decimal("3.00"),
                priority=1,
                is_active=True,
            ),
        ]
    return list(rules)


@pytest.fixture
def e1_import_items(db):
    """Create test license with E1 import items for planning."""
    company = CompanyModel.objects.create(
        iec="IEC-E1-TEST",
        name="E1 Test Company",
    )
    port, _ = PortModel.objects.get_or_create(
        code="INAPT1",
        defaults={"name": "Test Port"},
    )
    license_obj = LicenseDetailsModel.objects.create(
        license_number="LIC-E1-TEST-001",
        license_date=date.today(),
        license_expiry_date=date.today(),
        exporter=company,
        port=port,
    )

    # Create import items
    items = []
    item_specs = [
        ("080211", "Other Confectionery Ingredients", Decimal("100")),
        ("18031000", "Cocoa Mass", Decimal("60")),
        ("04041000", "Skimmed Milk Powder", Decimal("100")),
        ("35021100", "Egg Albumin", Decimal("60")),
        ("76071190", "Aluminium Foil", Decimal("100")),
        ("39021000", "Polypropylene Granules", Decimal("100")),
    ]

    for hs_code, description, qty in item_specs:
        hs, _ = HSCodeModel.objects.get_or_create(hs_code=hs_code)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            hs_code=hs,
            description=description,
            quantity=qty,
            available_quantity=qty,
        )
        items.append(item)

    return license_obj, items


# ============================================================================
# E5 Fixtures
# ============================================================================


@pytest.fixture
def e5_profile(db, e5_sion):
    """Create or fetch E5 planning profile."""
    import_e1_e5_profiles(activate=True)
    profile = SionPlanningProfile.objects.filter(sion=e5_sion).first()
    if not profile:
        profile = SionPlanningProfile.objects.create(
            sion=e5_sion,
            name="E5 Test Profile",
            version=1,
            is_active=True,
        )
    return profile


@pytest.fixture
def e5_rules(db, e5_sion):
    """Get or create active E5 planning rules."""
    import_e1_e5_profiles(activate=True)
    rules = SionPlanningRule.objects.filter(sion=e5_sion, is_active=True).order_by(
        "priority"
    )
    if not rules.exists():
        rules = [
            SionPlanningRule.objects.create(
                sion=e5_sion,
                name="Milk Products",
                expression={"field": "DESCRIPTION", "operator": "CONTAINS", "value": "Milk"},
                max_unit_price=Decimal("6.50"),
                priority=1,
                is_active=True,
            ),
        ]
    return list(rules)


@pytest.fixture
def e5_import_items(db):
    """Create test license with E5 import items for planning."""
    company = CompanyModel.objects.create(
        iec="IEC-E5-TEST",
        name="E5 Test Company",
    )
    port, _ = PortModel.objects.get_or_create(
        code="INAPT2",
        defaults={"name": "Test Port E5"},
    )
    license_obj = LicenseDetailsModel.objects.create(
        license_number="LIC-E5-TEST-001",
        license_date=date.today(),
        license_expiry_date=date.today(),
        exporter=company,
        port=port,
    )

    items = []
    item_specs = [
        ("04041000", "Skimmed Milk Powder", Decimal("100")),
        ("04051000", "Buttermilk", Decimal("50")),
    ]

    for hs_code, description, qty in item_specs:
        hs, _ = HSCodeModel.objects.get_or_create(hs_code=hs_code)
        item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            hs_code=hs,
            description=description,
            quantity=qty,
            available_quantity=qty,
        )
        items.append(item)

    return license_obj, items


# ============================================================================
# Generic Test License Fixture
# ============================================================================


@pytest.fixture
def test_license_with_balance(db):
    """Create a test license with patchable balance for planner tests."""

    def _make_license(license_number, balance_cif):
        company = CompanyModel.objects.create(
            iec=f"IEC{license_number[-7:]}",
            name=f"Test Company for {license_number}",
        )
        port, _ = PortModel.objects.get_or_create(
            code="TESTPORT",
            defaults={"name": "Test Port"},
        )
        license_obj = LicenseDetailsModel.objects.create(
            license_number=license_number,
            license_date=date.today(),
            license_expiry_date=date.today(),
            exporter=company,
            port=port,
        )

        # Patch the balance property for this specific license
        patcher = patch.object(
            LicenseDetailsModel,
            "get_balance_cif",
            new_callable=lambda: property(lambda self: balance_cif if self.id == license_obj.id else Decimal("0")),
        )
        patcher.start()

        return license_obj, patcher

    return _make_license


# ============================================================================
# HSCode Fixtures (for manual HS code lookups in tests)
# ============================================================================


@pytest.fixture
def hs_codes(db):
    """Pre-create common HS codes for import item tests."""
    codes = {
        "080211": "Almond",
        "18031000": "Cocoa Mass",
        "04041000": "Skimmed Milk Powder",
        "35021100": "Egg Albumin",
        "76071190": "Aluminium Foil",
        "39021000": "Polypropylene Granules",
    }

    result = {}
    for code, desc in codes.items():
        hs, _ = HSCodeModel.objects.get_or_create(hs_code=code)
        result[code] = hs

    return result
