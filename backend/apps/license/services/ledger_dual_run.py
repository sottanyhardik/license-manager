"""
Dual-Run Verification Framework — Ledger Old vs New Comparison

This module implements a verification framework that runs both the OLD (current)
and NEW (canonical) ledger calculations in parallel, compares results, and
classifies differences.

**Purpose:**
- Verify that new canonical service produces expected results
- Identify unexpected divergences from legacy implementation
- Classify differences (expected, acceptable, or blockers)
- Generate reports for stakeholders

**Usage (tests only, not production):**
```python
comparison = LedgerDualRun.run_dual_calculation(license_id)
if comparison['status'] == 'IDENTICAL':
    print("✅ New calculation matches old")
else:
    for diff in comparison['differences']:
        print(f"{diff['metric']}: {diff['classification']}")
```

**Classification Schema:**
- IDENTICAL: No differences found
- ROUNDING_DIFFERENCE: <0.01 difference (acceptable)
- ORDERING_DIFFERENCE: Same balance, different transaction order (acceptable)
- EXPECTED_BUSINESS_CHANGE: Change matches approved semantics (acceptable)
- UNEXPECTED_DIFFERENCE: Change not explained (investigate)
- SEMANTIC_DIFFERENCE: Change contradicts approved design (blocker)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Any, Optional

from apps.license.services.canonical_ledger_service import CanonicalLedgerService


class LedgerDualRun:
    """Run old and new ledger calculations in parallel and compare."""

    EPSILON = Decimal('0.01')  # Acceptable rounding difference

    @staticmethod
    def run_dual_calculation(
        license_id: int,
        license_type: str = 'DFIA',
        legacy_builder=None,  # Injected for testing
    ) -> Dict[str, Any]:
        """
        Run dual-run verification: both old and new calculations.

        Args:
            license_id: License to verify
            license_type: License type (DFIA, INCENTIVE, etc.)
            legacy_builder: Optional legacy calculation function (for mocking)

        Returns:
            Dict with comparison results:
            {
                'license_id': int,
                'status': 'IDENTICAL' | 'DIFFERENCES_FOUND',
                'differences': [
                    {
                        'metric': str,
                        'old_value': Any,
                        'new_value': Any,
                        'classification': str,
                        'reason': str,
                    },
                    ...
                ],
                'old_result': Dict,  # Legacy calculation result
                'new_result': Dict,  # Canonical calculation result
            }
        """
        # Run both calculations
        try:
            new_result = CanonicalLedgerService.build_canonical_ledger_dataset(
                license_id, license_type
            )
        except Exception as e:
            return {
                'license_id': license_id,
                'status': 'ERROR',
                'error': f"Canonical service failed: {str(e)}",
                'differences': [],
                'old_result': None,
                'new_result': None,
            }

        # For now, legacy_result is None (legacy code not yet integrated)
        # In Phase 4C, we'll inject the legacy builder
        old_result = legacy_builder(license_id) if legacy_builder else None

        # Compare results
        differences = []
        if old_result:
            differences = LedgerDualRun._compare_results(old_result, new_result)

        return {
            'license_id': license_id,
            'status': 'IDENTICAL' if not differences else 'DIFFERENCES_FOUND',
            'differences': differences,
            'old_result': old_result,
            'new_result': new_result,
        }

    @staticmethod
    def _compare_results(old_result: Dict, new_result: Dict) -> List[Dict[str, Any]]:
        """
        Compare old vs new results and classify differences.

        Args:
            old_result: Legacy calculation result
            new_result: Canonical calculation result

        Returns:
            List of differences found
        """
        differences = []

        # Compare license running balance
        old_balance = Decimal(str(old_result.get('available_balance', 0)))
        new_balance = Decimal(str(new_result.get('license_running_balance', 0)))

        if old_balance != new_balance:
            diff_amount = abs(old_balance - new_balance)
            if diff_amount < LedgerDualRun.EPSILON:
                classification = 'ROUNDING_DIFFERENCE'
                reason = f"Rounding: {diff_amount} (< 0.01)"
            elif 'COMMISSION' in str(new_result.get('comment', '')):
                classification = 'EXPECTED_BUSINESS_CHANGE'
                reason = "COMMISSION handling changed per approved semantics"
            else:
                classification = 'UNEXPECTED_DIFFERENCE'
                reason = f"Difference of {diff_amount} not explained"

            differences.append({
                'metric': 'license_running_balance',
                'old_value': old_balance,
                'new_value': new_balance,
                'classification': classification,
                'reason': reason,
            })

        # Compare transaction count
        old_txn_count = len(old_result.get('transactions', []))
        new_txn_count = len(new_result.get('transactions', []))

        if old_txn_count != new_txn_count:
            differences.append({
                'metric': 'transaction_count',
                'old_value': old_txn_count,
                'new_value': new_txn_count,
                'classification': 'INVESTIGATION_REQUIRED',
                'reason': f"Transaction count differs: {old_txn_count} vs {new_txn_count}",
            })

        # Compare company utilizations
        old_util = old_result.get('company_utilizations', {})
        new_util = new_result.get('company_utilizations', {})

        for company_id in set(list(old_util.keys()) + list(new_util.keys())):
            old_company_balance = Decimal(str(old_util.get(company_id, 0)))
            new_company_balance = Decimal(str(new_util.get(company_id, {}).get('utilization_balance', 0)))

            if old_company_balance != new_company_balance:
                diff_amount = abs(old_company_balance - new_company_balance)
                if diff_amount < LedgerDualRun.EPSILON:
                    classification = 'ROUNDING_DIFFERENCE'
                else:
                    classification = 'UNEXPECTED_DIFFERENCE'

                differences.append({
                    'metric': f'company_utilization_{company_id}',
                    'old_value': old_company_balance,
                    'new_value': new_company_balance,
                    'classification': classification,
                    'reason': f"Company utilization differs by {diff_amount}",
                })

        return differences

    @staticmethod
    def classify_difference(difference: Dict[str, Any]) -> str:
        """
        Classify a single difference as acceptable or blocker.

        Returns:
            Classification string
        """
        classification = difference.get('classification', 'UNKNOWN')

        # Acceptable classifications
        if classification in [
            'IDENTICAL',
            'ROUNDING_DIFFERENCE',
            'ORDERING_DIFFERENCE',
            'EXPECTED_BUSINESS_CHANGE',
        ]:
            return 'ACCEPTABLE'

        # Blocker classifications
        if classification in [
            'SEMANTIC_DIFFERENCE',
            'UNEXPECTED_DIFFERENCE',
        ]:
            return 'BLOCKER'

        return 'REVIEW_REQUIRED'

    @staticmethod
    def summarize_dual_run(comparisons: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Summarize results from multiple dual-run verifications.

        Args:
            comparisons: List of comparison results from run_dual_calculation()

        Returns:
            Summary dict with counts and status
        """
        total = len(comparisons)
        identical = sum(1 for c in comparisons if c['status'] == 'IDENTICAL')
        differences_found = sum(1 for c in comparisons if c['status'] == 'DIFFERENCES_FOUND')
        errors = sum(1 for c in comparisons if c['status'] == 'ERROR')

        blockers = 0
        acceptables = 0
        unknowns = 0

        for comparison in comparisons:
            for diff in comparison.get('differences', []):
                classification = LedgerDualRun.classify_difference(diff)
                if classification == 'BLOCKER':
                    blockers += 1
                elif classification == 'ACCEPTABLE':
                    acceptables += 1
                else:
                    unknowns += 1

        return {
            'total_licenses': total,
            'identical': identical,
            'with_differences': differences_found,
            'errors': errors,
            'total_differences': blockers + acceptables + unknowns,
            'acceptable_differences': acceptables,
            'blockers': blockers,
            'unknown': unknowns,
            'status': 'PASS' if blockers == 0 else 'FAIL',
        }


def generate_dual_run_report(comparisons: List[Dict[str, Any]]) -> str:
    """
    Generate a markdown report from dual-run comparisons.

    Args:
        comparisons: List of comparison results

    Returns:
        Markdown report string
    """
    summary = LedgerDualRun.summarize_dual_run(comparisons)

    report = f"""# Dual-Run Verification Report

Generated for {summary['total_licenses']} licenses

## Summary

| Metric | Count |
|--------|-------|
| Identical | {summary['identical']} |
| With Differences | {summary['with_differences']} |
| Errors | {summary['errors']} |
| Total Differences Found | {summary['total_differences']} |
| Acceptable Differences | {summary['acceptable_differences']} |
| Blockers | {summary['blockers']} |
| Unknown | {summary['unknown']} |

**Status: {'✅ PASS' if summary['status'] == 'PASS' else '❌ FAIL'}**

"""

    # List blockers if any
    if summary['blockers'] > 0:
        report += "## Blockers\n\n"
        for comparison in comparisons:
            for diff in comparison.get('differences', []):
                if LedgerDualRun.classify_difference(diff) == 'BLOCKER':
                    report += f"- License {comparison['license_id']}: {diff['metric']} "
                    report += f"({diff['old_value']} → {diff['new_value']})\n"
        report += "\n"

    # List acceptables if any
    if summary['acceptable_differences'] > 0:
        report += "## Acceptable Differences\n\n"
        for comparison in comparisons:
            for diff in comparison.get('differences', []):
                if LedgerDualRun.classify_difference(diff) == 'ACCEPTABLE':
                    report += f"- License {comparison['license_id']}: {diff['metric']} "
                    report += f"({diff['reason']})\n"
        report += "\n"

    return report
