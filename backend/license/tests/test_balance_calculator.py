"""
Unit tests for license.services.balance_calculator module
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from django.db.models import QuerySet

from core.constants import DEC_0, DEBIT
from license.services.balance_calculator import (
    LicenseBalanceCalculator,
    ItemBalanceCalculator,
)


class TestLicenseBalanceCalculator:
    """Tests for LicenseBalanceCalculator class"""

    @patch('license.services.balance_calculator.LicenseExportItemModel')
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

    @patch('license.services.balance_calculator.LicenseExportItemModel')
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

    @patch('license.services.balance_calculator.RowDetails')
    def test_calculate_debit_with_boe(self, mock_row_details):
        """Should calculate total BOE debits"""
        # Setup mock
        mock_license = Mock()
        mock_queryset = Mock()
        mock_queryset.aggregate.return_value = {'total': Decimal('300.00')}
        mock_row_details.objects.filter.return_value = mock_queryset

        # Execute
        result = LicenseBalanceCalculator.calculate_debit(mock_license)

        # Assert
        assert result == Decimal('300.00')
        mock_row_details.objects.filter.assert_called_once()

    @patch('license.services.balance_calculator.RowDetails')
    def test_calculate_debit_no_boe(self, mock_row_details):
        """Should return zero when no BOE"""
        # Setup mock
        mock_license = Mock()
        mock_queryset = Mock()
        mock_queryset.aggregate.return_value = {'total': DEC_0}
        mock_row_details.objects.filter.return_value = mock_queryset

        # Execute
        result = LicenseBalanceCalculator.calculate_debit(mock_license)

        # Assert
        assert result == DEC_0

    @patch('license.services.balance_calculator.AllotmentItems')
    def test_calculate_allotment_with_items(self, mock_allotment_items):
        """Should calculate total allotment CIF"""
        # Setup mock
        mock_license = Mock()
        mock_queryset = Mock()
        mock_queryset.aggregate.return_value = {'total': Decimal('200.00')}
        mock_allotment_items.objects.filter.return_value = mock_queryset

        # Execute
        result = LicenseBalanceCalculator.calculate_allotment(mock_license)

        # Assert
        assert result == Decimal('200.00')
        mock_allotment_items.objects.filter.assert_called_once()

    @patch('license.services.balance_calculator.AllotmentItems')
    def test_calculate_allotment_no_items(self, mock_allotment_items):
        """Should return zero when no allotments"""
        # Setup mock
        mock_license = Mock()
        mock_queryset = Mock()
        mock_queryset.aggregate.return_value = {'total': DEC_0}
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
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=Decimal('200.00')):

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
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=Decimal('200.00')):

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
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=Decimal('200.00')):

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
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=Decimal('200.00')):

            # Execute
            result = LicenseBalanceCalculator.calculate_all_components(mock_license)

            # Assert
            assert result['credit'] == Decimal('1000.00')
            assert result['debit'] == Decimal('300.00')
            assert result['allotment'] == Decimal('200.00')
            assert result['balance'] == Decimal('500.00')

    def test_calculate_all_components_negative_balance(self):
        """Should return zero balance in components when negative"""
        # Setup mock
        mock_license = Mock()

        with patch.object(LicenseBalanceCalculator, 'calculate_credit', return_value=Decimal('100.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_debit', return_value=Decimal('300.00')), \
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=Decimal('200.00')):

            # Execute
            result = LicenseBalanceCalculator.calculate_all_components(mock_license)

            # Assert
            assert result['balance'] == DEC_0


class TestItemBalanceCalculator:
    """Tests for ItemBalanceCalculator class"""

    @patch('license.services.balance_calculator.RowDetails')
    @patch('license.services.balance_calculator.AllotmentItems')
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

    @patch('license.services.balance_calculator.LicenseExportItemModel')
    @patch('license.services.balance_calculator.RowDetails')
    @patch('license.services.balance_calculator.AllotmentItems')
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

    @patch('license.services.balance_calculator.RowDetails')
    @patch('license.services.balance_calculator.AllotmentItems')
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

    @patch('license.services.balance_calculator.RowDetails')
    @patch('license.services.balance_calculator.AllotmentItems')
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

    @patch('license.services.balance_calculator.RowDetails')
    @patch('license.services.balance_calculator.AllotmentItems')
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


class TestEdgeCases:
    """Edge case tests for balance calculators"""

    def test_very_large_balances(self):
        """Should handle very large balance amounts"""
        mock_license = Mock()
        large_value = Decimal('999999999999.99')

        with patch.object(LicenseBalanceCalculator, 'calculate_credit', return_value=large_value), \
             patch.object(LicenseBalanceCalculator, 'calculate_debit', return_value=DEC_0), \
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=DEC_0):

            result = LicenseBalanceCalculator.calculate_balance(mock_license)
            assert result == large_value

    def test_very_small_positive_balances(self):
        """Should handle very small positive balances"""
        mock_license = Mock()
        small_value = Decimal('0.01')

        with patch.object(LicenseBalanceCalculator, 'calculate_credit', return_value=small_value), \
             patch.object(LicenseBalanceCalculator, 'calculate_debit', return_value=DEC_0), \
             patch.object(LicenseBalanceCalculator, 'calculate_allotment', return_value=DEC_0):

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
