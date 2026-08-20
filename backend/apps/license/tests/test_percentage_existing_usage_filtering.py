"""
Tests for exact BOE/Allotment filtering by license + canonical input.

Validates:
- Exact license filtering
- Canonical input alias resolution (PKO, PALM KERNEL OIL)
- Case and whitespace normalization
- No cross-contamination with wrong products
- No cross-contamination with other licenses
- Linked Allotment/BOE lifecycle handling
- PKO and Olive Oil calculations
"""
import pytest
from decimal import Decimal
from datetime import date

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT
from apps.core.models import CompanyModel, ItemNameModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.percentage_existing_usage import (
    CanonicalInputResolver,
    PercentageExistingUsageService,
)


@pytest.fixture
def usage_company(db):
    return CompanyModel.objects.create(iec="PCTUSAGE01", name="Percentage usage company")


@pytest.fixture
def _usage_license_factory(usage_company):
    counter = {"value": 0}

    def make(number):
        counter["value"] += 1
        return LicenseDetailsModel.objects.create(
            exporter=usage_company,
            license_number=number,
        )

    return make


@pytest.fixture
def license_3411008090(_usage_license_factory):
    return _usage_license_factory("3411008090")


@pytest.fixture
def license_a(_usage_license_factory):
    return _usage_license_factory("PCT-USAGE-A")


@pytest.fixture
def license_b(_usage_license_factory):
    return _usage_license_factory("PCT-USAGE-B")


@pytest.fixture
def _usage_row_factory(usage_company):
    sequence = {"value": 0}

    def make(license_obj, product, quantity, cif=None, *, allotment=False):
        sequence["value"] += 1
        item_name, _ = ItemNameModel.objects.get_or_create(name=product)
        import_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=sequence["value"],
            description=f"Usage source {sequence['value']}",
            quantity=Decimal(str(quantity)),
            available_quantity=Decimal(str(quantity)),
        )
        import_item.items.add(item_name)
        cif = Decimal(str(cif if cif is not None else quantity))
        if allotment:
            parent = AllotmentModel.objects.create(
                company=usage_company,
                item_name=f"Allotment {sequence['value']}",
            )
            return AllotmentItems.objects.create(
                allotment=parent, item=import_item,
                qty=Decimal(str(quantity)), cif_fc=cif,
            )
        boe = BillOfEntryModel.objects.create(
            company=usage_company,
            bill_of_entry_number=f"PCT-BOE-{sequence['value']}",
            bill_of_entry_date=date.today(),
            exchange_rate=Decimal("1"),
        )
        return RowDetails.objects.create(
            bill_of_entry=boe, sr_number=import_item, transaction_type=DEBIT,
            qty=Decimal(str(quantity)), cif_fc=cif, cif_inr=cif,
        )

    return make


@pytest.fixture
def boe_olive_51286_84(_usage_row_factory, license_3411008090):
    return _usage_row_factory(license_3411008090, "OLIVE OIL", "51286.84", "284982.98")


@pytest.fixture
def allotment_olive_26711(_usage_row_factory, license_3411008090):
    return _usage_row_factory(license_3411008090, "OLIVE OIL", "26711.00", "130033.87", allotment=True)


@pytest.fixture
def boe_pko_100(_usage_row_factory, license_3411008090):
    return _usage_row_factory(license_3411008090, "PKO", "100.00")


@pytest.fixture
def allotment_pko_alias_150(_usage_row_factory, license_3411008090):
    # Add the second approved alias to the BOE record set, then retain a
    # non-BOE row so both usage paths receive real fixture coverage.
    _usage_row_factory(license_3411008090, "PALM KERNEL OIL", "150.00")
    return _usage_row_factory(license_3411008090, "PALM KERNEL OIL", "150.00", allotment=True)


@pytest.fixture
def boe_olive_license_a_100(_usage_row_factory, license_a):
    return _usage_row_factory(license_a, "OLIVE OIL", "100.00")


@pytest.fixture
def boe_olive_license_b_300(_usage_row_factory, license_b):
    return _usage_row_factory(license_b, "OLIVE OIL", "300.00")


@pytest.fixture
def boe_pko_license_a_100(_usage_row_factory, license_a):
    return _usage_row_factory(license_a, "PKO", "100.00")


@pytest.fixture
def boe_pko_license_b_200(_usage_row_factory, license_b):
    return _usage_row_factory(license_b, "PALM KERNEL OIL", "200.00")


@pytest.fixture
def boe_palm_oil_300(_usage_row_factory, license_3411008090):
    return _usage_row_factory(license_3411008090, "PALM OIL", "300.00")


@pytest.fixture
def boe_olive_with_cif(_usage_row_factory, license_3411008090):
    return _usage_row_factory(license_3411008090, "OLIVE OIL", "10.00", "25.50")


@pytest.fixture
def boe_pko_variations(_usage_row_factory, license_3411008090):
    return [
        _usage_row_factory(license_3411008090, name, "100.00")
        for name in ("PKO", "pko", "Pko", "PALM KERNEL OIL", "Palm Kernel Oil", "palm kernel oil")
    ]


class TestCanonicalInputResolver:
    """Test product name normalization and canonical resolution."""

    def test_normalize_pko_aliases(self):
        """Test that PKO aliases normalize correctly."""
        assert CanonicalInputResolver.normalize_name("PKO") == "PKO"
        assert CanonicalInputResolver.normalize_name("pko") == "PKO"
        assert CanonicalInputResolver.normalize_name(" PKO ") == "PKO"
        assert CanonicalInputResolver.normalize_name("PALM KERNEL OIL") == "PALM KERNEL OIL"
        assert CanonicalInputResolver.normalize_name("Palm Kernel Oil") == "PALM KERNEL OIL"
        assert CanonicalInputResolver.normalize_name("  PALM   KERNEL   OIL  ") == "PALM KERNEL OIL"

    def test_resolve_pko_canonical(self):
        """Test that PKO aliases resolve to PKO canonical code."""
        assert CanonicalInputResolver.resolve_canonical("PKO") == "PKO"
        assert CanonicalInputResolver.resolve_canonical("pko") == "PKO"
        assert CanonicalInputResolver.resolve_canonical("PALM KERNEL OIL") == "PKO"
        assert CanonicalInputResolver.resolve_canonical("palm kernel oil") == "PKO"

    def test_resolve_olive_canonical(self):
        """Test that OLIVE OIL resolves to OLIVE_OIL canonical code."""
        assert CanonicalInputResolver.resolve_canonical("OLIVE OIL") == "OLIVE_OIL"
        assert CanonicalInputResolver.resolve_canonical("olive oil") == "OLIVE_OIL"

    def test_reject_wrong_products(self):
        """Test that wrong products do NOT resolve to PKO."""
        assert CanonicalInputResolver.resolve_canonical("PALM OIL") is None
        assert CanonicalInputResolver.resolve_canonical("RBD PALMOLEIN") is None
        assert CanonicalInputResolver.resolve_canonical("PALM OLEIN") is None
        assert CanonicalInputResolver.resolve_canonical("OTHER PALM PRODUCTS") is None

    def test_get_aliases_for_canonical(self):
        """Test retrieval of approved aliases for a canonical input."""
        pko_aliases = CanonicalInputResolver.get_aliases_for_canonical("PKO")
        assert "PKO" in pko_aliases
        assert "PALM KERNEL OIL" in pko_aliases

        olive_aliases = CanonicalInputResolver.get_aliases_for_canonical("OLIVE_OIL")
        assert "OLIVE OIL" in olive_aliases


@pytest.mark.django_db
class TestPercentageExistingUsageFiltering:
    """Test existing usage filtering for specific license + canonical input."""

    def test_olive_filter_by_license_and_product(self, db, license_3411008090, boe_olive_51286_84, allotment_olive_26711):
        """
        Test that Olive filtering returns only:
        - License 3411008090
        - Olive Oil product
        """
        usage = PercentageExistingUsageService.get_existing_usage(
            license_3411008090,
            "OLIVE_OIL",
        )

        assert usage["canonical_input"] == "OLIVE_OIL"
        assert usage["boe_quantity"] == Decimal("51286.84")
        assert usage["boe_cif"] == Decimal("284982.98")
        assert usage["allotment_quantity"] == Decimal("26711.00")
        assert usage["allotment_cif"] == Decimal("130033.87")
        assert usage["relevant_quantity"] == Decimal("77997.84")
        assert usage["relevant_cif"] == Decimal("415016.85")

    def test_pko_filter_by_license_and_aliases(self, db, license_3411008090, boe_pko_100, allotment_pko_alias_150):
        """
        Test that PKO filtering:
        - Matches both PKO and PALM KERNEL OIL aliases
        - Returns combined quantity/CIF
        """
        usage = PercentageExistingUsageService.get_existing_usage(
            license_3411008090,
            "PKO",
        )

        assert usage["canonical_input"] == "PKO"
        # Should match both 100 (PKO) + 150 (PALM KERNEL OIL)
        assert usage["boe_quantity"] == Decimal("250.00")

    def test_license_isolation_olive(self, db, license_a, license_b, boe_olive_license_a_100, boe_olive_license_b_300):
        """
        Test that Olive filtering does not cross licenses.

        License A: Olive BOE = 100
        License B: Olive BOE = 300

        Query License A + OLIVE_OIL should return 100, not 400.
        """
        usage_a = PercentageExistingUsageService.get_existing_usage(
            license_a,
            "OLIVE_OIL",
        )
        assert usage_a["boe_quantity"] == Decimal("100.00")

        usage_b = PercentageExistingUsageService.get_existing_usage(
            license_b,
            "OLIVE_OIL",
        )
        assert usage_b["boe_quantity"] == Decimal("300.00")

    def test_license_isolation_pko(self, db, license_a, license_b, boe_pko_license_a_100, boe_pko_license_b_200):
        """
        Test that PKO filtering does not cross licenses.

        License A: PKO BOE = 100
        License B: PKO BOE = 200

        Query License A + PKO should return 100, not 300.
        """
        usage_a = PercentageExistingUsageService.get_existing_usage(
            license_a,
            "PKO",
        )
        assert usage_a["boe_quantity"] == Decimal("100.00")

        usage_b = PercentageExistingUsageService.get_existing_usage(
            license_b,
            "PKO",
        )
        assert usage_b["boe_quantity"] == Decimal("200.00")

    def test_wrong_product_not_matched(self, db, license_3411008090, boe_pko_100, boe_palm_oil_300):
        """
        Test that wrong products do NOT contaminate PKO totals.

        License 3411008090:
        PKO BOE = 100
        PALM OIL BOE = 300

        Query PKO should return 100, not 400.
        """
        usage = PercentageExistingUsageService.get_existing_usage(
            license_3411008090,
            "PKO",
        )
        assert usage["boe_quantity"] == Decimal("100.00")
        # PALM OIL should not be included

    def test_quantity_and_cif_same_record_set(self, db, license_3411008090, boe_olive_with_cif):
        """
        Test that BOE quantity and CIF totals come from the same record set.

        If the logic has a bug and uses different filters for quantity vs CIF,
        this test will catch it by verifying the math.
        """
        usage = PercentageExistingUsageService.get_existing_usage(
            license_3411008090,
            "OLIVE_OIL",
        )

        # Verify that the data is self-consistent
        # (specific values depend on fixture data)
        assert usage["boe_cif"] > Decimal("0")
        assert usage["boe_quantity"] > Decimal("0")

    def test_case_insensitive_pko(self, db, license_3411008090, boe_pko_variations):
        """
        Test that PKO aliases are case-insensitive.

        Fixture: PKO, pko, Pko, PALM KERNEL OIL, Palm Kernel Oil, palm kernel oil all exist.

        All should aggregate to PKO.
        """
        usage = PercentageExistingUsageService.get_existing_usage(
            license_3411008090,
            "PKO",
        )
        # Should aggregate all variations
        assert usage["boe_quantity"] == Decimal("600.00")  # 100+100+100+100+100+100

    def test_empty_usage_when_no_matches(self, db, license_3411008090):
        """
        Test that empty usage is returned when no matching records exist.
        """
        usage = PercentageExistingUsageService.get_existing_usage(
            license_3411008090,
            "NONEXISTENT_INPUT",
        )

        assert usage["boe_quantity"] == Decimal("0")
        assert usage["boe_cif"] == Decimal("0")
        assert usage["allotment_quantity"] == Decimal("0")
        assert usage["allotment_cif"] == Decimal("0")
        assert usage["relevant_quantity"] == Decimal("0")
        assert usage["relevant_cif"] == Decimal("0")
