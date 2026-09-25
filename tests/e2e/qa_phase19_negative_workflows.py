#!/usr/bin/env python3
"""
Phase 19: Negative Workflows Testing
Tests invalid inputs, error conditions, and edge cases.
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

        def post(self, endpoint, data, timeout=30):
            return requests.post(f"{self.base_url}{endpoint}", json=data, headers=self.headers, timeout=timeout)

    return APIClient()


class NegativeWorkflowsTester:
    """Test negative scenarios and error cases."""

    def __init__(self, api_client):
        self.api = api_client
        self.results = {
            "invalid_input_tests": [],
            "missing_field_tests": [],
            "edge_case_tests": [],
        }

    def test_invalid_license_id(self):
        """Test: Invalid license ID returns 404."""
        test_name = "Invalid License ID"
        print(f"\n[NEGATIVE] {test_name}")

        try:
            # Try to access non-existent license
            r = self.api.get("/api/licenses/99999999/")

            if r.status_code == 404:
                self.results["invalid_input_tests"].append({
                    "name": test_name,
                    "status": "PASS",
                    "returns_404": True
                })
                print(f"  ✓ Returns 404 for invalid ID")
                return True
            else:
                self.results["invalid_input_tests"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "expected": 404,
                    "got": r.status_code
                })
                return False
        except Exception as e:
            self.results["invalid_input_tests"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_empty_post_request(self):
        """Test: Empty POST to create endpoint returns validation error."""
        test_name = "Empty POST Request"
        print(f"\n[NEGATIVE] {test_name}")

        try:
            # Try to create with no data
            r = self.api.post("/api/licenses/", {})

            if r.status_code in [400, 422]:
                self.results["missing_field_tests"].append({
                    "name": test_name,
                    "status": "PASS",
                    "returns_error": True,
                    "error_code": r.status_code
                })
                print(f"  ✓ Returns {r.status_code} for empty POST")
                return True
            else:
                self.results["missing_field_tests"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "reason": f"Expected error, got {r.status_code}"
                })
                return False
        except Exception as e:
            self.results["missing_field_tests"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_invalid_query_parameters(self):
        """Test: Invalid query parameters handled gracefully."""
        test_name = "Invalid Query Parameters"
        print(f"\n[NEGATIVE] {test_name}")

        try:
            # Try invalid page number
            r1 = self.api.get("/api/licenses/?page=999999")

            # Try invalid page size
            r2 = self.api.get("/api/licenses/?page_size=999999")

            # Both should return 200 with empty/adjusted results
            if r1.status_code == 200 and r2.status_code == 200:
                self.results["edge_case_tests"].append({
                    "name": test_name,
                    "status": "PASS",
                    "invalid_params_handled": True
                })
                print(f"  ✓ Invalid params handled gracefully (200)")
                return True
            else:
                self.results["edge_case_tests"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "r1": r1.status_code,
                    "r2": r2.status_code
                })
                return False
        except Exception as e:
            self.results["edge_case_tests"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_search_with_special_characters(self):
        """Test: Search handles special characters."""
        test_name = "Search with Special Characters"
        print(f"\n[NEGATIVE] {test_name}")

        try:
            # Try search with special characters
            r = self.api.get("/api/licenses/?search=<>\"'%&")

            if r.status_code == 200:
                self.results["edge_case_tests"].append({
                    "name": test_name,
                    "status": "PASS",
                    "special_chars_handled": True
                })
                print(f"  ✓ Special characters in search handled")
                return True
            else:
                self.results["edge_case_tests"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "status_code": r.status_code
                })
                return False
        except Exception as e:
            self.results["edge_case_tests"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_unauthorized_access_denied(self):
        """Test: Unauthorized users get 401."""
        test_name = "Unauthorized Access"
        print(f"\n[NEGATIVE] {test_name}")

        try:
            # Try to access without token
            r = requests.get(
                "http://localhost:8000/api/licenses/",
                timeout=10
            )

            if r.status_code == 401:
                self.results["invalid_input_tests"].append({
                    "name": test_name,
                    "status": "PASS",
                    "returns_401": True
                })
                print(f"  ✓ Returns 401 for unauthorized access")
                return True
            else:
                self.results["invalid_input_tests"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "expected": 401,
                    "got": r.status_code
                })
                return False
        except Exception as e:
            self.results["invalid_input_tests"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_malformed_data_types(self):
        """Test: Sending malformed data types."""
        test_name = "Malformed Data Types"
        print(f"\n[NEGATIVE] {test_name}")

        try:
            # Send string where number expected
            r = self.api.post("/api/licenses/", {
                "number": 123,  # Should be string
                "invalid_field": "test"
            })

            if r.status_code in [400, 422]:
                self.results["missing_field_tests"].append({
                    "name": test_name,
                    "status": "PASS",
                    "validates_types": True
                })
                print(f"  ✓ Data type validation working")
                return True
            else:
                self.results["missing_field_tests"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "no_validation": True
                })
                return False
        except Exception as e:
            self.results["missing_field_tests"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False


class TestPhase19NegativeWorkflows:
    """Phase 19: Negative Workflows."""

    def test_negative_scenarios(self, api_client):
        """Test negative scenarios."""
        tester = NegativeWorkflowsTester(api_client)

        print("\n" + "="*70)
        print("PHASE 19: NEGATIVE WORKFLOWS TESTING")
        print("="*70)

        print("\n[INVALID INPUT TESTS]")
        tester.test_invalid_license_id()
        tester.test_unauthorized_access_denied()

        print("\n[MISSING FIELD TESTS]")
        tester.test_empty_post_request()
        tester.test_malformed_data_types()

        print("\n[EDGE CASE TESTS]")
        tester.test_invalid_query_parameters()
        tester.test_search_with_special_characters()

        # Report
        print("\n" + "="*70)
        print("PHASE 19 RESULTS")
        print("="*70)

        all_results = (
            tester.results["invalid_input_tests"] +
            tester.results["missing_field_tests"] +
            tester.results["edge_case_tests"]
        )

        for result in all_results:
            status_symbol = "✓" if result["status"] == "PASS" else "✗"
            print(f"\n{status_symbol} {result['name']}")
            print(f"   Status: {result['status']}")

        passed = sum(1 for r in all_results if r["status"] == "PASS")
        failed = sum(1 for r in all_results if r["status"] == "FAIL")

        print(f"\n{'='*70}")
        print(f"Summary: {passed} PASS | {failed} FAIL")
        print("="*70)

        assert passed >= 4, f"Negative workflow coverage insufficient: {passed} PASS"
        print("\n✓ PHASE 19: Negative workflows verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
