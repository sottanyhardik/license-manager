"""
Tests for Dual-Run Verification Framework.

Verifies that canonical ledger calculations match approved semantics across
all golden scenarios.
"""

from decimal import Decimal
from datetime import date
from django.test import TestCase

from apps.license.models import LicenseDetailsModel
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.services.ledger_dual_run import LedgerDualRun
from apps.core.models import CompanyModel


class DualRunVerificationTests(TestCase):
    """Verify canonical service produces expected results."""

    def setUp(self):
        """Create test license and companies."""
        self.license = LicenseDetailsModel.objects.create(
            license_number='DUALRUN-TEST',
            exporter=CompanyModel.objects.create(name='Test Exporter', iec='0000000001'),
            license_date=date(2026, 1, 1),
            license_expiry_date=date(2026, 12, 31),
        )

    def test_dual_run_framework_empty_license(self):
        """Test dual-run on empty license."""
        result = LedgerDualRun.run_dual_calculation(self.license.id)

        self.assertEqual(result['license_id'], self.license.id)
        self.assertEqual(result['status'], 'IDENTICAL')  # No differences
        self.assertIsNotNone(result['new_result'])

    def test_summary_generation(self):
        """Test dual-run summary generation."""
        comparisons = [
            {
                'license_id': 1,
                'status': 'IDENTICAL',
                'differences': [],
                'old_result': None,
                'new_result': {},
            }
        ]

        summary = LedgerDualRun.summarize_dual_run(comparisons)

        self.assertEqual(summary['total_licenses'], 1)
        self.assertEqual(summary['identical'], 1)
        self.assertEqual(summary['status'], 'PASS')

    def test_difference_classification(self):
        """Test classification of differences."""
        rounding_diff = {
            'metric': 'balance',
            'old_value': Decimal('100.00'),
            'new_value': Decimal('100.01'),
            'classification': 'ROUNDING_DIFFERENCE',
            'reason': 'Rounding',
        }

        classification = LedgerDualRun.classify_difference(rounding_diff)
        self.assertEqual(classification, 'ACCEPTABLE')

        unexpected_diff = {
            'metric': 'balance',
            'old_value': Decimal('100.00'),
            'new_value': Decimal('200.00'),
            'classification': 'UNEXPECTED_DIFFERENCE',
            'reason': 'Unexplained',
        }

        classification = LedgerDualRun.classify_difference(unexpected_diff)
        self.assertEqual(classification, 'BLOCKER')
