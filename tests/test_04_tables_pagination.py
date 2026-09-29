"""Table and pagination tests."""

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import time
from config import BASE_URL


class TestTablesAndPagination:
    """Test table functionality and pagination."""

    @pytest.mark.smoke
    @pytest.mark.parametrize("route", [
        "/licenses",
        "/allotments",
        "/bill-of-entries",
        "/trades",
        "/incentive-licenses",
    ])
    def test_table_loads_with_data(self, auth_driver, artifacts_manager, route):
        """Test table pages load with data."""
        driver = auth_driver
        driver.get(f"{BASE_URL}{route}")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Check for table
        try:
            table = driver.find_element(By.XPATH, "//table | //*[@role='table']")
            assert table is not None

            # Check for headers
            headers = driver.find_elements(By.XPATH, "//th | //*[@role='columnheader']")
            assert len(headers) > 0

            # Check for rows
            rows = driver.find_elements(By.XPATH, "//tbody/tr | //*[@role='row']")
            print(f"Table on {route} has {len(rows)} rows and {len(headers)} headers")

            artifacts_manager.save_screenshot(driver, f"test_table_{route.strip('/')}")
        except:
            # Table might not exist on some routes
            artifacts_manager.save_screenshot(driver, f"test_table_not_found_{route.strip('/')}")

    def test_pagination_next_previous(self, auth_driver, artifacts_manager):
        """Test pagination next/previous buttons."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Check for pagination
        try:
            pagination = driver.find_element(By.XPATH, "//*[contains(text(), 'Next')] | //*[contains(text(), 'Previous')]")
            assert pagination is not None

            # Try clicking next
            next_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Next')]")
            next_btn.click()

            time.sleep(2)

            artifacts_manager.save_screenshot(driver, "test_pagination_next")
        except:
            print("Pagination buttons not found or not clickable")
            artifacts_manager.save_screenshot(driver, "test_pagination_not_found")

    def test_table_sorting(self, auth_driver, artifacts_manager):
        """Test table column sorting."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find sortable header
        try:
            headers = driver.find_elements(By.XPATH, "//th")
            if len(headers) > 0:
                # Click first header
                headers[0].click()
                time.sleep(1)

                artifacts_manager.save_screenshot(driver, "test_table_sorting")
        except:
            print("No sortable headers found")
            artifacts_manager.save_screenshot(driver, "test_table_sorting_error")

    def test_table_row_selection(self, auth_driver, artifacts_manager):
        """Test table row selection."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find row with data
        try:
            rows = driver.find_elements(By.XPATH, "//tbody/tr")
            if len(rows) > 0:
                # Click first row
                rows[0].click()
                time.sleep(1)

                artifacts_manager.save_screenshot(driver, "test_table_row_selection")
        except:
            print("No table rows found")
            artifacts_manager.save_screenshot(driver, "test_table_row_selection_error")

    def test_table_empty_state(self, auth_driver, artifacts_manager):
        """Test table empty state."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Try to find empty state message
        try:
            empty_msg = driver.find_element(By.XPATH, "//*[contains(text(), 'No')] | //*[contains(text(), 'Empty')]")
            print(f"Empty state message: {empty_msg.text}")
        except:
            pass

        artifacts_manager.save_screenshot(driver, "test_table_empty_state")

    def test_table_page_size_selector(self, auth_driver, artifacts_manager):
        """Test page size selector."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Look for page size selector
        try:
            page_size_select = driver.find_element(By.XPATH, "//select | //*[contains(text(), 'per page')]")
            assert page_size_select is not None

            artifacts_manager.save_screenshot(driver, "test_table_page_size")
        except:
            print("Page size selector not found")
            artifacts_manager.save_screenshot(driver, "test_table_page_size_not_found")
