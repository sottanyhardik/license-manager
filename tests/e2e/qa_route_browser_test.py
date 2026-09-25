#!/usr/bin/env python3
"""
Browser-based comprehensive route and interaction testing.
Uses pre-authenticated driver with localStorage tokens.
"""

import os
import json
import time
import pytest
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


@pytest.fixture(scope="session")
def auth_payload(backend_url="http://localhost:8000"):
    """Get authenticated tokens via API."""
    r = requests.post(
        f"{backend_url}/api/auth/login/",
        json={"username": "hardik", "password": "admin@123"},
        timeout=10,
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()


@pytest.fixture
def authenticated_browser(auth_payload):
    """Create a pre-authenticated browser session."""
    options = Options()
    if os.getenv("LM_HEADLESS", "1") == "1":
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,900")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)

    # Navigate to frontend and inject tokens
    frontend_url = os.getenv("LM_FRONTEND_URL", "http://localhost:5173")
    driver.get(f"{frontend_url}/login")

    # Inject authentication into localStorage
    driver.execute_script(
        "localStorage.setItem('access', arguments[0]);"
        "localStorage.setItem('refresh', arguments[1]);"
        "localStorage.setItem('user', arguments[2]);",
        auth_payload["access"],
        auth_payload["refresh"],
        json.dumps(auth_payload.get("user", {})),
    )

    yield driver
    driver.quit()


class RouteQATester:
    """Test routes and page functionality."""

    def __init__(self, driver, frontend_url="http://localhost:5173"):
        self.driver = driver
        self.frontend_url = frontend_url
        self.wait = WebDriverWait(driver, 10)
        self.results = {
            "routes_tested": 0,
            "routes_passed": [],
            "routes_failed": [],
            "interactions_tested": 0,
            "interactions_passed": 0,
            "interactions_failed": [],
        }

    def navigate_and_wait(self, path):
        """Navigate and wait for page to load."""
        self.driver.get(f"{self.frontend_url}{path}")
        time.sleep(1)

        # Wait for main content
        try:
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//main | //*[@role='main']"))
            )
            return True
        except TimeoutException:
            return False

    def check_errors(self):
        """Check for console errors and error boundary."""
        # Check for error boundary
        try:
            self.driver.find_element(By.XPATH, "//*[contains(text(), 'Something went wrong')]")
            return True  # Error found
        except NoSuchElementException:
            return False  # No error

    def get_page_title(self):
        """Get current page title."""
        return self.driver.find_element(By.TAG_NAME, "h1").text if self.driver.find_elements(By.TAG_NAME, "h1") else "Unknown"

    def test_route(self, path, expected_title_partial=None):
        """Test a single route."""
        self.results["routes_tested"] += 1

        try:
            if not self.navigate_and_wait(path):
                self.results["routes_failed"].append({
                    "path": path,
                    "reason": "Page did not load within timeout"
                })
                return False

            # Check for errors
            if self.check_errors():
                self.results["routes_failed"].append({
                    "path": path,
                    "reason": "Error boundary shown"
                })
                return False

            # Verify some content loaded (page source should have reasonable length)
            page_source = self.driver.page_source
            if len(page_source) < 500:
                self.results["routes_failed"].append({
                    "path": path,
                    "reason": f"Minimal content loaded (page source length: {len(page_source)})"
                })
                return False

            self.results["routes_passed"].append(path)
            return True

        except Exception as e:
            self.results["routes_failed"].append({
                "path": path,
                "reason": str(e)
            })
            return False

    def test_button(self, selector, button_name):
        """Test clicking a button."""
        self.results["interactions_tested"] += 1
        try:
            button = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
            button.click()
            time.sleep(0.5)
            self.results["interactions_passed"] += 1
            return True
        except Exception as e:
            self.results["interactions_failed"].append({
                "element": button_name,
                "reason": str(e)
            })
            return False

    def test_input(self, selector, value):
        """Test filling an input field."""
        self.results["interactions_tested"] += 1
        try:
            field = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            field.clear()
            field.send_keys(value)
            self.results["interactions_passed"] += 1
            return True
        except Exception as e:
            self.results["interactions_failed"].append({
                "element": selector,
                "reason": str(e)
            })
            return False

    def report(self):
        """Print test results."""
        print("\n" + "="*80)
        print("COMPREHENSIVE ROUTE QA RESULTS")
        print("="*80)
        print(f"\nROUTES TESTED: {self.results['routes_tested']}")
        print(f"  ✓ PASSED: {len(self.results['routes_passed'])}")
        print(f"  ✗ FAILED: {len(self.results['routes_failed'])}")

        if self.results["routes_failed"]:
            print("\nFailed Routes:")
            for failure in self.results["routes_failed"]:
                print(f"  {failure['path']} - {failure['reason']}")

        print(f"\nINTERACTIONS TESTED: {self.results['interactions_tested']}")
        print(f"  ✓ PASSED: {self.results['interactions_passed']}")
        print(f"  ✗ FAILED: {len(self.results['interactions_failed'])}")

        if self.results["interactions_failed"]:
            print("\nFailed Interactions:")
            for failure in self.results["interactions_failed"]:
                print(f"  {failure['element']} - {failure['reason']}")


class TestRoutesCritical:
    """Critical route tests."""

    def test_core_routes(self, authenticated_browser):
        """Test core application routes."""
        tester = RouteQATester(authenticated_browser)

        # Core routes
        core_routes = [
            "/dashboard",
            "/licenses",
            "/allotments",
            "/bill-of-entries",
            "/trades",
            "/license-ledger",
            "/reports/item-pivot",
            "/reports/active-licenses",
            "/reconciliation",
            "/admin/users",
        ]

        for route in core_routes:
            passed = tester.test_route(route)
            print(f"{'✓' if passed else '✗'} {route}")

        tester.report()

        # At least 80% should pass
        pass_rate = len(tester.results["routes_passed"]) / tester.results["routes_tested"]
        assert pass_rate >= 0.8, f"Route pass rate too low: {pass_rate:.1%}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
