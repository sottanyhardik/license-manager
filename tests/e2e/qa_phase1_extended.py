#!/usr/bin/env python3
"""
Phase 1 Extended: Systematic testing of all remaining routes.
Tests loading, interaction discovery, form presence, API operations.
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
    """Get authenticated tokens."""
    r = requests.post(
        f"{backend_url}/api/auth/login/",
        json={"username": "hardik", "password": "admin@123"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip(f"Backend login failed: {r.status_code}")
    return r.json()


@pytest.fixture
def authenticated_browser(auth_payload):
    """Pre-authenticated browser."""
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
        "localStorage.setItem('access', arguments[0]);"
        "localStorage.setItem('refresh', arguments[1]);",
        auth_payload["access"],
        auth_payload["refresh"],
    )

    yield driver
    driver.quit()


class Phase1Tester:
    """Phase 1 comprehensive route tester."""

    def __init__(self, driver, frontend_url="http://localhost:5173"):
        self.driver = driver
        self.frontend_url = frontend_url
        self.wait = WebDriverWait(driver, 10)
        self.results = {
            "routes_tested": 0,
            "routes_passed": [],
            "routes_failed": [],
            "forms_found": {},
            "buttons_found": {},
            "api_calls": {},
        }

    def navigate(self, path):
        """Navigate and stabilize."""
        self.driver.get(f"{self.frontend_url}{path}")
        time.sleep(1.5)

    def test_route(self, path, name):
        """Test route loading and content."""
        self.results["routes_tested"] += 1

        try:
            self.navigate(path)

            # Check for errors
            try:
                self.driver.find_element(By.XPATH, "//*[contains(text(), 'Something went wrong')]")
                self.results["routes_failed"].append({"path": path, "reason": "Error boundary"})
                return False
            except NoSuchElementException:
                pass

            # Check page source length
            if len(self.driver.page_source) < 500:
                self.results["routes_failed"].append({"path": path, "reason": "Minimal content"})
                return False

            # Discover interactive elements
            forms = self.discover_forms()
            buttons = self.discover_buttons()

            if forms:
                self.results["forms_found"][path] = forms
            if buttons:
                self.results["buttons_found"][path] = buttons

            self.results["routes_passed"].append(path)
            return True

        except TimeoutException:
            self.results["routes_failed"].append({"path": path, "reason": "Timeout"})
            return False
        except Exception as e:
            self.results["routes_failed"].append({"path": path, "reason": str(e)})
            return False

    def discover_forms(self):
        """Find forms on page."""
        try:
            forms = self.driver.find_elements(By.TAG_NAME, "form")
            return [{"tag": "form", "id": f.get_attribute("id")} for f in forms[:3]]
        except:
            return []

    def discover_buttons(self):
        """Find interactive buttons."""
        try:
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            return [{"text": b.text[:50], "type": b.get_attribute("type")} for b in buttons[:5]]
        except:
            return []


class TestPhase1Extended:
    """Extended Phase 1 testing."""

    # All routes to test in Phase 1
    ROUTES = [
        # Already tested
        ("/dashboard", "Dashboard"),
        ("/licenses", "Licenses"),
        ("/allotments", "Allotments"),
        ("/bill-of-entries", "BOE"),
        ("/trades", "Trades"),
        ("/license-ledger", "Ledger"),
        ("/reports/item-pivot", "Item Pivot"),
        ("/reports/active-licenses", "Active Licenses"),
        ("/reconciliation", "Reconciliation"),
        ("/admin/users", "Users"),

        # Remaining critical routes
        ("/licenses/create", "Create License"),
        ("/allotments/create", "Create Allotment"),
        ("/bill-of-entries/create", "Create BOE"),
        ("/trades/create", "Create Trade"),
        ("/login", "Login"),
        ("/profile", "Profile"),
        ("/settings", "Settings"),
        ("/ledger-upload", "Ledger Upload"),
        ("/reports/parle/sion-e1", "SION E1"),
        ("/reports/parle/sion-e5", "SION E5"),
        ("/reports/parle/sion-e132", "SION E132"),
        ("/reports/expiring-licenses", "Expiring Licenses"),
        ("/reconciliation-issues", "Reconciliation Issues"),
        ("/admin/activity-log", "Activity Log"),
    ]

    def test_all_remaining_routes(self, authenticated_browser):
        """Test all routes systematically."""
        tester = Phase1Tester(authenticated_browser)

        passed = 0
        failed = 0

        for path, name in self.ROUTES:
            if tester.test_route(path, name):
                print(f"✓ {name:30} {path}")
                passed += 1
            else:
                print(f"✗ {name:30} {path}")
                failed += 1

        print(f"\n{'='*70}")
        print(f"Routes Passed: {passed}/{len(self.ROUTES)}")
        print(f"Routes Failed: {failed}/{len(self.ROUTES)}")
        print(f"Forms Discovered: {len(tester.results['forms_found'])}")
        print(f"Buttons Discovered: {len(tester.results['buttons_found'])}")

        if tester.results["routes_failed"]:
            print(f"\nFailed Routes:")
            for failure in tester.results["routes_failed"]:
                print(f"  {failure['path']}: {failure['reason']}")

        # 90% pass rate expected
        pass_rate = passed / len(self.ROUTES)
        assert pass_rate >= 0.90, f"Pass rate {pass_rate:.1%} below 90%"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
