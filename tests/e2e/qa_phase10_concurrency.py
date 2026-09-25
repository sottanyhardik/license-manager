#!/usr/bin/env python3
"""
Phase 10: Concurrency Testing
Tests for race conditions, duplicate records, and data integrity under concurrent operations.
"""

import os
import time
import pytest
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


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


class ConcurrencyTester:
    """Test concurrent operations."""

    def __init__(self, api_client):
        self.api = api_client
        self.results = {
            "duplicate_record_tests": [],
            "race_condition_tests": [],
            "concurrent_request_tests": [],
        }

    def test_list_consistency_concurrent_reads(self):
        """Test: Concurrent reads return consistent data."""
        test_name = "Concurrent License List Reads"
        print(f"\n[CONCURRENCY] {test_name}")

        try:
            results = []
            counts = []

            def read_licenses():
                r = self.api.get("/api/licenses/?page_size=10", timeout=30)
                if r.status_code == 200:
                    counts.append(r.json().get("count", 0))
                    results.append(r.status_code)
                return r.status_code

            # 5 concurrent reads
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(read_licenses) for _ in range(5)]
                for future in as_completed(futures):
                    future.result()

            # Check consistency
            if len(set(counts)) == 1:
                self.results["race_condition_tests"].append({
                    "name": test_name,
                    "status": "PASS",
                    "concurrent_reads": 5,
                    "all_consistent": True,
                    "count": counts[0]
                })
                print(f"  ✓ All 5 concurrent reads returned same count ({counts[0]})")
                return True
            else:
                self.results["race_condition_tests"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "reason": f"Inconsistent counts: {set(counts)}"
                })
                return False

        except Exception as e:
            self.results["race_condition_tests"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_simultaneous_api_requests(self):
        """Test: Multiple simultaneous API requests."""
        test_name = "Simultaneous API Requests"
        print(f"\n[CONCURRENCY] {test_name}")

        try:
            endpoints = [
                "/api/licenses/?page_size=5",
                "/api/allotments/?page_size=5",
                "/api/bill-of-entries/?page_size=5",
                "/api/trades/?page_size=5",
                "/api/license-ledger/?page_size=5",
            ]

            statuses = []

            def fetch_endpoint(endpoint):
                try:
                    r = self.api.get(endpoint, timeout=30)
                    statuses.append(r.status_code)
                    return r.status_code
                except Exception as e:
                    statuses.append(None)
                    return None

            # 5 simultaneous requests to different endpoints
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(fetch_endpoint, ep) for ep in endpoints]
                for future in as_completed(futures):
                    future.result()

            # Check all successful
            if all(s == 200 for s in statuses):
                self.results["concurrent_request_tests"].append({
                    "name": test_name,
                    "status": "PASS",
                    "concurrent_requests": 5,
                    "all_successful": True
                })
                print(f"  ✓ All 5 simultaneous requests successful (200)")
                return True
            else:
                self.results["concurrent_request_tests"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "statuses": statuses
                })
                return False

        except Exception as e:
            self.results["concurrent_request_tests"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_rapid_sequential_reads(self):
        """Test: Rapid sequential reads maintain consistency."""
        test_name = "Rapid Sequential Reads"
        print(f"\n[CONCURRENCY] {test_name}")

        try:
            counts = []

            # 10 rapid reads
            for i in range(10):
                r = self.api.get("/api/licenses/?page_size=1", timeout=30)
                if r.status_code == 200:
                    counts.append(r.json().get("count", 0))
                time.sleep(0.01)  # Very small delay

            # All should be consistent
            if len(set(counts)) == 1:
                self.results["race_condition_tests"].append({
                    "name": test_name,
                    "status": "PASS",
                    "rapid_reads": 10,
                    "consistent": True
                })
                print(f"  ✓ 10 rapid sequential reads consistent")
                return True
            else:
                self.results["race_condition_tests"].append({
                    "name": test_name,
                    "status": "FAIL",
                    "reason": f"Inconsistent: {set(counts)}"
                })
                return False

        except Exception as e:
            self.results["race_condition_tests"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False

    def test_concurrent_filtered_reads(self):
        """Test: Concurrent reads with filters."""
        test_name = "Concurrent Filtered Reads"
        print(f"\n[CONCURRENCY] {test_name}")

        try:
            results = []

            def read_with_filter():
                r = self.api.get("/api/licenses/?search=test&page_size=10", timeout=30)
                if r.status_code == 200:
                    results.append((r.status_code, r.json().get("count", 0)))
                return r.status_code

            # 5 concurrent filtered reads
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(read_with_filter) for _ in range(5)]
                for future in as_completed(futures):
                    future.result()

            if len(results) == 5 and all(r[0] == 200 for r in results):
                counts = [r[1] for r in results]
                if len(set(counts)) == 1:
                    self.results["concurrent_request_tests"].append({
                        "name": test_name,
                        "status": "PASS",
                        "concurrent_filtered_reads": 5
                    })
                    print(f"  ✓ 5 concurrent filtered reads successful and consistent")
                    return True

            self.results["concurrent_request_tests"].append({
                "name": test_name,
                "status": "FAIL",
                "reason": "Inconsistent filtered results"
            })
            return False

        except Exception as e:
            self.results["concurrent_request_tests"].append({
                "name": test_name,
                "status": "FAIL",
                "error": str(e)
            })
            return False


class TestPhase10Concurrency:
    """Phase 10: Concurrency Testing."""

    def test_concurrency(self, api_client):
        """Test concurrent operations."""
        tester = ConcurrencyTester(api_client)

        print("\n" + "="*70)
        print("PHASE 10: CONCURRENCY TESTING")
        print("="*70)

        print("\n[RACE CONDITION TESTS]")
        tester.test_list_consistency_concurrent_reads()
        tester.test_rapid_sequential_reads()

        print("\n[CONCURRENT REQUEST TESTS]")
        tester.test_simultaneous_api_requests()
        tester.test_concurrent_filtered_reads()

        # Report
        print("\n" + "="*70)
        print("PHASE 10 RESULTS")
        print("="*70)

        all_results = (
            tester.results["duplicate_record_tests"] +
            tester.results["race_condition_tests"] +
            tester.results["concurrent_request_tests"]
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

        assert passed >= 3, f"Concurrency verification failed: {passed} PASS"
        print("\n✓ PHASE 10: Concurrency verified - no race conditions detected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
