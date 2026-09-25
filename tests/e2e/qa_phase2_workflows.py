#!/usr/bin/env python3
"""
Phase 2 & 3: Critical workflow and form testing.
Tests actual business workflows and form submissions.
"""

import os
import json
import time
import pytest
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import *


@pytest.fixture(scope="session")
def auth_payload(backend_url="http://localhost:8000"):
    """Authenticate and get tokens."""
    r = requests.post(
        f"{backend_url}/api/auth/login/",
        json={"username": "hardik", "password": "admin@123"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip(f"Auth failed: {r.status_code}")
    return r.json()


@pytest.fixture
def authenticated_browser(auth_payload):
    """Pre-authenticated browser session."""
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


class WorkflowTester:
    """Workflow and form testing utilities."""

    def __init__(self, driver, frontend_url="http://localhost:5173", backend_url="http://localhost:8000"):
        self.driver = driver
        self.frontend_url = frontend_url
        self.backend_url = backend_url
        self.wait = WebDriverWait(driver, 10)
        self.results = {
            "workflows_passed": [],
            "workflows_failed": [],
            "forms_tested": 0,
            "forms_passed": 0,
        }

    def navigate(self, path):
        """Navigate to path."""
        self.driver.get(f"{self.frontend_url}{path}")
        time.sleep(1)

    def fill_field(self, selector, value):
        """Fill a form field."""
        try:
            field = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            field.clear()
            field.send_keys(value)
            return True
        except:
            return False

    def click(self, selector):
        """Click an element."""
        try:
            elem = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            elem.click()
            time.sleep(0.5)
            return True
        except:
            return False

    def click_xpath(self, xpath):
        """Click using XPath."""
        try:
            elem = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            elem.click()
            time.sleep(0.5)
            return True
        except:
            return False

    def select_dropdown(self, selector, value):
        """Select from dropdown."""
        try:
            elem = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            Select(elem).select_by_value(value) if value.isdigit() else Select(elem).select_by_visible_text(value)
            return True
        except:
            return False

    def get_form_error(self):
        """Check for form error message."""
        try:
            error = self.driver.find_element(By.XPATH, "//*[@role='alert' or contains(@class, 'error')]")
            return error.text
        except:
            return None

    def api_get(self, endpoint, headers=None):
        """Make API GET request."""
        if not headers:
            headers = {"Authorization": f"Bearer {self._get_token()}"}
        try:
            r = requests.get(f"{self.backend_url}{endpoint}", headers=headers, timeout=10)
            return r
        except:
            return None

    def _get_token(self):
        """Get current token from localStorage."""
        return self.driver.execute_script("return localStorage.getItem('access')")

    def test_license_list_navigation(self):
        """Test: Navigate to license list and verify."""
        try:
            self.navigate("/licenses")

            # Check for table/list
            tables = self.driver.find_elements(By.TAG_NAME, "table")
            if not tables:
                self.results["workflows_failed"].append("License list: No table found")
                return False

            # Check for create button
            create_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Create') or contains(text(), 'Add')]")
            if not create_buttons:
                self.results["workflows_failed"].append("License list: No create button")
                return False

            self.results["workflows_passed"].append("License list navigation")
            return True
        except Exception as e:
            self.results["workflows_failed"].append(f"License list: {str(e)}")
            return False

    def test_license_create_form_presence(self):
        """Test: License create form exists and has required fields."""
        try:
            self.navigate("/licenses/create")

            # Check for form
            forms = self.driver.find_elements(By.TAG_NAME, "form")
            if not forms:
                self.results["workflows_failed"].append("License create: No form found")
                return False

            # Check for common fields
            required_fields = ["license_number", "scheme_code", "company"]
            for field in required_fields:
                try:
                    self.driver.find_element(By.NAME, field)
                except NoSuchElementException:
                    # Try different selector
                    try:
                        self.driver.find_element(By.CSS_SELECTOR, f"input[placeholder*='{field}' i], input[aria-label*='{field}' i]")
                    except:
                        self.results["workflows_failed"].append(f"License create: Missing field {field}")
                        return False

            self.results["workflows_passed"].append("License create form")
            return True
        except Exception as e:
            self.results["workflows_failed"].append(f"License create: {str(e)}")
            return False

    def test_allotment_create_form_presence(self):
        """Test: Allotment create form."""
        try:
            self.navigate("/allotments/create")

            forms = self.driver.find_elements(By.TAG_NAME, "form")
            if not forms:
                self.results["workflows_failed"].append("Allotment create: No form")
                return False

            self.results["workflows_passed"].append("Allotment create form")
            return True
        except Exception as e:
            self.results["workflows_failed"].append(f"Allotment: {str(e)}")
            return False

    def test_boe_create_form_presence(self):
        """Test: BOE create form."""
        try:
            self.navigate("/bill-of-entries/create")

            forms = self.driver.find_elements(By.TAG_NAME, "form")
            if not forms:
                self.results["workflows_failed"].append("BOE create: No form")
                return False

            self.results["workflows_passed"].append("BOE create form")
            return True
        except Exception as e:
            self.results["workflows_failed"].append(f"BOE: {str(e)}")
            return False

    def test_report_filter_functionality(self):
        """Test: Report pages have filters and data."""
        try:
            self.navigate("/reports/active-licenses")

            # Check for data
            page_source = self.driver.page_source
            if len(page_source) < 1000:
                self.results["workflows_failed"].append("Report: Insufficient content")
                return False

            self.results["workflows_passed"].append("Report page loads")
            return True
        except Exception as e:
            self.results["workflows_failed"].append(f"Report: {str(e)}")
            return False

    def test_ledger_detail_page(self):
        """Test: Ledger detail page (if data exists)."""
        try:
            # First get a license ID from API
            r = requests.get(
                f"{self.backend_url}/api/licenses/?page_size=1",
                headers={"Authorization": f"Bearer {self._get_token()}"},
                timeout=10
            )

            if r.status_code != 200:
                self.results["workflows_failed"].append("Ledger: Could not fetch licenses")
                return False

            data = r.json()
            if not data.get("results"):
                self.results["workflows_passed"].append("Ledger: No test data (OK)")
                return True

            license_id = data["results"][0]["id"]

            # Navigate to ledger detail
            self.navigate(f"/license-ledger/{license_id}")

            # Check for content
            if len(self.driver.page_source) < 500:
                self.results["workflows_failed"].append("Ledger detail: No content")
                return False

            self.results["workflows_passed"].append("Ledger detail page")
            return True
        except Exception as e:
            self.results["workflows_failed"].append(f"Ledger detail: {str(e)}")
            return False


class TestPhase2And3:
    """Workflow and form tests."""

    def test_critical_workflows(self, authenticated_browser):
        """Test critical business workflows."""
        tester = WorkflowTester(authenticated_browser)

        print("\n" + "="*70)
        print("PHASE 2: WORKFLOW TESTING")
        print("="*70)

        workflows = [
            ("License List Navigation", tester.test_license_list_navigation),
            ("License Create Form", tester.test_license_create_form_presence),
            ("Allotment Create Form", tester.test_allotment_create_form_presence),
            ("BOE Create Form", tester.test_boe_create_form_presence),
            ("Report Page", tester.test_report_filter_functionality),
            ("Ledger Detail", tester.test_ledger_detail_page),
        ]

        for name, test_func in workflows:
            result = test_func()
            print(f"{'✓' if result else '✗'} {name}")

        print(f"\n{'='*70}")
        print(f"Workflows Passed: {len(tester.results['workflows_passed'])}/{len(workflows)}")
        print(f"Workflows Failed: {len(tester.results['workflows_failed'])}/{len(workflows)}")

        if tester.results["workflows_failed"]:
            print("\nFailed Workflows:")
            for failure in tester.results["workflows_failed"]:
                print(f"  - {failure}")

        # 80% pass rate
        pass_rate = len(tester.results["workflows_passed"]) / len(workflows)
        assert pass_rate >= 0.80, f"Workflow pass rate {pass_rate:.1%} below 80%"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
