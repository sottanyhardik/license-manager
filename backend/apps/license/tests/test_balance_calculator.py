"""
Unit tests for apps.license.services.balance_calculator module
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest import TestCase
from unittest.mock import ANY, Mock, patch

from django.test import TestCase as DjangoTestCase

from apps.core.constants import DEC_0, DEBIT
from apps.core.models import CompanyModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.trade.models import LicenseTrade, LicenseTradeLine
from apps.license.services.balance_calculator import (
    LicenseBalanceCalculator,
    ItemBalanceCalculator,
)


class TestLicenseBalanceCalculator(TestCase):
    """Tests for LicenseBalanceCalculator class"""

    @patch('apps.license.services.balance_calculator.LicenseExportItemModel')
    def test_calculate_credit_with_exports(self, mock_export_model):
        """Should calculate total export CIF"""
        # Setup mock
        mock_license = Mock()
        mock_queryset = Mock()
        mock_queryset.aggregate.return_value = {'total': Decimal('1000.00')}
        mock_export_model.objects.filter.return_value = mock_queryset

        # Execute
        result = LicenseBalanceCalculator.calculate_credit(mock_license)

        # Assert
        assert result == Decimal('1000.00')
        mock_export_model.objects.filter.assert_called_once_with(license=mock_license)

    @patch('apps.license.services.balance_calculator.LicenseExportItemModel')
    def test_calculate_credit_no_exports(self, mock_export_model):
        """Should return zero when no exports"""
        # Setup mock
        mock_license = Mock()
        mock_queryset = Mock()
        mock_queryset.aggregate.return_value = {'total': DEC_0}
        mock_export_model.objects.filter.return_value = mock_queryset

        # Execute
        result = LicenseBalanceCalculator.calculate_credit(mock_license)

        # Assert
        assert result == DEC_0

    @patch('apps.license.services.balance_calculator.RowDetails')
    def test_calculate_debit_with_boe(self, mock_row_details):
        """
        Should calculate total BOE debits via the allocation-driven
        annotation chain (Phase A): `.filter(...).annotate(allocated=...)
        .annotate(matched=...).annotate(contributed=...).aggregate(...)`,
        replacing the old `~Exists(linked_sale_line)` binary exclusion.
        """
        # Setup mock
        mock_license = Mock()
        mock_queryset = Mock()
        annotated = mock_queryset.annotate.return_value.annotate.return_value.annotate.return_value
        annotated.aggregate.return_value = {'total': Decimal('300.00')}
        mock_row_details.objects.filter.return_value = mock_queryset

        # Execute
        result = LicenseBalanceCalculator.calculate_debit(mock_license)

        # Assert
        assert result == Decimal('300.00')
        mock_row_details.objects.filter.assert_called_once_with(
            sr_number__license=mock_license,
            transaction_type=DEBIT,
        )

    @patch('apps.license.services.balance_calculator.RowDetails')
    def test_calculate_debit_no_boe(self, mock_row_details):
        """Should return zero when no BOE"""
        # Setup mock
        mock_license = Mock()
        mock_queryset = Mock()
        annotated = mock_queryset.annotate.return_value.annotate.return_value.annotate.return_value
        annotated.aggregate.return_value = {'total': DEC_0}
        mock_row_details.objects.filter.return_value = mock_queryset

        # Execute
        result = LicenseBalanceCalculator.calculate_debit(mock_license)

        # Assert
        assert result == DEC_0

    @patch('apps.license.services.balance_calculator.AllotmentItems')
    def test_calculate_allotment_with_items(self, mock_allotment_items):
        """
        Should calculate total allotment CIF via the allocation-driven
        annotation chain (Phase A) -- no longer filters on
        `allotment__bill_of_entry__isnull=True` (that binary inclusion was
        replaced by BOEAllotmentAllocation-driven partial exclusion).
        """
        # Setup mock
        mock_license = Mock()
        mock_queryset = Mock()
        annotated = mock_queryset.annotate.return_value.annotate.return_value.annotate.return_value
        annotated.aggregate.return_value = {'total': Decimal('200.00')}
        mock_allotment_items.objects.filter.return_value = mock_queryset

        # Execute
        result = LicenseBalanceCalculator.calculate_allotment(mock_license)

        # Assert
        assert result == Decimal('200.00')
        mock_allotment_items.objects.filter.assert_called_once_with(
            item__license=mock_license,
        )

    @patch('apps.trade.models.LicenseTradeLine')
    def test_calculate_trade_counts_only_sale_trades(self, mock_trade_line):
        """Should calculate trade debits only from SALE trade lines"""
        mock_license = Mock()
        mock_queryset = Mock()
        mock_queryset.aggregate.return_value = {'total': Decimal('125.00')}
        mock_trade_line.objects.filter.return_value = mock_queryset

        result = LicenseBalanceCalculator.calculate_trade(mock_license)

        assert result == Decimal('125.00')
        mock_trade_line.objects.filter.assert_called_once_with(
            sr_number__license=mock_license,
            trade__direction='SALE',
        )

    @patch('apps.license.services.balance_calculator.AllotmentItems')
    def test_calculate_allotment_no_items(self, mock_allotment_items):
        """Should return zero when no allotments"""
        # Setup mock
        mock_license = Mock()
        mock_queryset = Mock()
        annotated = mock_queryset.annotate.return_value.annotate.return_value.annotate.return_value
        annotated.aggregate.return_value = {'total': DEC_0}
        mock_allotment_items.objects.filter.return_value = mock_queryset

        # Execute
        result = LicenseBalanceCalculator.calculate_allotment(mock_license)

        # Assert
        assert result == DEC_0

    def test_calculate_balance_positive(self):
        """Should calculate positive balance"""
        # Setup mock
        mock_license = Mock()

        with patch.object(LicenseBalanceCalculator, 'calculate_credit', return_value=Decimal('1000.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_debit', return_value=Decimal('300.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=Decimal('200.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_trade', return_value=DEC_0):

            # Execute
            result = LicenseBalanceCalculator.calculate_balance(mock_license)

            # Assert
            assert result == Decimal('500.00')  # 1000 - (300 + 200)

    def test_calculate_balance_zero(self):
        """Should return zero when balance would be negative"""
        # Setup mock
        mock_license = Mock()

        with patch.object(LicenseBalanceCalculator, 'calculate_credit', return_value=Decimal('100.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_debit', return_value=Decimal('300.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=Decimal('200.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_trade', return_value=DEC_0):

            # Execute
            result = LicenseBalanceCalculator.calculate_balance(mock_license)

            # Assert
            assert result == DEC_0  # Should not return negative

    def test_calculate_balance_exact_zero(self):
        """Should handle exact zero balance"""
        # Setup mock
        mock_license = Mock()

        with patch.object(LicenseBalanceCalculator, 'calculate_credit', return_value=Decimal('500.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_debit', return_value=Decimal('300.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=Decimal('200.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_trade', return_value=DEC_0):

            # Execute
            result = LicenseBalanceCalculator.calculate_balance(mock_license)

            # Assert
            assert result == DEC_0

    def test_calculate_all_components(self):
        """Should calculate all balance components at once"""
        # Setup mock
        mock_license = Mock()

        with patch.object(LicenseBalanceCalculator, 'calculate_credit', return_value=Decimal('1000.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_debit', return_value=Decimal('300.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=Decimal('200.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_trade', return_value=DEC_0):

            # Execute
            result = LicenseBalanceCalculator.calculate_all_components(mock_license)

            # Assert
            assert result['credit'] == Decimal('1000.00')
            assert result['debit'] == Decimal('300.00')
            assert result['allotment'] == Decimal('200.00')
            assert result['trade'] == DEC_0
            assert result['balance'] == Decimal('500.00')

    def test_calculate_all_components_negative_balance(self):
        """Should return zero balance in components when negative"""
        # Setup mock
        mock_license = Mock()

        with patch.object(LicenseBalanceCalculator, 'calculate_credit', return_value=Decimal('100.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_debit', return_value=Decimal('300.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=Decimal('200.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_trade', return_value=DEC_0):

            # Execute
            result = LicenseBalanceCalculator.calculate_all_components(mock_license)

            # Assert
            assert result['balance'] == DEC_0


class TestItemBalanceCalculator(TestCase):
    """Tests for ItemBalanceCalculator class"""

    @patch('apps.license.services.balance_calculator.RowDetails')
    @patch('apps.license.services.balance_calculator.AllotmentItems')
    def test_calculate_item_credit_debit_with_item_cif(self, mock_allotment, mock_row_details):
        """Should calculate credit/debit using specific item CIF"""
        # Setup mock
        mock_item = Mock()
        mock_item.cif_fc = Decimal('500.00')
        mock_item.license = Mock()

        # Mock debit query
        mock_debit_qs = Mock()
        mock_debit_qs.aggregate.return_value = {'cif_fc__sum': Decimal('100.00')}
        mock_row_details.objects.filter.return_value = mock_debit_qs

        # Mock allotment query
        mock_allotment_qs = Mock()
        mock_allotment_qs.aggregate.return_value = {'cif_fc__sum': Decimal('50.00')}
        mock_allotment.objects.filter.return_value = mock_allotment_qs

        # Execute
        credit, total_debit = ItemBalanceCalculator.calculate_item_credit_debit(mock_item)

        # Assert
        assert credit == Decimal('500.00')
        assert total_debit == Decimal('150.00')  # 100 + 50

    @patch('apps.license.services.balance_calculator.LicenseExportItemModel')
    @patch('apps.license.services.balance_calculator.RowDetails')
    @patch('apps.license.services.balance_calculator.AllotmentItems')
    def test_calculate_item_credit_debit_zero_cif(self, mock_allotment, mock_row_details, mock_export):
        """Should calculate using total export CIF when item CIF is zero"""
        # Setup mock
        mock_item = Mock()
        mock_item.cif_fc = DEC_0
        mock_item.license = Mock()

        # Mock export query
        mock_export_qs = Mock()
        mock_export_qs.aggregate.return_value = {'cif_fc__sum': Decimal('1000.00')}
        mock_export.objects.filter.return_value = mock_export_qs

        # Mock debit query
        mock_debit_qs = Mock()
        mock_debit_qs.aggregate.return_value = {'cif_fc__sum': Decimal('300.00')}
        mock_row_details.objects.filter.return_value = mock_debit_qs

        # Mock allotment query
        mock_allotment_qs = Mock()
        mock_allotment_qs.aggregate.return_value = {'cif_fc__sum': Decimal('100.00')}
        mock_allotment.objects.filter.return_value = mock_allotment_qs

        # Execute
        credit, total_debit = ItemBalanceCalculator.calculate_item_credit_debit(mock_item)

        # Assert
        assert credit == Decimal('1000.00')  # Total export CIF
        assert total_debit == Decimal('400.00')  # 300 + 100

    @patch('apps.license.services.balance_calculator.RowDetails')
    @patch('apps.license.services.balance_calculator.AllotmentItems')
    def test_calculate_item_credit_debit_no_debits(self, mock_allotment, mock_row_details):
        """Should handle zero debits"""
        # Setup mock
        mock_item = Mock()
        mock_item.cif_fc = Decimal('500.00')
        mock_item.license = Mock()

        # Mock debit query
        mock_debit_qs = Mock()
        mock_debit_qs.aggregate.return_value = {'cif_fc__sum': None}
        mock_row_details.objects.filter.return_value = mock_debit_qs

        # Mock allotment query
        mock_allotment_qs = Mock()
        mock_allotment_qs.aggregate.return_value = {'cif_fc__sum': None}
        mock_allotment.objects.filter.return_value = mock_allotment_qs

        # Execute
        credit, total_debit = ItemBalanceCalculator.calculate_item_credit_debit(mock_item)

        # Assert
        assert credit == Decimal('500.00')
        assert total_debit == DEC_0

    def test_calculate_item_balance_positive(self):
        """Should calculate positive item balance"""
        # Setup mock
        mock_item = Mock()

        with patch.object(ItemBalanceCalculator, 'calculate_item_credit_debit',
                          return_value=(Decimal('500.00'), Decimal('200.00'))):
            # Execute
            result = ItemBalanceCalculator.calculate_item_balance(mock_item)

            # Assert
            assert result == Decimal('300.00')

    def test_calculate_item_balance_zero(self):
        """Should return zero when balance would be negative"""
        # Setup mock
        mock_item = Mock()

        with patch.object(ItemBalanceCalculator, 'calculate_item_credit_debit',
                          return_value=(Decimal('100.00'), Decimal('300.00'))):
            # Execute
            result = ItemBalanceCalculator.calculate_item_balance(mock_item)

            # Assert
            assert result == DEC_0

    @patch('apps.license.services.balance_calculator.RowDetails')
    @patch('apps.license.services.balance_calculator.AllotmentItems')
    def test_calculate_available_quantity(self, mock_allotment, mock_row_details):
        """Should calculate available quantity"""
        # Setup mock
        mock_item = Mock()
        mock_item.quantity = Decimal('1000')

        # Mock debited quantity
        mock_debit_qs = Mock()
        mock_debit_qs.aggregate.return_value = {'qty__sum': Decimal('300')}
        mock_row_details.objects.filter.return_value = mock_debit_qs

        # Mock allotted quantity
        mock_allotment_qs = Mock()
        mock_allotment_qs.aggregate.return_value = {'qty__sum': Decimal('200')}
        mock_allotment.objects.filter.return_value = mock_allotment_qs

        # Execute
        result = ItemBalanceCalculator.calculate_available_quantity(mock_item)

        # Assert
        assert result == Decimal('500')  # 1000 - 300 - 200

    @patch('apps.license.services.balance_calculator.RowDetails')
    @patch('apps.license.services.balance_calculator.AllotmentItems')
    def test_calculate_available_quantity_zero(self, mock_allotment, mock_row_details):
        """Should return zero when fully allocated"""
        # Setup mock
        mock_item = Mock()
        mock_item.quantity = Decimal('1000')

        # Mock debited quantity
        mock_debit_qs = Mock()
        mock_debit_qs.aggregate.return_value = {'qty__sum': Decimal('600')}
        mock_row_details.objects.filter.return_value = mock_debit_qs

        # Mock allotted quantity
        mock_allotment_qs = Mock()
        mock_allotment_qs.aggregate.return_value = {'qty__sum': Decimal('500')}
        mock_allotment.objects.filter.return_value = mock_allotment_qs

        # Execute
        result = ItemBalanceCalculator.calculate_available_quantity(mock_item)

        # Assert
        assert result == DEC_0  # Should not go negative

    def test_calculate_item_components(self):
        """Should calculate all item components"""
        # Setup mock
        mock_item = Mock()

        with patch.object(ItemBalanceCalculator, 'calculate_item_credit_debit',
                          return_value=(Decimal('500.00'), Decimal('200.00'))), \
             patch.object(ItemBalanceCalculator, 'calculate_available_quantity',
                          return_value=Decimal('300')):

            # Execute
            result = ItemBalanceCalculator.calculate_item_components(mock_item)

            # Assert
            assert result['credit'] == Decimal('500.00')
            assert result['debit'] == Decimal('200.00')
            assert result['balance'] == Decimal('300.00')
            assert result['available_quantity'] == Decimal('300')

    def test_calculate_available_value_for_allocation_quantity_constraint(self):
        """Should be constrained by available quantity"""
        # Setup mock
        mock_item = Mock()
        unit_price = Decimal('10.00')

        with patch.object(ItemBalanceCalculator, 'calculate_available_quantity',
                          return_value=Decimal('100')), \
             patch.object(ItemBalanceCalculator, 'calculate_item_balance',
                          return_value=Decimal('5000.00')):  # High CIF balance

            # Execute
            result = ItemBalanceCalculator.calculate_available_value_for_allocation(
                mock_item, unit_price
            )

            # Assert
            assert result['max_quantity'] == Decimal('100')
            assert result['max_value'] == Decimal('1000.00')  # 100 * 10

    def test_calculate_available_value_for_allocation_cif_constraint(self):
        """Should be constrained by CIF balance"""
        # Setup mock
        mock_item = Mock()
        unit_price = Decimal('10.00')

        with patch.object(ItemBalanceCalculator, 'calculate_available_quantity',
                          return_value=Decimal('1000')), \
             patch.object(ItemBalanceCalculator, 'calculate_item_balance',
                          return_value=Decimal('500.00')):  # Low CIF balance

            # Execute
            result = ItemBalanceCalculator.calculate_available_value_for_allocation(
                mock_item, unit_price
            )

            # Assert
            assert result['max_quantity'] == Decimal('50')  # 500 / 10
            assert result['max_value'] == Decimal('500.00')

    def test_calculate_available_value_for_allocation_required_value_constraint(self):
        """Should be constrained by required value"""
        # Setup mock
        mock_item = Mock()
        unit_price = Decimal('10.00')
        required_value = Decimal('300.00')

        with patch.object(ItemBalanceCalculator, 'calculate_available_quantity',
                          return_value=Decimal('1000')), \
             patch.object(ItemBalanceCalculator, 'calculate_item_balance',
                          return_value=Decimal('5000.00')):

            # Execute
            result = ItemBalanceCalculator.calculate_available_value_for_allocation(
                mock_item, unit_price, required_value
            )

            # Assert
            assert result['max_quantity'] == Decimal('30')  # 300 / 10
            assert result['max_value'] == Decimal('300.00')

    def test_calculate_available_value_for_allocation_zero_unit_price(self):
        """Should handle zero unit price"""
        # Setup mock
        mock_item = Mock()
        unit_price = DEC_0

        with patch.object(ItemBalanceCalculator, 'calculate_available_quantity',
                          return_value=Decimal('1000')), \
             patch.object(ItemBalanceCalculator, 'calculate_item_balance',
                          return_value=Decimal('5000.00')):

            # Execute
            result = ItemBalanceCalculator.calculate_available_value_for_allocation(
                mock_item, unit_price
            )

        # Assert
        assert result['max_quantity'] == DEC_0
        assert result['max_value'] == DEC_0

    def test_calculate_available_value_for_allocation_none_unit_price(self):
        """Should treat a missing unit price as zero allocation capacity"""
        mock_item = Mock()

        with patch.object(ItemBalanceCalculator, 'calculate_available_quantity',
                          return_value=Decimal('1000')), \
             patch.object(ItemBalanceCalculator, 'calculate_item_balance',
                          return_value=Decimal('5000.00')):

            result = ItemBalanceCalculator.calculate_available_value_for_allocation(
                mock_item, None
            )

            assert result['max_quantity'] == DEC_0
            assert result['max_value'] == DEC_0

    def test_calculate_available_value_for_allocation_invalid_required_value_ignored(self):
        """Should ignore malformed required-value caps instead of raising"""
        mock_item = Mock()

        with patch.object(ItemBalanceCalculator, 'calculate_available_quantity',
                          return_value=Decimal('100')), \
             patch.object(ItemBalanceCalculator, 'calculate_item_balance',
                          return_value=Decimal('5000.00')):

            result = ItemBalanceCalculator.calculate_available_value_for_allocation(
                mock_item, Decimal('10.00'), "not-a-decimal"
            )

            assert result['max_quantity'] == Decimal('100')
            assert result['max_value'] == Decimal('1000.00')

    def test_calculate_available_value_for_allocation_negative_required_value_ignored(self):
        """Should ignore negative required-value caps instead of returning negative allocation"""
        mock_item = Mock()

        with patch.object(ItemBalanceCalculator, 'calculate_available_quantity',
                          return_value=Decimal('100')), \
             patch.object(ItemBalanceCalculator, 'calculate_item_balance',
                          return_value=Decimal('5000.00')):

            result = ItemBalanceCalculator.calculate_available_value_for_allocation(
                mock_item, Decimal('10.00'), Decimal('-1.00')
            )

            assert result['max_quantity'] == Decimal('100')
            assert result['max_value'] == Decimal('1000.00')


class TestEdgeCases(TestCase):
    """Edge case tests for balance calculators"""

    def test_very_large_balances(self):
        """Should handle very large balance amounts"""
        mock_license = Mock()
        large_value = Decimal('999999999999.99')

        with patch.object(LicenseBalanceCalculator, 'calculate_credit', return_value=large_value), \
             patch.object(LicenseBalanceCalculator, 'calculate_debit', return_value=DEC_0), \
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=DEC_0), \
             patch.object(LicenseBalanceCalculator, 'calculate_trade', return_value=DEC_0):

            result = LicenseBalanceCalculator.calculate_balance(mock_license)
            assert result == large_value

    def test_very_small_positive_balances(self):
        """Should handle very small positive balances"""
        mock_license = Mock()
        small_value = Decimal('0.01')

        with patch.object(LicenseBalanceCalculator, 'calculate_credit', return_value=small_value), \
             patch.object(LicenseBalanceCalculator, 'calculate_debit', return_value=DEC_0), \
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=DEC_0), \
             patch.object(LicenseBalanceCalculator, 'calculate_trade', return_value=DEC_0):

            result = LicenseBalanceCalculator.calculate_balance(mock_license)
            assert result == small_value

    def test_precision_in_calculations(self):
        """Should maintain decimal precision in calculations"""
        mock_item = Mock()
        unit_price = Decimal('3.333')

        with patch.object(ItemBalanceCalculator, 'calculate_available_quantity',
                          return_value=Decimal('100')), \
             patch.object(ItemBalanceCalculator, 'calculate_item_balance',
                          return_value=Decimal('500.00')):

            result = ItemBalanceCalculator.calculate_available_value_for_allocation(
                mock_item, unit_price
            )

            # Should handle decimal division properly
            assert isinstance(result['max_quantity'], Decimal)
            assert isinstance(result['max_value'], Decimal)


class TestCalculateDebitLineLevelExclusion(DjangoTestCase):
    """
    Real-DB regression tests for the double-debit bug fix.

    Business rule under test: "One physical import may generate multiple
    documents, but it must produce exactly one licence debit."

    Phase A update: `calculate_debit()`'s exclusion is now ALLOCATION-DRIVEN
    (see `apps.reconciliation.models.InvoiceBOEAllocation` /
    `apps.reconciliation.services.allocation_service`), not the earlier
    binary, BOE-level `Exists()` check. Merely linking a BOE to a trade's
    `boes` M2M is NO LONGER sufficient for exclusion on its own -- an
    explicit, ACTIVE `InvoiceBOEAllocation` row must exist, and only the
    ALLOCATED portion of a RowDetails row's cif_fc is excluded (never the
    whole row just because SOME allocation exists). `trade.boes` is still
    set in these fixtures for document-level realism, but
    `calculate_debit()` no longer reads it directly.
    """

    def _make_company(self):
        return CompanyModel.objects.create(
            iec=str(uuid.uuid4().int)[:10],
            name="Test Exporter Ltd",
        )

    def _make_license(self, company):
        return LicenseDetailsModel.objects.create(
            license_number="03" + str(uuid.uuid4().int)[:8],
            license_date=datetime.now().date(),
            license_expiry_date=datetime.now().date() + timedelta(days=365),
            exporter=company,
        )

    def _make_item(self, license_obj, serial_number):
        return LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=serial_number,
            description=f"Test Import Item {serial_number}",
            quantity=Decimal("1000.000"),
            available_quantity=Decimal("1000.000"),
        )

    def _make_boe(self, company):
        return BillOfEntryModel.objects.create(
            company=company,
            bill_of_entry_number=str(uuid.uuid4().int)[:9],
            bill_of_entry_date=datetime.now().date(),
            exchange_rate=Decimal("84.50"),
        )

    def _make_debit_row(self, boe, item, cif_fc):
        return RowDetails.objects.create(
            bill_of_entry=boe,
            sr_number=item,
            transaction_type=DEBIT,
            cif_inr=cif_fc * Decimal("84.5"),
            cif_fc=cif_fc,
            qty=Decimal("100.000"),
        )

    def _make_sale_trade(self, company, boes=None):
        trade = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_SALE,
            from_company=company,
            invoice_number=f"INV-TEST-{uuid.uuid4().int % 999999:06d}",
            invoice_date=datetime.now().date(),
        )
        if boes:
            trade.boes.set(boes)
        return trade

    def _make_trade_line(self, trade, item, cif_fc):
        return LicenseTradeLine.objects.create(
            trade=trade,
            sr_number=item,
            description=item.description or "Test Item",
            mode=LicenseTradeLine.MODE_CIF_INR,
            cif_fc=cif_fc,
            cif_inr=cif_fc * Decimal("84.5"),
        )

    def _make_allocation(self, trade_line, row_details, cif_fc, qty=None, cif_inr=None, user=None):
        """Create a real ACTIVE InvoiceBOEAllocation via the service (not a
        direct .objects.create()), so these tests exercise the same
        validation path production code goes through."""
        from apps.reconciliation.services.allocation_service import create_invoice_boe_allocation

        return create_invoice_boe_allocation(
            trade_line=trade_line,
            row_details=row_details,
            qty=qty if qty is not None else DEC_0,
            cif_fc=cif_fc,
            cif_inr=cif_inr if cif_inr is not None else cif_fc * Decimal("84.5"),
            user=user,
        )

    def test_debit_counts_once_when_boe_linked_to_matching_sale_line(self):
        """
        (1) A SALE trade line exists for an item and an explicit, ACTIVE
        InvoiceBOEAllocation fully allocates its cif_fc against the
        matching BOE debit row -- the allocated portion of the RowDetails
        debit row must be excluded from calculate_debit() so the item is
        debited exactly once (via calculate_trade()'s SALE line), not
        twice.
        """
        company = self._make_company()
        license_obj = self._make_license(company)
        item = self._make_item(license_obj, serial_number=1)
        boe = self._make_boe(company)
        debit_row = self._make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        trade = self._make_sale_trade(company, boes=[boe])
        trade_line = self._make_trade_line(trade, item, cif_fc=Decimal("1000.00"))
        self._make_allocation(trade_line, debit_row, cif_fc=Decimal("1000.00"))

        debit = LicenseBalanceCalculator.calculate_debit(license_obj)
        trade_total = LicenseBalanceCalculator.calculate_trade(license_obj)

        assert debit == DEC_0, (
            "BOE row must be excluded once it is fully covered by an "
            "ACTIVE InvoiceBOEAllocation against the matching SALE line"
        )
        assert trade_total == Decimal("1000.00")

    def test_debit_double_counts_when_boe_not_linked_to_matching_trade(self):
        """
        (2) Documents CURRENT expected (deferred) behavior: a BOE debits an
        item AND a SALE trade line also debits that same item, but there is
        NO InvoiceBOEAllocation between them. The allocation-driven
        exclusion only applies to the explicitly allocated amount, so with
        zero allocation both amounts are still counted in full. This
        remaining double count is a DATA problem to be surfaced/resolved
        via the reconciliation panel (link the BOE and create an
        allocation), not silently hidden by the calculator.
        """
        company = self._make_company()
        license_obj = self._make_license(company)
        item = self._make_item(license_obj, serial_number=1)
        boe = self._make_boe(company)
        self._make_debit_row(boe, item, cif_fc=Decimal("1000.00"))
        # Trade debits the SAME sr_number, but its `boes` does NOT include
        # the BOE above, and no InvoiceBOEAllocation exists -- no exclusion
        # should apply.
        trade = self._make_sale_trade(company, boes=None)
        self._make_trade_line(trade, item, cif_fc=Decimal("1000.00"))

        debit = LicenseBalanceCalculator.calculate_debit(license_obj)
        trade_total = LicenseBalanceCalculator.calculate_trade(license_obj)

        assert debit == Decimal("1000.00")
        assert trade_total == Decimal("1000.00")

    def test_debit_not_wrongly_excluded_for_unrelated_item_on_same_boe(self):
        """
        (3) The actual bug scenario the original fix targeted, restated for
        the allocation-driven mechanism: a single BOE debits sr_number A
        AND sr_number B. A SALE trade line debits ONLY sr_number B, and an
        explicit InvoiceBOEAllocation fully allocates B's RowDetails row
        against that line. The exclusion must apply ONLY to B's row --
        sr_number A's debit must still count in full, since no allocation
        was ever created against A's row.
        """
        company = self._make_company()
        license_obj = self._make_license(company)
        item_a = self._make_item(license_obj, serial_number=1)
        item_b = self._make_item(license_obj, serial_number=2)
        boe = self._make_boe(company)
        self._make_debit_row(boe, item_a, cif_fc=Decimal("400.00"))
        debit_row_b = self._make_debit_row(boe, item_b, cif_fc=Decimal("600.00"))
        trade = self._make_sale_trade(company, boes=[boe])
        trade_line_b = self._make_trade_line(trade, item_b, cif_fc=Decimal("600.00"))
        self._make_allocation(trade_line_b, debit_row_b, cif_fc=Decimal("600.00"))

        debit = LicenseBalanceCalculator.calculate_debit(license_obj)
        trade_total = LicenseBalanceCalculator.calculate_trade(license_obj)

        assert debit == Decimal("400.00"), (
            "sr_number A's BOE debit must NOT be excluded just because "
            "sr_number B's row on the same BOE has an active allocation"
        )
        assert trade_total == Decimal("600.00")

        # And the batched sibling must agree with the per-license method.
        batched_debit = LicenseBalanceCalculator.calculate_debit_for_licenses(
            [license_obj.id]
        )
        assert batched_debit.get(license_obj.id, DEC_0) == Decimal("400.00")
