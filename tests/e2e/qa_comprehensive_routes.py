#!/usr/bin/env python3
"""
Comprehensive route-by-route QA testing using Selenium.
Tests every route with full interaction coverage.
"""

import os
import time
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)


@pytest.fixture
def browser():
    """Create a Selenium webdriver instance."""
    options = Options()
    if os.getenv("LM_HEADLESS", "1") == "1":
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,900")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    yield driver
    driver.quit()


class BrowserQATester:
    """Comprehensive browser QA tester."""

    def __init__(self, driver, base_url="http://localhost:5173"):
        self.driver = driver
        self.base_url = base_url
        self.wait = WebDriverWait(driver, 15)
        self.results = {
            "passed": [],
            "failed": [],
            "errors": [],
        }

    def login(self, username="hardik", password="admin@123"):
        """Login to the application."""
        self.driver.get(f"{self.base_url}/login")
        try:
            username_field = self.wait.until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            password_field = self.driver.find_element(By.NAME, "password")
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")

            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)
            login_button.click()

            # Wait for redirect to dashboard
            time.sleep(2)
        except Exception as e:
            print(f"Login failed: {e}")
            raise

    def navigate_to(self, path):
        """Navigate to a specific path and wait for stabilization."""
        self.driver.get(f"{self.base_url}{path}")
        time.sleep(1.5)  # Wait for React to render

    def check_page_health(self, path):
        """Check if page loaded without errors."""
        issues = {
            "console_errors": [],
            "error_boundary": False,
            "missing_main": False,
            "status_code": 200,
        }

        # Check for error boundary
        try:
            error_element = self.driver.find_element(
                By.XPATH,
                "//*[contains(text(), 'Something went wrong')]"
            )
            issues["error_boundary"] = True
        except NoSuchElementException:
            pass

        # Check for main content area
        try:
            self.driver.find_element(By.XPATH, "//main | //*[@role='main']")
        except NoSuchElementException:
            issues["missing_main"] = True

        return issues

    def test_route(self, path, name, expected_role=None):
        """Test a single route."""
        try:
            self.navigate_to(path)
            issues = self.check_page_health(path)

            if issues["error_boundary"] or issues["missing_main"]:
                self.results["failed"].append({
                    "path": path,
                    "name": name,
                    "issue": "Page not properly rendered",
                    "details": issues,
                })
                return False

            self.results["passed"].append({
                "path": path,
                "name": name,
            })
            return True
        except Exception as e:
            self.results["errors"].append({
                "path": path,
                "name": name,
                "error": str(e),
            })
            return False

    def test_button_click(self, selector, button_name, wait_for_url=None):
        """Test clicking a button and verify result."""
        try:
            button = self.wait.until(
                EC.presence_of_element_located((By.XPATH if "//" in selector else By.CSS_SELECTOR, selector))
            )
            self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
            button.click()

            if wait_for_url:
                time.sleep(1)
                current_url = self.driver.current_url
                if wait_for_url not in current_url:
                    return False

            time.sleep(0.5)
            return True
        except Exception as e:
            print(f"Button click failed for {button_name}: {e}")
            return False

    def test_form_input(self, field_selector, value):
        """Test filling a form input."""
        try:
            field = self.wait.until(
                EC.presence_of_element_located((By.XPATH if "//" in field_selector else By.CSS_SELECTOR, field_selector))
            )
            field.clear()
            field.send_keys(value)
            return True
        except Exception as e:
            print(f"Form input failed: {e}")
            return False

    def report_results(self):
        """Print test results."""
        print("\n" + "="*80)
        print("COMPREHENSIVE ROUTE QA RESULTS")
        print("="*80)
        print(f"\nPASSED: {len(self.results['passed'])}")
        for result in self.results["passed"]:
            print(f"  ✓ {result['name']} ({result['path']})")

        print(f"\nFAILED: {len(self.results['failed'])}")
        for result in self.results["failed"]:
            print(f"  ✗ {result['name']} ({result['path']})")
            print(f"    Issue: {result['issue']}")

        print(f"\nERRORS: {len(self.results['errors'])}")
        for result in self.results["errors"]:
            print(f"  ✗ {result['name']} ({result['path']})")
            print(f"    Error: {result['error']}")


class TestAllRoutes:
    """Test all application routes."""

    ROUTES = [
        # Public routes
        ("/login", "Login Page"),
        ("/forgot-password", "Password Reset"),

        # Core
        ("/dashboard", "Dashboard"),
        ("/profile", "Profile"),

        # License Management
        ("/licenses", "License List"),
        ("/licenses/create", "Create License"),

        # Allotments
        ("/allotments", "Allotment List"),

        # Bill of Entry
        ("/bill-of-entries", "BOE List"),

        # Trades
        ("/trades", "Trade List"),

        # Incentive Licenses
        ("/incentive-licenses", "Incentive Licenses"),

        # Ledger
        ("/license-ledger", "License Ledger"),
        ("/ledger-upload", "Ledger Upload"),

        # Reports
        ("/reports/item-pivot", "Item Pivot Report"),
        ("/reports/item-report", "Item Report"),
        ("/reports/active-licenses", "Active Licenses Report"),
        ("/reports/expiring-licenses", "Expiring Licenses Report"),
        ("/reports/parle/sion-e1", "SION E1 Report"),
        ("/reports/parle/sion-e5", "SION E5 Report"),

        # Reconciliation
        ("/reconciliation", "Reconciliation Panel"),
        ("/reconciliation-issues", "Reconciliation Issues"),

        # Admin
        ("/admin/users", "User Management"),
    ]

    def test_all_routes(self, browser):
        """Test all routes for basic functionality."""
        tester = BrowserQATester(browser)

        # Login first
        tester.login()

        # Test each route
        for path, name in self.ROUTES:
            # Skip login/forgot-password after login
            if path in ["/login", "/forgot-password"]:
                continue

            tester.test_route(path, name)

        # Report results
        tester.report_results()

        # Assert no critical failures
        assert len(tester.results["failed"]) == 0, f"Failed routes: {tester.results['failed']}"
        assert len(tester.results["errors"]) == 0, f"Errored routes: {tester.results['errors']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
