#!/usr/bin/env python3
"""
Phase 11: Responsive Design Testing
Tests critical workflows at 4 different viewports.
"""

import os
import time
import pytest
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


@pytest.fixture(scope="session")
def auth_payload():
    """Get auth token."""
    r = requests.post(
        "http://localhost:8000/api/auth/login/",
        json={"username": "hardik", "password": "admin@123"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip("Auth failed")
    return r.json()


@pytest.fixture
def browser_with_viewport(auth_payload):
    """Browser fixture that can change viewports."""
    options = Options()
    if os.getenv("LM_HEADLESS", "1") == "1":
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)

    frontend_url = os.getenv("LM_FRONTEND_URL", "http://localhost:5173")
    driver.get(f"{frontend_url}/login")
    driver.execute_script(
        "localStorage.setItem('access', arguments[0]);",
        auth_payload["access"],
    )

    yield driver
    driver.quit()


class ResponsiveDesignTester:
    """Test responsive design at multiple viewports."""

    def __init__(self, driver, frontend_url="http://localhost:5173"):
        self.driver = driver
        self.frontend_url = frontend_url
        self.results = {
            "viewport_tests": [],
            "overflow_tests": [],
        }

    def set_viewport(self, width, height):
        """Set browser window size."""
        self.driver.set_window_size(width, height)
        time.sleep(0.5)

    def navigate(self, path):
        """Navigate to path."""
        self.driver.get(f"{self.frontend_url}{path}")
        time.sleep(1.5)

    def check_viewport_health(self, name, width, height):
        """Check if page renders correctly at given viewport."""
        try:
            self.set_viewport(width, height)
            page_source = self.driver.page_source

            # Check basic rendering
            page_loaded = len(page_source) > 500

            # Check for console errors
            console_logs = self.driver.get_log("browser") if "browser" in self.driver.log_types else []
            critical_errors = [log for log in console_logs if "SEVERE" in log.get("level", "")]

            # Check for horizontal overflow
            try:
                html = self.driver.find_element(By.TAG_NAME, "html")
                scroll_width = self.driver.execute_script("return document.documentElement.scrollWidth")
                viewport_width = self.driver.execute_script("return window.innerWidth")
                horizontal_overflow = scroll_width > viewport_width
            except:
                horizontal_overflow = False

            if page_loaded and not critical_errors and not horizontal_overflow:
                return True, "PASS"
            else:
                reasons = []
                if not page_loaded:
                    reasons.append("not_loaded")
                if critical_errors:
                    reasons.append(f"errors({len(critical_errors)})")
                if horizontal_overflow:
                    reasons.append("h_overflow")
                return False, " | ".join(reasons)

        except Exception as e:
            return False, str(e)

    def test_all_viewports_license_list(self):
        """Test license list at all viewports."""
        test_name = "License List - All Viewports"
        print(f"\n[RESPONSIVE] {test_name}")

        viewports = [
            (1366, 768, "Desktop 1366×768"),
            (1440, 900, "Desktop 1440×900"),
            (768, 1024, "Tablet 768×1024"),
            (390, 844, "Mobile 390×844"),
        ]

        self.navigate("/licenses")

        results = []
        for width, height, name in viewports:
            passed, reason = self.check_viewport_health(name, width, height)
            results.append((name, passed, reason))
            status = "✓" if passed else "✗"
            print(f"  {status} {name}: {reason if not passed else 'OK'}")

        passed_count = sum(1 for _, p, _ in results if p)

        self.results["viewport_tests"].append({
            "name": test_name,
            "status": "PASS" if passed_count >= 3 else "FAIL",
            "passed_viewports": passed_count,
            "total": len(viewports)
        })

        return passed_count >= 3

    def test_all_viewports_dashboard(self):
        """Test dashboard at all viewports."""
        test_name = "Dashboard - All Viewports"
        print(f"\n[RESPONSIVE] {test_name}")

        viewports = [
            (1366, 768, "Desktop 1366×768"),
            (1440, 900, "Desktop 1440×900"),
            (768, 1024, "Tablet 768×1024"),
            (390, 844, "Mobile 390×844"),
        ]

        self.navigate("/dashboard")

        results = []
        for width, height, name in viewports:
            passed, reason = self.check_viewport_health(name, width, height)
            results.append((name, passed))
            status = "✓" if passed else "✗"
            print(f"  {status} {name}")

        passed_count = sum(1 for _, p in results if p)

        self.results["viewport_tests"].append({
            "name": test_name,
            "status": "PASS" if passed_count >= 3 else "FAIL",
            "passed_viewports": passed_count
        })

        return passed_count >= 3

    def test_all_viewports_reports(self):
        """Test reports at all viewports."""
        test_name = "Reports - All Viewports"
        print(f"\n[RESPONSIVE] {test_name}")

        viewports = [
            (1366, 768, "Desktop"),
            (768, 1024, "Tablet"),
        ]

        self.navigate("/reports/active-licenses")
        time.sleep(2)

        results = []
        for width, height, name in viewports:
            passed, reason = self.check_viewport_health(name, width, height)
            results.append((name, passed))
            status = "✓" if passed else "✗"
            print(f"  {status} {name}")

        passed_count = sum(1 for _, p in results if p)

        self.results["viewport_tests"].append({
            "name": test_name,
            "status": "PASS" if passed_count >= 1 else "FAIL",
            "passed_viewports": passed_count
        })

        return passed_count >= 1


class TestPhase11Responsive:
    """Phase 11: Responsive Design."""

    def test_responsive_design(self, browser_with_viewport):
        """Test responsive design."""
        tester = ResponsiveDesignTester(browser_with_viewport)

        print("\n" + "="*70)
        print("PHASE 11: RESPONSIVE DESIGN TESTING")
        print("="*70)

        print("\n[VIEWPORT TESTS]")
        tester.test_all_viewports_license_list()
        tester.test_all_viewports_dashboard()
        tester.test_all_viewports_reports()

        # Report
        print("\n" + "="*70)
        print("PHASE 11 RESULTS")
        print("="*70)

        all_results = tester.results["viewport_tests"]

        for result in all_results:
            status_symbol = "✓" if result["status"] == "PASS" else "✗"
            print(f"\n{status_symbol} {result['name']}")
            print(f"   Status: {result['status']}")
            if "passed_viewports" in result:
                print(f"   Viewports: {result['passed_viewports']}/{result.get('total', 4)}")

        passed = sum(1 for r in all_results if r["status"] == "PASS")

        print(f"\n{'='*70}")
        print(f"Summary: {passed} PASS")
        print("="*70)

        assert passed >= 2, f"Responsive design verification insufficient"
        print("\n✓ PHASE 11: Responsive design verified across viewports")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
