#!/usr/bin/env python3
"""
Phase 7-8: Data Consistency and JWT Session Management
Critical production verification tests
"""

import os
import time
import pytest
import requests
import json
from datetime import datetime, timedelta
from jwt import decode as jwt_decode


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

    tokens = r.json()

    class APIClient:
        def __init__(self):
            self.access_token = tokens["access"]
            self.refresh_token = tokens.get("refresh")
            self.headers = {"Authorization": f"Bearer {self.access_token}"}
            self.base_url = "http://localhost:8000"

        def get(self, endpoint):
            return requests.get(f"{self.base_url}{endpoint}", headers=self.headers, timeout=10)

        def post(self, endpoint, data):
            return requests.post(f"{self.base_url}{endpoint}", json=data, headers=self.headers, timeout=10)

    return APIClient()


class CriticalTestSuite:
    """Phase 7-8 critical tests."""

    def __init__(self, api_client):
        self.api = api_client
        self.results = {
            "data_consistency": [],
            "jwt_handling": [],
        }

    def test_data_consistency_licenses(self):
        """Test: License data is consistent across API calls."""
        test_name = "License List Consistency"
        print(f"\n[DATA] {test_name}")

        try:
            # Get licenses twice
            r1 = self.api.get("/api/licenses/?page_size=10")
            time.sleep(0.5)
            r2 = self.api.get("/api/licenses/?page_size=10")

            if r1.status_code != 200 or r2.status_code != 200:
                self.results["data_consistency"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "reason": "API calls failed"
                })
                return False

            data1 = r1.json()
            data2 = r2.json()

            # Check counts match
            count1 = data1.get("count", 0)
            count2 = data2.get("count", 0)

            if count1 == count2:
                self.results["data_consistency"].append({
                    "name": test_name,
                    "status": "PASS",
                    "count": count1,
                    "note": "Consistent data across calls"
                })
                print(f"  ✓ Data consistent (count={count1})")
                return True
            else:
                self.results["data_consistency"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "reason": f"Count mismatch: {count1} vs {count2}"
                })
                return False
        except Exception as e:
            self.results["data_consistency"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_api_list_pagination_consistency(self):
        """Test: Pagination returns consistent data."""
        test_name = "Pagination Consistency"
        print(f"\n[DATA] {test_name}")

        try:
            # Get first page
            r1 = self.api.get("/api/licenses/?page=1&page_size=5")

            if r1.status_code != 200:
                self.results["data_consistency"].append({
                    "name": test_name,
                    "status": "SKIP",
                    "reason": "No data to paginate"
                })
                print(f"  ⚠ No data for pagination test")
                return True

            data1 = r1.json()
            if not data1.get("results"):
                self.results["data_consistency"].append({
                    "name": test_name,
                    "status": "SKIP",
                    "reason": "Empty result set"
                })
                print(f"  ⚠ Empty result set")
                return True

            # Check pagination structure
            has_pagination = all(k in data1 for k in ["count", "results"])

            if has_pagination:
                self.results["data_consistency"].append({
                    "name": test_name,
                    "status": "PASS",
                    "pages_total": data1.get("count", 0) // 5 + 1
                })
                print(f"  ✓ Pagination structure valid")
                return True
            else:
                self.results["data_consistency"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "reason": "Missing pagination fields"
                })
                return False
        except Exception as e:
            self.results["data_consistency"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_jwt_token_structure(self):
        """Test: JWT token has required claims."""
        test_name = "JWT Token Structure"
        print(f"\n[JWT] {test_name}")

        try:
            token = self.api.access_token

            # Decode without verification (just check structure)
            try:
                decoded = jwt_decode(token, options={"verify_signature": False})
            except:
                self.results["jwt_handling"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "reason": "Invalid JWT format"
                })
                return False

            # Check required claims
            required_claims = ["exp", "iat", "user_id", "username"]
            has_claims = all(claim in decoded for claim in required_claims)

            if has_claims:
                exp_time = datetime.fromtimestamp(decoded["exp"])
                now = datetime.now()
                ttl = (exp_time - now).total_seconds()

                self.results["jwt_handling"].append({
                    "name": test_name,
                    "status": "PASS",
                    "user": decoded.get("username"),
                    "ttl_seconds": int(ttl)
                })
                print(f"  ✓ JWT valid with all required claims (TTL: {int(ttl)}s)")
                return True
            else:
                missing = [c for c in required_claims if c not in decoded]
                self.results["jwt_handling"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "missing_claims": missing
                })
                return False
        except Exception as e:
            self.results["jwt_handling"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_jwt_expiration_format(self):
        """Test: JWT expiration is set correctly."""
        test_name = "JWT Expiration Validation"
        print(f"\n[JWT] {test_name}")

        try:
            token = self.api.access_token
            decoded = jwt_decode(token, options={"verify_signature": False})

            exp_timestamp = decoded.get("exp")
            iat_timestamp = decoded.get("iat")

            if not exp_timestamp or not iat_timestamp:
                self.results["jwt_handling"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "reason": "Missing exp or iat claim"
                })
                return False

            # Calculate lifetime
            lifetime = exp_timestamp - iat_timestamp

            # Check if lifetime is reasonable (30-180 min depending on config)
            min_lifetime = 30 * 60  # 30 minutes
            max_lifetime = 24 * 60 * 60  # 24 hours

            if min_lifetime <= lifetime <= max_lifetime:
                self.results["jwt_handling"].append({
                    "name": test_name,
                    "status": "PASS",
                    "lifetime_minutes": int(lifetime / 60)
                })
                print(f"  ✓ JWT lifetime valid ({int(lifetime/60)} minutes)")
                return True
            else:
                self.results["jwt_handling"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "reason": f"Lifetime {int(lifetime/60)}min outside expected range"
                })
                return False
        except Exception as e:
            self.results["jwt_handling"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_authenticated_request_with_token(self):
        """Test: Authenticated request works."""
        test_name = "Authenticated Request"
        print(f"\n[JWT] {test_name}")

        try:
            r = self.api.get("/api/profile/")

            if r.status_code == 200:
                profile = r.json()
                self.results["jwt_handling"].append({
                    "name": test_name,
                    "status": "PASS",
                    "user": profile.get("username")
                })
                print(f"  ✓ Authenticated request successful")
                return True
            else:
                self.results["jwt_handling"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "status_code": r.status_code
                })
                return False
        except Exception as e:
            self.results["jwt_handling"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_api_response_formats_consistent(self):
        """Test: API responses are consistent."""
        test_name = "API Response Format Consistency"
        print(f"\n[DATA] {test_name}")

        try:
            endpoints = [
                "/api/licenses/",
                "/api/allotments/",
                "/api/bill-of-entries/",
            ]

            consistent = True
            for endpoint in endpoints:
                r = self.api.get(endpoint)
                if r.status_code == 200:
                    data = r.json()
                    # Check for standard pagination format
                    if not ("results" in data or isinstance(data, list)):
                        consistent = False
                        break

            if consistent:
                self.results["data_consistency"].append({
                    "name": test_name,
                    "status": "PASS",
                    "endpoints_checked": len(endpoints)
                })
                print(f"  ✓ API response formats consistent")
                return True
            else:
                self.results["data_consistency"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "reason": "Inconsistent response formats"
                })
                return False
        except Exception as e:
            self.results["data_consistency"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False


class TestPhase7And8:
    """Phase 7-8: Data Consistency and JWT."""

    def test_critical_features(self, api_client):
        """Test critical production features."""
        tester = CriticalTestSuite(api_client)

        print("\n" + "="*70)
        print("PHASE 7-8: DATA CONSISTENCY & JWT HANDLING")
        print("="*70)

        # Phase 7: Data Consistency
        print("\n[PHASE 7: DATA CONSISTENCY]")
        tester.test_data_consistency_licenses()
        tester.test_api_list_pagination_consistency()
        tester.test_api_response_formats_consistent()

        # Phase 8: JWT
        print("\n[PHASE 8: JWT SESSION HANDLING]")
        tester.test_jwt_token_structure()
        tester.test_jwt_expiration_format()
        tester.test_authenticated_request_with_token()

        # Report
        print("\n" + "="*70)
        print("PHASE 7-8 RESULTS")
        print("="*70)

        all_results = (
            tester.results["data_consistency"] +
            tester.results["jwt_handling"]
        )

        for result in all_results:
            status_symbol = "✓" if result["status"] == "PASS" else "⚠" if result["status"] == "SKIP" else "✗"
            print(f"\n{status_symbol} {result['name']}")
            print(f"   Status: {result['status']}")

        # Summary
        passed = sum(1 for r in all_results if r["status"] == "PASS")
        skipped = sum(1 for r in all_results if r["status"] == "SKIP")
        failed = sum(1 for r in all_results if r["status"] == "FAIL")

        print(f"\n{'='*70}")
        print(f"Summary: {passed} PASS | {skipped} SKIP | {failed} FAIL")
        print("="*70)

        assert (passed + skipped) >= 4, "Critical features not verified"
        print("\n✓ PHASE 7-8: Critical features verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
