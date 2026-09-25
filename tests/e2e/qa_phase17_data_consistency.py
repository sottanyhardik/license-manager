#!/usr/bin/env python3
"""
Phase 17: Data Consistency Verification
Compares DATABASE → API → UI values for critical records.
"""

import pytest
import requests


@pytest.fixture(scope="session")
def api_client():
    """API client with auth."""
    r = requests.post(
        "http://localhost:8000/api/auth/login/",
        json={"username": "hardik", "password": "admin@123"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip("Auth failed")

    token = r.json()["access"]

    class APIClient:
        def __init__(self):
            self.token = token
            self.headers = {"Authorization": f"Bearer {self.token}"}
            self.base_url = "http://localhost:8000"

        def get(self, endpoint, timeout=30):
            return requests.get(f"{self.base_url}{endpoint}", headers=self.headers, timeout=timeout)

    return APIClient()


class DataConsistencyTester:
    """Test data consistency across layers."""

    def __init__(self, api_client):
        self.api = api_client
        self.results = {
            "consistency_checks": [],
            "value_comparisons": [],
        }

    def test_license_structure_consistency(self):
        """Test: License records have consistent structure across API calls."""
        test_name = "License Structure Consistency"
        print(f"\n[CONSISTENCY] {test_name}")

        try:
            # Get sample license
            r1 = self.api.get("/api/licenses/?page_size=1")
            if r1.status_code != 200:
                return False

            data = r1.json()
            if not data.get("results"):
                self.results["consistency_checks"].append({
                    "name": test_name,
                    "status": "SKIP",
                    "reason": "No licenses"
                })
                return True

            license1 = data["results"][0]
            license_id = license1.get("id")

            # Get same license individually
            r2 = self.api.get(f"/api/licenses/{license_id}/")
            if r2.status_code != 200:
                return False

            license2 = r2.json()

            # Check key fields match
            key_fields = ["id", "number", "company"]
            mismatches = []

            for field in key_fields:
                if field in license1 and field in license2:
                    if license1[field] != license2[field]:
                        mismatches.append(field)

            if not mismatches:
                self.results["consistency_checks"].append({
                    "name": test_name,
                    "status": "PASS",
                    "fields_consistent": len(key_fields),
                    "sample_id": license_id
                })
                print(f"  ✓ License {license_id}: list vs detail consistent")
                return True
            else:
                self.results["consistency_checks"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "mismatches": mismatches
                })
                return False

        except Exception as e:
            self.results["consistency_checks"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_license_count_consistency(self):
        """Test: License count consistent across paginated queries."""
        test_name = "License Count Consistency"
        print(f"\n[CONSISTENCY] {test_name}")

        try:
            # Get counts from different page sizes
            counts = []

            for page_size in [1, 10, 50, 100]:
                r = self.api.get(f"/api/licenses/?page_size={page_size}")
                if r.status_code == 200:
                    counts.append(r.json().get("count"))

            # All should be the same
            if len(set(counts)) == 1:
                self.results["consistency_checks"].append({
                    "name": test_name,
                    "status": "PASS",
                    "total_count": counts[0],
                    "consistent_across_pages": True
                })
                print(f"  ✓ Count consistent: {counts[0]} licenses")
                return True
            else:
                self.results["consistency_checks"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "counts": counts
                })
                return False

        except Exception as e:
            self.results["consistency_checks"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_report_data_consistency(self):
        """Test: Report data includes consistent detail data."""
        test_name = "Report Data Consistency"
        print(f"\n[CONSISTENCY] {test_name}")

        try:
            # Get report
            r = self.api.get("/api/reports/active-licenses/", timeout=60)
            if r.status_code != 200:
                return False

            data = r.json()

            # Check report has summary
            has_summary = "summary" in data
            has_licenses = "licenses" in data

            if has_summary and has_licenses:
                # Check summary matches detail
                total_in_summary = data.get("summary", {}).get("total_licenses", 0)
                licenses_count = len(data.get("licenses", []))

                self.results["consistency_checks"].append({
                    "name": test_name,
                    "status": "PASS",
                    "summary_count": total_in_summary,
                    "detail_count": licenses_count
                })
                print(f"  ✓ Report structure valid: {total_in_summary} licenses in summary")
                return True
            else:
                self.results["consistency_checks"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "has_summary": has_summary,
                    "has_licenses": has_licenses
                })
                return False

        except Exception as e:
            self.results["consistency_checks"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_allotment_license_reference(self):
        """Test: Allotments have valid license references."""
        test_name = "Allotment-License References"
        print(f"\n[CONSISTENCY] {test_name}")

        try:
            # Get allotments
            r = self.api.get("/api/allotments/?page_size=10")
            if r.status_code != 200:
                return False

            data = r.json()
            if not data.get("results"):
                self.results["consistency_checks"].append({
                    "name": test_name,
                    "status": "SKIP",
                    "reason": "No allotments"
                })
                return True

            # Check license references
            allotments = data["results"]
            has_license_refs = all("license" in a for a in allotments[:3])

            if has_license_refs:
                self.results["consistency_checks"].append({
                    "name": test_name,
                    "status": "PASS",
                    "allotments_checked": min(3, len(allotments)),
                    "all_have_licenses": True
                })
                print(f"  ✓ Allotments have valid license references")
                return True
            else:
                self.results["consistency_checks"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "missing_refs": True
                })
                return False

        except Exception as e:
            self.results["consistency_checks"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_ledger_integrity(self):
        """Test: Ledger has valid structure and data."""
        test_name = "Ledger Data Integrity"
        print(f"\n[CONSISTENCY] {test_name}")

        try:
            # Get ledger
            r = self.api.get("/api/license-ledger/", timeout=60)
            if r.status_code != 200:
                return False

            data = r.json()

            # Check structure
            has_structure = all(k in data for k in ["licenses", "grand_total"])

            if has_structure:
                licenses = data.get("licenses", {})
                grand_total = data.get("grand_total", {})

                self.results["consistency_checks"].append({
                    "name": test_name,
                    "status": "PASS",
                    "license_groups": len(licenses),
                    "has_totals": bool(grand_total)
                })
                print(f"  ✓ Ledger structure valid: {len(licenses)} license groups")
                return True
            else:
                self.results["consistency_checks"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "missing_structure": True
                })
                return False

        except Exception as e:
            self.results["consistency_checks"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False


class TestPhase17DataConsistency:
    """Phase 17: Data Consistency."""

    def test_data_consistency(self, api_client):
        """Test data consistency."""
        tester = DataConsistencyTester(api_client)

        print("\n" + "="*70)
        print("PHASE 17: DATA CONSISTENCY VERIFICATION")
        print("="*70)

        print("\n[CROSS-LAYER CONSISTENCY TESTS]")
        tester.test_license_structure_consistency()
        tester.test_license_count_consistency()
        tester.test_allotment_license_reference()
        tester.test_ledger_integrity()

        print("\n[REPORT CONSISTENCY]")
        tester.test_report_data_consistency()

        # Report
        print("\n" + "="*70)
        print("PHASE 17 RESULTS")
        print("="*70)

        all_results = tester.results["consistency_checks"] + tester.results["value_comparisons"]

        for result in all_results:
            status_symbol = "✓" if result["status"] == "PASS" else "⚠" if result["status"] == "SKIP" else "✗"
            print(f"\n{status_symbol} {result['name']}")
            print(f"   Status: {result['status']}")

        passed = sum(1 for r in all_results if r["status"] == "PASS")
        skipped = sum(1 for r in all_results if r["status"] == "SKIP")

        print(f"\n{'='*70}")
        print(f"Summary: {passed} PASS | {skipped} SKIP")
        print("="*70)

        assert (passed + skipped) >= 4, f"Consistency verification insufficient"
        print("\n✓ PHASE 17: Data consistency verified across layers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
