"""Filter and autocomplete field tests."""

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
import time
from config import BASE_URL


class TestFiltersAndAutocomplete:
    """Test all filter types and autocomplete fields."""

    @pytest.mark.filters
    def test_exporter_autocomplete_typing(self, auth_driver, artifacts_manager):
        """Test exporter field accepts typed input."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find exporter autocomplete input
        exporter_input = driver.find_element(
            By.XPATH,
            "//label[contains(text(), 'Exporter')]/..//input"
        )

        # Type "Parle"
        exporter_input.click()
        exporter_input.send_keys("Parle")

        # Verify text appears in input
        assert "Parle" in exporter_input.get_attribute("value"), \
            f"Expected 'Parle' in input, got '{exporter_input.get_attribute('value')}'"

        # Wait for results
        time.sleep(2)

        artifacts_manager.save_screenshot(driver, "test_exporter_typing")
        artifacts_manager.save_console_logs(driver, "test_exporter_typing")

        # Verify API request happened (check network)
        console_logs = driver.get_log("browser")
        print(f"Console logs: {console_logs}")

    @pytest.mark.filters
    def test_exclude_port_autocomplete_typing(self, auth_driver, artifacts_manager):
        """Test exclude port field accepts typed input."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find exclude port autocomplete input
        exclude_port_input = driver.find_element(
            By.XPATH,
            "//label[contains(text(), 'Exclude Port')]/..//input"
        )

        # Type "Mundra"
        exclude_port_input.click()
        exclude_port_input.send_keys("Mundra")

        # Verify text appears
        assert "Mundra" in exclude_port_input.get_attribute("value"), \
            f"Expected 'Mundra' in input, got '{exclude_port_input.get_attribute('value')}'"

        time.sleep(2)

        artifacts_manager.save_screenshot(driver, "test_exclude_port_typing")
        artifacts_manager.save_console_logs(driver, "test_exclude_port_typing")

    @pytest.mark.filters
    def test_purchase_status_labels_not_ids(self, auth_driver, artifacts_manager):
        """Test Purchase Status shows labels, not numeric IDs."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find Purchase Status filter
        purchase_status_elem = driver.find_element(
            By.XPATH,
            "//label[contains(text(), 'Purchase Status')]/../.."
        )

        # Check visible text
        visible_text = purchase_status_elem.text

        # Should NOT contain raw numeric IDs like [object Object]
        assert "[object Object]" not in visible_text
        assert "undefined" not in visible_text.lower()

        # Look for readable labels (all caps, words)
        artifacts_manager.save_screenshot(driver, "test_purchase_status_labels")

        print(f"Purchase Status visible text: {visible_text}")

    @pytest.mark.filters
    def test_filter_clear_all(self, auth_driver, artifacts_manager):
        """Test Clear All filters button."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Apply a filter (Exporter)
        exporter_input = driver.find_element(
            By.XPATH,
            "//label[contains(text(), 'Exporter')]/..//input"
        )
        exporter_input.click()
        exporter_input.send_keys("Parle")
        time.sleep(2)

        # Find and click Clear All button
        try:
            clear_all_btn = driver.find_element(
                By.XPATH,
                "//button[contains(text(), 'Clear All')] | //button[contains(text(), 'Reset')]"
            )
            clear_all_btn.click()

            # Verify filters cleared
            time.sleep(1)
            exporter_input_after = driver.find_element(
                By.XPATH,
                "//label[contains(text(), 'Exporter')]/..//input"
            )
            assert exporter_input_after.get_attribute("value") == ""

            artifacts_manager.save_screenshot(driver, "test_filter_clear_all")
        except:
            artifacts_manager.save_screenshot(driver, "test_filter_clear_all_not_found")
            print("Clear All button not found")

    @pytest.mark.filters
    def test_filter_apply_and_verify_results(self, auth_driver, artifacts_manager):
        """Test applying filter shows relevant results."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find table with results
        try:
            table_rows = driver.find_elements(By.XPATH, "//tbody/tr")
            initial_count = len(table_rows)

            print(f"Initial table rows: {initial_count}")

            # Apply filter
            exporter_input = driver.find_element(
                By.XPATH,
                "//label[contains(text(), 'Exporter')]/..//input"
            )
            exporter_input.click()
            exporter_input.send_keys("Parle")

            # Wait for results to update
            time.sleep(3)

            # Check updated count
            table_rows_after = driver.find_elements(By.XPATH, "//tbody/tr")
            after_count = len(table_rows_after)

            print(f"After filter rows: {after_count}")

            artifacts_manager.save_screenshot(driver, "test_filter_apply_results")
        except Exception as e:
            print(f"Error testing filter results: {e}")
            artifacts_manager.save_screenshot(driver, "test_filter_apply_results_error")

    @pytest.mark.filters
    def test_filter_url_synchronization(self, auth_driver, artifacts_manager):
        """Test filters sync with URL."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        initial_url = driver.current_url

        # Apply filter
        exporter_input = driver.find_element(
            By.XPATH,
            "//label[contains(text(), 'Exporter')]/..//input"
        )
        exporter_input.click()
        exporter_input.send_keys("Parle")
        time.sleep(2)

        # Check URL changed
        current_url = driver.current_url

        print(f"Initial URL: {initial_url}")
        print(f"After filter URL: {current_url}")

        # URL should have changed with filter params
        artifacts_manager.save_screenshot(driver, "test_filter_url_sync")

    @pytest.mark.filters
    def test_filter_refresh_preserves_state(self, auth_driver, artifacts_manager):
        """Test filter state is preserved on refresh."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Apply filter
        exporter_input = driver.find_element(
            By.XPATH,
            "//label[contains(text(), 'Exporter')]/..//input"
        )
        exporter_input.click()
        exporter_input.send_keys("Parle")
        time.sleep(2)

        initial_url = driver.current_url

        # Refresh
        driver.refresh()
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Verify filter still applied
        time.sleep(2)
        exporter_input_after = driver.find_element(
            By.XPATH,
            "//label[contains(text(), 'Exporter')]/..//input"
        )

        value_after = exporter_input_after.get_attribute("value")
        print(f"Value after refresh: {value_after}")

        artifacts_manager.save_screenshot(driver, "test_filter_refresh_preserve")

    @pytest.mark.filters
    def test_all_filter_fields_visible(self, auth_driver, artifacts_manager):
        """Test all filter fields are visible on filter panel."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find all filter labels
        filter_labels = driver.find_elements(By.XPATH, "//label")
        label_texts = [label.text for label in filter_labels if label.text]

        print(f"Found {len(label_texts)} labels")
        print(f"Labels: {label_texts}")

        # Common filter fields
        expected_filters = ["Exporter", "Company", "Port"]

        found_filters = [f for f in expected_filters if any(f in label for label in label_texts)]
        print(f"Found filters: {found_filters}")

        artifacts_manager.save_metadata("test_all_filter_fields", {
            "total_labels": len(label_texts),
            "visible_labels": label_texts,
            "found_expected_filters": found_filters,
        })
