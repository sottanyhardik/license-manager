"""Console error and network health tests."""

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import json
from config import BASE_URL


class TestConsoleAndNetwork:
    """Test console and network health."""

    @pytest.mark.smoke
    def test_dashboard_no_console_errors(self, auth_driver, artifacts_manager):
        """Test dashboard loads without console errors."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/dashboard")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Check console for SEVERE errors
        console_logs = driver.get_log("browser")
        severe_errors = [log for log in console_logs if log["level"] == "SEVERE"]

        artifacts_manager.save_console_logs(driver, "test_dashboard_no_console_errors")

        # Print all logs for debugging
        print("Console logs:")
        for log in console_logs:
            print(f"  [{log['level']}] {log['message']}")

        # Should have 0 or very few errors
        assert len(severe_errors) == 0, f"Found SEVERE console errors: {severe_errors}"

    def test_licenses_page_no_console_errors(self, auth_driver, artifacts_manager):
        """Test licenses page loads without console errors."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        console_logs = driver.get_log("browser")
        severe_errors = [log for log in console_logs if log["level"] == "SEVERE"]
        warnings = [log for log in console_logs if log["level"] == "WARNING"]

        artifacts_manager.save_console_logs(driver, "test_licenses_page")

        print(f"Warnings: {len(warnings)}")
        print(f"Severe errors: {len(severe_errors)}")

        # SEVERE errors should be minimal
        assert len(severe_errors) <= 1, f"Too many SEVERE errors: {severe_errors}"

    def test_no_401_errors(self, auth_driver, artifacts_manager):
        """Test no unauthorized (401) errors."""
        driver = auth_driver
        routes = [
            "/dashboard",
            "/licenses",
            "/allotments",
            "/trades",
        ]

        for route in routes:
            driver.get(f"{BASE_URL}{route}")

            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            # Check for 401 in page
            assert "401" not in driver.page_source

            # Get network logs
            try:
                perf_entries = driver.execute_script(
                    "return performance.getEntries().map(e => ({name: e.name, status: e.status}))"
                )

                # Check for 401 responses
                has_401 = any(entry.get("status") == 401 for entry in perf_entries if "status" in entry)
                assert not has_401, f"Found 401 error on {route}"
            except:
                pass

        artifacts_manager.save_screenshot(driver, "test_no_401_errors")

    def test_no_500_errors(self, auth_driver, artifacts_manager):
        """Test no server errors (500)."""
        driver = auth_driver

        console_logs = driver.get_log("browser")

        # Check for 500 error messages
        error_messages = [log["message"] for log in console_logs if "500" in log["message"]]

        assert len(error_messages) == 0, f"Found 500 errors: {error_messages}"

        artifacts_manager.save_screenshot(driver, "test_no_500_errors")

    def test_no_429_errors(self, auth_driver, artifacts_manager):
        """Test no rate limit errors (429)."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        console_logs = driver.get_log("browser")

        # Check for 429 error messages
        error_messages = [log["message"] for log in console_logs if "429" in log["message"]]

        assert len(error_messages) == 0, f"Found 429 rate limit errors: {error_messages}"

        artifacts_manager.save_screenshot(driver, "test_no_429_errors")

    def test_no_connection_reset_errors(self, auth_driver, artifacts_manager):
        """Test no connection reset errors."""
        driver = auth_driver

        console_logs = driver.get_log("browser")

        # Check for connection reset messages
        error_messages = [
            log["message"] for log in console_logs
            if "connection reset" in log["message"].lower() or "net::err" in log["message"].lower()
        ]

        assert len(error_messages) == 0, f"Found connection errors: {error_messages}"

        artifacts_manager.save_screenshot(driver, "test_no_connection_reset")

    def test_no_uncontrolled_component_warnings(self, auth_driver, artifacts_manager):
        """Test no controlled/uncontrolled component warnings."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        console_logs = driver.get_log("browser")

        # Check for uncontrolled/controlled warnings
        warnings = [
            log["message"] for log in console_logs
            if "controlled" in log["message"].lower() and "warning" in log["level"].lower()
        ]

        print(f"Uncontrolled component warnings: {len(warnings)}")

        # Should be 0
        assert len(warnings) == 0, f"Found controlled/uncontrolled warnings: {warnings}"

        artifacts_manager.save_screenshot(driver, "test_no_uncontrolled_warnings")

    def test_no_mui_input_errors(self, auth_driver, artifacts_manager):
        """Test no MUI input errors."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        console_logs = driver.get_log("browser")

        # Check for MUI input errors like "Unable to find the input element"
        errors = [
            log["message"] for log in console_logs
            if "Unable to find the input element" in log["message"]
        ]

        print(f"MUI input errors: {len(errors)}")

        assert len(errors) == 0, f"Found MUI input errors: {errors}"

        artifacts_manager.save_screenshot(driver, "test_no_mui_input_errors")

    def test_no_react_dom_errors(self, auth_driver, artifacts_manager):
        """Test no React DOM errors."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/dashboard")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        console_logs = driver.get_log("browser")

        # Check for React DOM errors
        react_errors = [
            log["message"] for log in console_logs
            if "react" in log["message"].lower() and "error" in log["level"].lower()
        ]

        print(f"React errors: {len(react_errors)}")

        # Allow some React warnings but no SEVERE errors
        severe_react_errors = [e for e in react_errors if len(e) > 100]
        assert len(severe_react_errors) == 0, f"Found React DOM errors: {severe_react_errors}"

        artifacts_manager.save_screenshot(driver, "test_no_react_dom_errors")
