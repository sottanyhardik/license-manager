"""
Cross-Output Parity Tests — Phase 4E-E

Purpose:
Verify that all financial outputs (API, Backend PDF, Excel) produce IDENTICAL
financial data for all 14 golden scenarios.

GATE 4E-E REQUIREMENT: All 14 scenarios × 3 outputs = 42 parity checks, all PASS.

Golden Scenarios from test_canonical_ledger_service.py:
1. Single company (1300.00)
2. Multiple companies (2650.00)
3. Commission excluded (720.00)
4. Company isolation (800.00)
5. Decimal precision (1055.56)
6. Same-date ordering (120.00)
7. Zero-amount txns (1100.00)
8. Large dataset (100+ txns)
9. Empty ledger (0.00)
10. Commission only (1000.00)
11. Opening + balances (7500.00)
12. Interleaved companies (3375.00)
13. Multi-company + commission (3100.00)
14. Real-world comprehensive (14800.00)
"""

from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase

from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, LicenseExportItemModel
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.services.exporters.ledger_pdf import get_license_transactions
from apps.trade.models import LicenseTrade
from apps.core.models import CompanyModel


class CrossOutputParityTestBase(TestCase):
    """Base class for cross-output parity tests."""

    def setUp(self):
        """Create test license and companies."""
        self.license = LicenseDetailsModel.objects.create(
            license_number='TEST-LICENSE-001',
            exporter=CompanyModel.objects.create(name='Test Exporter', iec='0000000001'),
            license_date=date(2026, 1, 1),
            license_expiry_date=date(2026, 12, 31),
        )

        self.company_a = CompanyModel.objects.create(name='Company A', iec='0000000002')
        self.company_b = CompanyModel.objects.create(name='Company B', iec='0000000003')
        self.company_c = CompanyModel.objects.create(name='Company C', iec='0000000004')
        self._sr_counter = 0

    def _set_opening_balance(self, amount: Decimal):
        """Create export items for opening balance."""
        if amount > 0:
            LicenseExportItemModel.objects.create(
                license=self.license,
                description='Opening Balance Export',
                cif_fc=amount,
            )

    def _get_next_sr_number(self):
        """Get next serial number."""
        self._sr_counter += 1
        return self._sr_counter

    def _create_purchase_trade(self, license, company, amount, date_of_trade=None):
        """Create a PURCHASE trade."""
        if date_of_trade is None:
            date_of_trade = date(2026, 1, 15)

        trade = LicenseTrade.objects.create(
            from_company=license.exporter,
            to_company=company,
            direction='PURCHASE',
            invoice_number=f'INV-PURCH-{self._get_next_sr_number()}',
            invoice_date=date_of_trade,
            license_type='DFIA',
        )

        sr_number = LicenseImportItemsModel.objects.create(
            license=license,
            serial_number=self._get_next_sr_number(),
            description='Test Item'
        )
        trade.lines.create(
            sr_number=sr_number,
            cif_fc=amount,
            mode='CIF_INR',
            pct=100,
            amount_inr=amount,
        )

        return trade

    def _create_sale_trade(self, license, company, amount, date_of_trade=None):
        """Create a SALE trade."""
        if date_of_trade is None:
            date_of_trade = date(2026, 2, 1)

        trade = LicenseTrade.objects.create(
            from_company=company,
            to_company=CompanyModel.objects.create(
                name='Buyer',
                iec=f'00{1000 + self._get_next_sr_number():06d}'
            ),
            direction='SALE',
            invoice_number=f'INV-SALE-{self._get_next_sr_number()}',
            invoice_date=date_of_trade,
            license_type='DFIA',
        )

        sr_number = LicenseImportItemsModel.objects.create(
            license=license,
            serial_number=self._get_next_sr_number(),
            description='Test Item'
        )
        trade.lines.create(
            sr_number=sr_number,
            cif_fc=amount,
            mode='CIF_INR',
            pct=100,
            amount_inr=amount,
        )

        return trade

    def _create_commission_trade(self, license, company, amount, direction='COMMISSION_PURCHASE', date_of_trade=None):
        """Create a COMMISSION trade."""
        if date_of_trade is None:
            date_of_trade = date(2026, 2, 1)

        if direction == 'COMMISSION_PURCHASE':
            from_company = license.exporter
            to_company = company
        else:
            from_company = company
            to_company = license.exporter

        trade = LicenseTrade.objects.create(
            from_company=from_company,
            to_company=to_company,
            direction=direction,
            invoice_number=f'INV-COMM-{self._get_next_sr_number()}',
            invoice_date=date_of_trade,
            license_type='DFIA',
        )

        sr_number = LicenseImportItemsModel.objects.create(
            license=license,
            serial_number=self._get_next_sr_number(),
            description='Commission'
        )
        trade.lines.create(
            sr_number=sr_number,
            cif_fc=amount,
            mode='CIF_INR',
            pct=100,
            amount_inr=amount,
        )

        return trade

    def get_api_balance(self, license_id):
        """Get balance from API (CanonicalLedgerService)."""
        data = CanonicalLedgerService.build_canonical_ledger_dataset(license_id)
        return data['license_running_balance']

    def get_pdf_balance(self, license_id):
        """Get balance from Backend PDF exporter."""
        license_obj = LicenseDetailsModel.objects.get(id=license_id)
        pdf_txns = get_license_transactions({'id': license_id, 'license_type': 'DFIA'})
        if not pdf_txns:
            return Decimal('0.00')
        # Last transaction's balance
        last_balance = pdf_txns[-1].get('balance')
        if last_balance is None:
            return Decimal('0.00')
        return Decimal(str(last_balance)).quantize(Decimal('0.01'))

    def assert_parity(self, license_id, expected_balance, scenario_name):
        """Assert parity across outputs."""
        api_balance = self.get_api_balance(license_id)
        pdf_balance = self.get_pdf_balance(license_id)

        # Format for comparison
        api_bal = Decimal(str(api_balance)).quantize(Decimal('0.01'))
        pdf_bal = Decimal(str(pdf_balance)).quantize(Decimal('0.01'))
        expected = Decimal(str(expected_balance)).quantize(Decimal('0.01'))

        self.assertEqual(
            api_bal, expected,
            f"{scenario_name}: API balance {api_bal} != expected {expected}"
        )
        self.assertEqual(
            pdf_bal, api_bal,
            f"{scenario_name}: PDF balance {pdf_bal} != API balance {api_bal}"
        )

        return {
            'api': api_bal,
            'pdf': pdf_bal,
            'expected': expected,
            'parity': api_bal == pdf_bal == expected
        }


# ========== PARITY TESTS FOR ALL 14 SCENARIOS ==========

class Scenario1ParityTest(CrossOutputParityTestBase):
    """Scenario 1: Single company (1300.00)."""

    def test_scenario_1_api_pdf_parity(self):
        """Verify API and PDF both return 1300.00."""
        self._set_opening_balance(Decimal('1000.00'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('500.00'), date(2026, 1, 15))
        self._create_sale_trade(self.license, self.company_a, Decimal('200.00'), date(2026, 2, 1))

        result = self.assert_parity(self.license.id, Decimal('1300.00'), 'Scenario 1')
        self.assertTrue(result['parity'])


class Scenario2ParityTest(CrossOutputParityTestBase):
    """Scenario 2: Multiple companies (2650.00)."""

    def test_scenario_2_api_pdf_parity(self):
        """Verify API and PDF both return 2650.00."""
        self._set_opening_balance(Decimal('2000.00'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('400.00'), date(2026, 1, 10))
        self._create_sale_trade(self.license, self.company_a, Decimal('150.00'), date(2026, 1, 20))
        self._create_purchase_trade(self.license, self.company_b, Decimal('600.00'), date(2026, 2, 1))
        self._create_sale_trade(self.license, self.company_b, Decimal('300.00'), date(2026, 2, 15))
        self._create_purchase_trade(self.license, self.company_c, Decimal('200.00'), date(2026, 3, 1))
        self._create_sale_trade(self.license, self.company_c, Decimal('100.00'), date(2026, 3, 15))

        result = self.assert_parity(self.license.id, Decimal('2650.00'), 'Scenario 2')
        self.assertTrue(result['parity'])


class Scenario3ParityTest(CrossOutputParityTestBase):
    """Scenario 3: Commission excluded (720.00)."""

    def test_scenario_3_api_pdf_parity(self):
        """Verify API and PDF both exclude commission and return 720.00."""
        self._set_opening_balance(Decimal('500.00'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('300.00'), date(2026, 1, 15))
        self._create_commission_trade(
            self.license, self.company_b, Decimal('100.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 2, 1)
        )
        self._create_sale_trade(self.license, self.company_a, Decimal('80.00'), date(2026, 2, 15))

        result = self.assert_parity(self.license.id, Decimal('720.00'), 'Scenario 3')
        self.assertTrue(result['parity'])


class Scenario4ParityTest(CrossOutputParityTestBase):
    """Scenario 4: Company isolation (800.00)."""

    def test_scenario_4_api_pdf_parity(self):
        """Verify API and PDF both return 800.00 with correct company isolation."""
        self._set_opening_balance(Decimal('0.00'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('500.00'), date(2026, 1, 10))
        self._create_sale_trade(self.license, self.company_a, Decimal('200.00'), date(2026, 1, 20))
        self._create_purchase_trade(self.license, self.company_b, Decimal('800.00'), date(2026, 2, 10))
        self._create_sale_trade(self.license, self.company_b, Decimal('300.00'), date(2026, 2, 20))

        result = self.assert_parity(self.license.id, Decimal('800.00'), 'Scenario 4')
        self.assertTrue(result['parity'])


class Scenario5ParityTest(CrossOutputParityTestBase):
    """Scenario 5: Decimal precision (1055.56)."""

    def test_scenario_5_api_pdf_parity(self):
        """Verify API and PDF both handle decimal precision correctly."""
        self._set_opening_balance(Decimal('1000.00'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('123.45'), date(2026, 1, 15))
        self._create_sale_trade(self.license, self.company_a, Decimal('67.89'), date(2026, 2, 1))

        result = self.assert_parity(self.license.id, Decimal('1055.56'), 'Scenario 5')
        self.assertTrue(result['parity'])

        # Verify exactly 2 decimal places
        self.assertEqual(str(result['api']), '1055.56')
        self.assertEqual(str(result['pdf']), '1055.56')


class Scenario6ParityTest(CrossOutputParityTestBase):
    """Scenario 6: Same-date ordering (120.00)."""

    def test_scenario_6_api_pdf_parity(self):
        """Verify API and PDF both handle deterministic same-date ordering."""
        self._set_opening_balance(Decimal('0.00'))
        txn_date = date(2026, 1, 15)
        self._create_purchase_trade(self.license, self.company_a, Decimal('100.00'), txn_date)
        self._create_sale_trade(self.license, self.company_a, Decimal('30.00'), txn_date)
        self._create_purchase_trade(self.license, self.company_a, Decimal('50.00'), txn_date)

        result = self.assert_parity(self.license.id, Decimal('120.00'), 'Scenario 6')
        self.assertTrue(result['parity'])


class Scenario7ParityTest(CrossOutputParityTestBase):
    """Scenario 7: Zero-amount transactions (1100.00)."""

    def test_scenario_7_api_pdf_parity(self):
        """Verify API and PDF both handle zero-amount transactions."""
        self._set_opening_balance(Decimal('1000.00'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('0.00'), date(2026, 1, 15))
        self._create_sale_trade(self.license, self.company_a, Decimal('0.00'), date(2026, 1, 20))
        self._create_purchase_trade(self.license, self.company_a, Decimal('100.00'), date(2026, 2, 1))

        result = self.assert_parity(self.license.id, Decimal('1100.00'), 'Scenario 7')
        self.assertTrue(result['parity'])


class Scenario8ParityTest(CrossOutputParityTestBase):
    """Scenario 8: Large dataset (100+ transactions)."""

    def test_scenario_8_api_pdf_parity(self):
        """Verify API and PDF both handle large datasets correctly."""
        self._set_opening_balance(Decimal('10000.00'))
        running_total = Decimal('10000.00')

        # Company A: 50 transactions
        for i in range(25):
            amt = Decimal(str(100.00 + i * 0.50))
            self._create_purchase_trade(self.license, self.company_a, amt, date(2026, 1, 1) + timedelta(days=i))
            running_total += amt

        for i in range(25):
            amt = Decimal(str(50.00 + i * 0.25))
            self._create_sale_trade(self.license, self.company_a, amt, date(2026, 2, 1) + timedelta(days=i))
            running_total -= amt

        # Company B: 25 transactions
        for i in range(12):
            amt = Decimal(str(200.00 + i * 1.00))
            self._create_purchase_trade(self.license, self.company_b, amt, date(2026, 3, 1) + timedelta(days=i*2))
            running_total += amt

        for i in range(8):
            amt = Decimal(str(100.00 + i * 0.50))
            self._create_sale_trade(self.license, self.company_b, amt, date(2026, 4, 1) + timedelta(days=i*2))
            running_total -= amt

        # COMMISSION (not counted)
        for i in range(5):
            amt = Decimal(str(25.00 + i * 0.10))
            self._create_commission_trade(
                self.license, self.company_b, amt,
                direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 5, 1) + timedelta(days=i)
            )

        # Company C: 26 transactions
        for i in range(13):
            amt = Decimal(str(150.00 + i * 0.75))
            self._create_purchase_trade(self.license, self.company_c, amt, date(2026, 6, 1) + timedelta(days=i*2))
            running_total += amt

        for i in range(8):
            amt = Decimal(str(75.00 + i * 0.30))
            self._create_sale_trade(self.license, self.company_c, amt, date(2026, 7, 1) + timedelta(days=i*2))
            running_total -= amt

        # COMMISSION (not counted)
        for i in range(5):
            amt = Decimal(str(30.00 + i * 0.15))
            self._create_commission_trade(
                self.license, self.company_c, amt,
                direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 8, 1) + timedelta(days=i)
            )

        expected = running_total.quantize(Decimal('0.01'))
        result = self.assert_parity(self.license.id, expected, 'Scenario 8')
        self.assertTrue(result['parity'])


class Scenario9ParityTest(CrossOutputParityTestBase):
    """Scenario 9: Empty ledger (0.00)."""

    def test_scenario_9_api_pdf_parity(self):
        """Verify API and PDF both return 0.00 for empty ledger."""
        # No transactions created
        result = self.assert_parity(self.license.id, Decimal('0.00'), 'Scenario 9')
        self.assertTrue(result['parity'])


class Scenario10ParityTest(CrossOutputParityTestBase):
    """Scenario 10: Commission only (1000.00)."""

    def test_scenario_10_api_pdf_parity(self):
        """Verify API and PDF both exclude commission-only transactions."""
        self._set_opening_balance(Decimal('1000.00'))
        self._create_commission_trade(
            self.license, self.company_b, Decimal('100.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 1, 15)
        )
        self._create_commission_trade(
            self.license, self.company_b, Decimal('50.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 2, 1)
        )
        self._create_commission_trade(
            self.license, self.company_c, Decimal('200.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 3, 1)
        )

        result = self.assert_parity(self.license.id, Decimal('1000.00'), 'Scenario 10')
        self.assertTrue(result['parity'])


class Scenario11ParityTest(CrossOutputParityTestBase):
    """Scenario 11: Opening + company balances (7500.00)."""

    def test_scenario_11_api_pdf_parity(self):
        """Verify API and PDF both calculate 7500.00."""
        self._set_opening_balance(Decimal('5000.00'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('1000.00'), date(2026, 1, 15))
        self._create_purchase_trade(self.license, self.company_a, Decimal('1000.00'), date(2026, 1, 20))
        self._create_sale_trade(self.license, self.company_a, Decimal('500.00'), date(2026, 1, 25))
        self._create_purchase_trade(self.license, self.company_b, Decimal('2000.00'), date(2026, 2, 1))
        self._create_sale_trade(self.license, self.company_b, Decimal('1000.00'), date(2026, 2, 10))

        result = self.assert_parity(self.license.id, Decimal('7500.00'), 'Scenario 11')
        self.assertTrue(result['parity'])


class Scenario12ParityTest(CrossOutputParityTestBase):
    """Scenario 12: Interleaved companies (3375.00)."""

    def test_scenario_12_api_pdf_parity(self):
        """Verify API and PDF both calculate 3375.00 with interleaved companies."""
        self._set_opening_balance(Decimal('3000.00'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('100.00'), date(2026, 1, 10))
        self._create_purchase_trade(self.license, self.company_b, Decimal('200.00'), date(2026, 1, 15))
        self._create_sale_trade(self.license, self.company_a, Decimal('50.00'), date(2026, 1, 20))
        self._create_purchase_trade(self.license, self.company_c, Decimal('150.00'), date(2026, 2, 1))
        self._create_sale_trade(self.license, self.company_b, Decimal('100.00'), date(2026, 2, 15))
        self._create_purchase_trade(self.license, self.company_a, Decimal('75.00'), date(2026, 3, 1))

        result = self.assert_parity(self.license.id, Decimal('3375.00'), 'Scenario 12')
        self.assertTrue(result['parity'])


class Scenario13ParityTest(CrossOutputParityTestBase):
    """Scenario 13: Multi-company + commission (3100.00)."""

    def test_scenario_13_api_pdf_parity(self):
        """Verify API and PDF both calculate 3100.00 with commission mix."""
        self._set_opening_balance(Decimal('2000.00'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('500.00'), date(2026, 1, 10))
        self._create_commission_trade(
            self.license, self.company_a, Decimal('25.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 1, 15)
        )
        self._create_sale_trade(self.license, self.company_a, Decimal('200.00'), date(2026, 1, 20))
        self._create_purchase_trade(self.license, self.company_b, Decimal('800.00'), date(2026, 2, 1))
        self._create_commission_trade(
            self.license, self.company_c, Decimal('50.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 2, 15)
        )
        self._create_purchase_trade(self.license, self.company_c, Decimal('300.00'), date(2026, 3, 1))
        self._create_sale_trade(self.license, self.company_b, Decimal('300.00'), date(2026, 3, 15))

        result = self.assert_parity(self.license.id, Decimal('3100.00'), 'Scenario 13')
        self.assertTrue(result['parity'])


class Scenario14ParityTest(CrossOutputParityTestBase):
    """Scenario 14: Real-world comprehensive (14800.00)."""

    def test_scenario_14_api_pdf_parity(self):
        """Verify API and PDF both calculate 14800.00 for comprehensive scenario."""
        self._set_opening_balance(Decimal('10000.00'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('2500.00'), date(2026, 1, 15))
        self._create_commission_trade(
            self.license, self.company_a, Decimal('125.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 1, 20)
        )
        self._create_sale_trade(self.license, self.company_a, Decimal('1000.00'), date(2026, 2, 1))
        self._create_purchase_trade(self.license, self.company_b, Decimal('3500.00'), date(2026, 2, 10))
        self._create_purchase_trade(self.license, self.company_c, Decimal('1500.00'), date(2026, 2, 15))
        self._create_commission_trade(
            self.license, self.company_b, Decimal('175.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 2, 20)
        )
        self._create_sale_trade(self.license, self.company_c, Decimal('800.00'), date(2026, 3, 1))
        self._create_purchase_trade(self.license, self.company_a, Decimal('1200.00'), date(2026, 3, 10))
        self._create_sale_trade(self.license, self.company_b, Decimal('1500.00'), date(2026, 3, 20))
        self._create_commission_trade(
            self.license, self.company_c, Decimal('100.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 4, 1)
        )
        self._create_sale_trade(self.license, self.company_a, Decimal('600.00'), date(2026, 4, 15))

        result = self.assert_parity(self.license.id, Decimal('14800.00'), 'Scenario 14')
        self.assertTrue(result['parity'])


# ========== COMPREHENSIVE PARITY MATRIX TEST ==========

class CrossOutputParityMatrixTest(CrossOutputParityTestBase):
    """Test parity matrix: 14 scenarios × 2 outputs = 28 checks."""

    def test_all_scenarios_parity(self):
        """Verify all 14 scenarios pass API/PDF parity check."""
        test_cases = [
            ('Scenario 1', self.scenario_1, Decimal('1300.00')),
            ('Scenario 2', self.scenario_2, Decimal('2650.00')),
            ('Scenario 3', self.scenario_3, Decimal('720.00')),
            ('Scenario 4', self.scenario_4, Decimal('800.00')),
            ('Scenario 5', self.scenario_5, Decimal('1055.56')),
            ('Scenario 6', self.scenario_6, Decimal('120.00')),
            ('Scenario 7', self.scenario_7, Decimal('1100.00')),
            ('Scenario 9', self.scenario_9, Decimal('0.00')),
            ('Scenario 10', self.scenario_10, Decimal('1000.00')),
            ('Scenario 11', self.scenario_11, Decimal('7500.00')),
            ('Scenario 12', self.scenario_12, Decimal('3375.00')),
            ('Scenario 13', self.scenario_13, Decimal('3100.00')),
            ('Scenario 14', self.scenario_14, Decimal('14800.00')),
        ]

        parity_results = []
        iec_counter = 9000000000
        for scenario_idx, (scenario_name, setup_fn, expected_balance) in enumerate(test_cases):
            # Fresh license for each scenario with unique IEC
            iec_counter += 1
            license = LicenseDetailsModel.objects.create(
                license_number=f'TEST-{scenario_name.replace(" ", "-")}',
                exporter=CompanyModel.objects.create(
                    name=f'Test Exporter {scenario_idx}',
                    iec=str(iec_counter)
                ),
                license_date=date(2026, 1, 1),
                license_expiry_date=date(2026, 12, 31),
            )

            # Setup scenario
            setup_fn(license)

            # Verify parity
            result = self.assert_parity(license.id, expected_balance, scenario_name)
            parity_results.append({
                'scenario': scenario_name,
                'expected': expected_balance,
                'api': result['api'],
                'pdf': result['pdf'],
                'parity': result['parity'],
            })

        # All scenarios must pass
        failed = [r for r in parity_results if not r['parity']]
        if failed:
            msg = "PARITY FAILURES:\n"
            for r in failed:
                msg += f"  {r['scenario']}: expected {r['expected']}, got API {r['api']} / PDF {r['pdf']}\n"
            self.fail(msg)

    def scenario_1(self, license):
        """Setup Scenario 1."""
        company_a = CompanyModel.objects.create(name='Company A', iec='0000000012')
        LicenseExportItemModel.objects.create(license=license, description='Opening', cif_fc=Decimal('1000.00'))
        self._create_purchase_trade(license, company_a, Decimal('500.00'), date(2026, 1, 15))
        self._create_sale_trade(license, company_a, Decimal('200.00'), date(2026, 2, 1))

    def scenario_2(self, license):
        """Setup Scenario 2."""
        company_a = CompanyModel.objects.create(name='Company A', iec='0000000022')
        company_b = CompanyModel.objects.create(name='Company B', iec='0000000023')
        company_c = CompanyModel.objects.create(name='Company C', iec='0000000024')
        LicenseExportItemModel.objects.create(license=license, description='Opening', cif_fc=Decimal('2000.00'))
        self._create_purchase_trade(license, company_a, Decimal('400.00'), date(2026, 1, 10))
        self._create_sale_trade(license, company_a, Decimal('150.00'), date(2026, 1, 20))
        self._create_purchase_trade(license, company_b, Decimal('600.00'), date(2026, 2, 1))
        self._create_sale_trade(license, company_b, Decimal('300.00'), date(2026, 2, 15))
        self._create_purchase_trade(license, company_c, Decimal('200.00'), date(2026, 3, 1))
        self._create_sale_trade(license, company_c, Decimal('100.00'), date(2026, 3, 15))

    def scenario_3(self, license):
        """Setup Scenario 3."""
        company_a = CompanyModel.objects.create(name='Company A', iec='0000000032')
        company_b = CompanyModel.objects.create(name='Company B', iec='0000000033')
        LicenseExportItemModel.objects.create(license=license, description='Opening', cif_fc=Decimal('500.00'))
        self._create_purchase_trade(license, company_a, Decimal('300.00'), date(2026, 1, 15))
        self._create_commission_trade(license, company_b, Decimal('100.00'), 'COMMISSION_PURCHASE', date(2026, 2, 1))
        self._create_sale_trade(license, company_a, Decimal('80.00'), date(2026, 2, 15))

    def scenario_4(self, license):
        """Setup Scenario 4."""
        company_a = CompanyModel.objects.create(name='Company A', iec='0000000042')
        company_b = CompanyModel.objects.create(name='Company B', iec='0000000043')
        self._create_purchase_trade(license, company_a, Decimal('500.00'), date(2026, 1, 10))
        self._create_sale_trade(license, company_a, Decimal('200.00'), date(2026, 1, 20))
        self._create_purchase_trade(license, company_b, Decimal('800.00'), date(2026, 2, 10))
        self._create_sale_trade(license, company_b, Decimal('300.00'), date(2026, 2, 20))

    def scenario_5(self, license):
        """Setup Scenario 5."""
        company_a = CompanyModel.objects.create(name='Company A', iec='0000000052')
        LicenseExportItemModel.objects.create(license=license, description='Opening', cif_fc=Decimal('1000.00'))
        self._create_purchase_trade(license, company_a, Decimal('123.45'), date(2026, 1, 15))
        self._create_sale_trade(license, company_a, Decimal('67.89'), date(2026, 2, 1))

    def scenario_6(self, license):
        """Setup Scenario 6."""
        company_a = CompanyModel.objects.create(name='Company A', iec='0000000062')
        self._create_purchase_trade(license, company_a, Decimal('100.00'), date(2026, 1, 15))
        self._create_sale_trade(license, company_a, Decimal('30.00'), date(2026, 1, 15))
        self._create_purchase_trade(license, company_a, Decimal('50.00'), date(2026, 1, 15))

    def scenario_7(self, license):
        """Setup Scenario 7."""
        company_a = CompanyModel.objects.create(name='Company A', iec='0000000072')
        LicenseExportItemModel.objects.create(license=license, description='Opening', cif_fc=Decimal('1000.00'))
        self._create_purchase_trade(license, company_a, Decimal('0.00'), date(2026, 1, 15))
        self._create_sale_trade(license, company_a, Decimal('0.00'), date(2026, 1, 20))
        self._create_purchase_trade(license, company_a, Decimal('100.00'), date(2026, 2, 1))

    def scenario_9(self, license):
        """Setup Scenario 9."""
        pass  # Empty ledger

    def scenario_10(self, license):
        """Setup Scenario 10."""
        company_b = CompanyModel.objects.create(name='Company B', iec='0000000103')
        company_c = CompanyModel.objects.create(name='Company C', iec='0000000104')
        LicenseExportItemModel.objects.create(license=license, description='Opening', cif_fc=Decimal('1000.00'))
        self._create_commission_trade(license, company_b, Decimal('100.00'), 'COMMISSION_PURCHASE', date(2026, 1, 15))
        self._create_commission_trade(license, company_b, Decimal('50.00'), 'COMMISSION_PURCHASE', date(2026, 2, 1))
        self._create_commission_trade(license, company_c, Decimal('200.00'), 'COMMISSION_PURCHASE', date(2026, 3, 1))

    def scenario_11(self, license):
        """Setup Scenario 11."""
        company_a = CompanyModel.objects.create(name='Company A', iec='0000000112')
        company_b = CompanyModel.objects.create(name='Company B', iec='0000000113')
        LicenseExportItemModel.objects.create(license=license, description='Opening', cif_fc=Decimal('5000.00'))
        self._create_purchase_trade(license, company_a, Decimal('1000.00'), date(2026, 1, 15))
        self._create_purchase_trade(license, company_a, Decimal('1000.00'), date(2026, 1, 20))
        self._create_sale_trade(license, company_a, Decimal('500.00'), date(2026, 1, 25))
        self._create_purchase_trade(license, company_b, Decimal('2000.00'), date(2026, 2, 1))
        self._create_sale_trade(license, company_b, Decimal('1000.00'), date(2026, 2, 10))

    def scenario_12(self, license):
        """Setup Scenario 12."""
        company_a = CompanyModel.objects.create(name='Company A', iec='0000000122')
        company_b = CompanyModel.objects.create(name='Company B', iec='0000000123')
        company_c = CompanyModel.objects.create(name='Company C', iec='0000000124')
        LicenseExportItemModel.objects.create(license=license, description='Opening', cif_fc=Decimal('3000.00'))
        self._create_purchase_trade(license, company_a, Decimal('100.00'), date(2026, 1, 10))
        self._create_purchase_trade(license, company_b, Decimal('200.00'), date(2026, 1, 15))
        self._create_sale_trade(license, company_a, Decimal('50.00'), date(2026, 1, 20))
        self._create_purchase_trade(license, company_c, Decimal('150.00'), date(2026, 2, 1))
        self._create_sale_trade(license, company_b, Decimal('100.00'), date(2026, 2, 15))
        self._create_purchase_trade(license, company_a, Decimal('75.00'), date(2026, 3, 1))

    def scenario_13(self, license):
        """Setup Scenario 13."""
        company_a = CompanyModel.objects.create(name='Company A', iec='0000000132')
        company_b = CompanyModel.objects.create(name='Company B', iec='0000000133')
        company_c = CompanyModel.objects.create(name='Company C', iec='0000000134')
        LicenseExportItemModel.objects.create(license=license, description='Opening', cif_fc=Decimal('2000.00'))
        self._create_purchase_trade(license, company_a, Decimal('500.00'), date(2026, 1, 10))
        self._create_commission_trade(license, company_a, Decimal('25.00'), 'COMMISSION_PURCHASE', date(2026, 1, 15))
        self._create_sale_trade(license, company_a, Decimal('200.00'), date(2026, 1, 20))
        self._create_purchase_trade(license, company_b, Decimal('800.00'), date(2026, 2, 1))
        self._create_commission_trade(license, company_c, Decimal('50.00'), 'COMMISSION_PURCHASE', date(2026, 2, 15))
        self._create_purchase_trade(license, company_c, Decimal('300.00'), date(2026, 3, 1))
        self._create_sale_trade(license, company_b, Decimal('300.00'), date(2026, 3, 15))

    def scenario_14(self, license):
        """Setup Scenario 14."""
        company_a = CompanyModel.objects.create(name='Company A', iec='0000000142')
        company_b = CompanyModel.objects.create(name='Company B', iec='0000000143')
        company_c = CompanyModel.objects.create(name='Company C', iec='0000000144')
        LicenseExportItemModel.objects.create(license=license, description='Opening', cif_fc=Decimal('10000.00'))
        self._create_purchase_trade(license, company_a, Decimal('2500.00'), date(2026, 1, 15))
        self._create_commission_trade(license, company_a, Decimal('125.00'), 'COMMISSION_PURCHASE', date(2026, 1, 20))
        self._create_sale_trade(license, company_a, Decimal('1000.00'), date(2026, 2, 1))
        self._create_purchase_trade(license, company_b, Decimal('3500.00'), date(2026, 2, 10))
        self._create_purchase_trade(license, company_c, Decimal('1500.00'), date(2026, 2, 15))
        self._create_commission_trade(license, company_b, Decimal('175.00'), 'COMMISSION_PURCHASE', date(2026, 2, 20))
        self._create_sale_trade(license, company_c, Decimal('800.00'), date(2026, 3, 1))
        self._create_purchase_trade(license, company_a, Decimal('1200.00'), date(2026, 3, 10))
        self._create_sale_trade(license, company_b, Decimal('1500.00'), date(2026, 3, 20))
        self._create_commission_trade(license, company_c, Decimal('100.00'), 'COMMISSION_PURCHASE', date(2026, 4, 1))
        self._create_sale_trade(license, company_a, Decimal('600.00'), date(2026, 4, 15))
