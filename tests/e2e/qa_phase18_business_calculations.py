#!/usr/bin/env python3
"""Phase 18: Business Calculations - independent verification"""
import pytest, requests

@pytest.fixture(scope="session")
def api_client():
    r = requests.post("http://localhost:8000/api/auth/login/",
                     json={"username":"hardik","password":"admin@123"}, timeout=10)
    if r.status_code != 200:
        pytest.skip("Auth failed")

    token = r.json()["access"]
    class APIClient:
        def __init__(self):
            self.token = token
            self.headers = {"Authorization": f"Bearer {self.token}"}
            self.base_url = "http://localhost:8000"

        def get(self, endpoint, timeout=60):
            return requests.get(f"{self.base_url}{endpoint}", headers=self.headers, timeout=timeout)

    return APIClient()

class BusinessCalculationsTester:
    def __init__(self, api_client):
        self.api = api_client
        self.results = []

    def test_license_count(self):
        """Verify license count consistency across queries"""
        test_name = "License Count Consistency"
        try:
            counts = {}
            r = self.api.get("/api/licenses/?page_size=1")
            if r.status_code == 200:
                counts["page1"] = r.json().get("count")

            r = self.api.get("/api/licenses/?page_size=100")
            if r.status_code == 200:
                counts["page100"] = r.json().get("count")

            if len(set(counts.values())) == 1 and counts:
                self.results.append({"name": test_name, "status": "PASS", "count": counts.get("page1")})
                return True
            else:
                self.results.append({"name": test_name, "status": "FAIL", "counts": counts})
                return False
        except Exception as e:
            self.results.append({"name": test_name, "status": "FAIL", "error": str(e)})
            return False

    def test_allotment_structure(self):
        """Verify allotments have proper financial structure"""
        test_name = "Allotment Financial Structure"
        try:
            r = self.api.get("/api/allotments/?page_size=10")
            if r.status_code != 200:
                self.results.append({"name": test_name, "status": "FAIL"})
                return False

            data = r.json()
            if not data.get("results"):
                self.results.append({"name": test_name, "status": "SKIP", "reason": "No allotments"})
                return True

            # Verify financial fields exist
            required = ["id", "company", "required_quantity", "cif_inr", "alloted_quantity"]
            allot = data["results"][0]
            missing = [f for f in required if f not in allot]

            if not missing:
                self.results.append({"name": test_name, "status": "PASS", "fields": len(required)})
                return True
            else:
                self.results.append({"name": test_name, "status": "FAIL", "missing": missing})
                return False
        except Exception as e:
            self.results.append({"name": test_name, "status": "FAIL", "error": str(e)})
            return False

    def test_ledger_structure(self):
        """Verify ledger has complete structure for calculations"""
        test_name = "Ledger Calculation Structure"
        try:
            r = self.api.get("/api/license-ledger/", timeout=60)
            if r.status_code != 200:
                self.results.append({"name": test_name, "status": "FAIL"})
                return False

            data = r.json()

            # Check structure
            has_licenses = "licenses" in data
            has_groups = "company_groups" in data
            has_totals = "grand_total" in data

            if has_licenses and has_totals:
                self.results.append({
                    "name": test_name,
                    "status": "PASS",
                    "license_groups": len(data.get("licenses", {})),
                    "has_totals": True
                })
                return True
            else:
                self.results.append({"name": test_name, "status": "FAIL"})
                return False
        except Exception as e:
            self.results.append({"name": test_name, "status": "FAIL", "error": str(e)})
            return False

    def test_report_totals(self):
        """Verify reports include proper totals"""
        test_name = "Report Summary Totals"
        try:
            r = self.api.get("/api/reports/active-licenses/", timeout=60)
            if r.status_code != 200:
                self.results.append({"name": test_name, "status": "FAIL"})
                return False

            data = r.json()

            has_summary = "summary" in data
            has_licenses = "licenses" in data

            if has_summary and has_licenses:
                self.results.append({
                    "name": test_name,
                    "status": "PASS",
                    "has_summary": True,
                    "license_count": len(data.get("licenses", []))
                })
                return True
            else:
                self.results.append({"name": test_name, "status": "FAIL"})
                return False
        except Exception as e:
            self.results.append({"name": test_name, "status": "FAIL", "error": str(e)})
            return False

    def test_item_pivot_report(self):
        """Verify item pivot report structure for calculations"""
        test_name = "Item Pivot Report Structure"
        try:
            r = self.api.get("/api/reports/item-pivot/", timeout=60)
            if r.status_code != 200:
                self.results.append({"name": test_name, "status": "FAIL", "status_code": r.status_code})
                return False

            data = r.json()

            # Should have items and structure
            is_dict = isinstance(data, dict)
            has_data = len(str(data)) > 100

            if is_dict and has_data:
                self.results.append({"name": test_name, "status": "PASS"})
                return True
            else:
                self.results.append({"name": test_name, "status": "FAIL"})
                return False
        except Exception as e:
            self.results.append({"name": test_name, "status": "FAIL", "error": str(e)})
            return False

class TestPhase18:
    def test_business_calculations(self, api_client):
        tester = BusinessCalculationsTester(api_client)

        print("\n" + "="*70)
        print("PHASE 18: BUSINESS CALCULATIONS VERIFICATION")
        print("="*70)

        print("\n[CALCULATION STRUCTURE TESTS]")
        tester.test_license_count()
        tester.test_allotment_structure()
        tester.test_ledger_structure()
        tester.test_report_totals()
        tester.test_item_pivot_report()

        print("\n" + "="*70)
        print("PHASE 18 RESULTS")
        print("="*70)

        for result in tester.results:
            status_symbol = "✓" if result["status"] == "PASS" else "⚠" if result["status"] == "SKIP" else "✗"
            print(f"\n{status_symbol} {result['name']}")
            print(f"   Status: {result['status']}")

        passed = sum(1 for r in tester.results if r["status"] == "PASS")

        print(f"\n{'='*70}")
        print(f"Summary: {passed}/5 PASS")
        print("="*70)

        assert passed >= 4, f"Business calculations: {passed}/5 PASS"
        print(f"\n✓ PHASE 18: Business calculation structures verified ({passed}/5)")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
