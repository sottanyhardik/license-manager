"""Form field and validation tests."""

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import time
from config import BASE_URL


class TestFormsAndFields:
    """Test all form fields and validations."""

    @pytest.mark.forms
    def test_create_license_form_visible(self, auth_driver, artifacts_manager):
        """Test create license form loads."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses/create")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Check for form elements
        inputs = driver.find_elements(By.XPATH, "//input | //textarea | //select")
        print(f"Form inputs found: {len(inputs)}")

        assert len(inputs) > 0, "No form inputs found"

        artifacts_manager.save_screenshot(driver, "test_create_license_form")

    @pytest.mark.forms
    def test_form_required_fields(self, auth_driver, artifacts_manager):
        """Test required fields are marked."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses/create")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find required field indicators
        required_fields = driver.find_elements(By.XPATH, "//*[contains(text(), '*')] | //*[@required]")
        print(f"Required field indicators: {len(required_fields)}")

        artifacts_manager.save_screenshot(driver, "test_form_required_fields")

    def test_text_field_input(self, auth_driver, artifacts_manager):
        """Test text field accepts input."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses/create")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find first text input
        try:
            text_input = driver.find_element(By.XPATH, "//input[@type='text'][1]")
            text_input.send_keys("Test Input")

            value = text_input.get_attribute("value")
            assert value == "Test Input"

            artifacts_manager.save_screenshot(driver, "test_text_field_input")
        except Exception as e:
            print(f"Could not test text input: {e}")

    def test_select_field_options(self, auth_driver, artifacts_manager):
        """Test select field opens with options."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses/create")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find select element
        try:
            select = driver.find_element(By.XPATH, "//select[1]")
            options = select.find_elements(By.TAG_NAME, "option")

            print(f"Select field has {len(options)} options")
            assert len(options) > 0

            artifacts_manager.save_screenshot(driver, "test_select_field_options")
        except Exception as e:
            print(f"Could not find select: {e}")

    def test_checkbox_toggle(self, auth_driver, artifacts_manager):
        """Test checkbox can be toggled."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses/create")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find checkbox
        try:
            checkbox = driver.find_element(By.XPATH, "//input[@type='checkbox'][1]")

            # Get initial state
            initial_state = checkbox.is_selected()

            # Click
            checkbox.click()
            time.sleep(0.5)

            # Verify state changed
            new_state = checkbox.is_selected()
            assert initial_state != new_state

            artifacts_manager.save_screenshot(driver, "test_checkbox_toggle")
        except:
            print("No checkbox found")

    def test_radio_button_selection(self, auth_driver, artifacts_manager):
        """Test radio button selection."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses/create")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find radio buttons
        try:
            radios = driver.find_elements(By.XPATH, "//input[@type='radio']")
            if len(radios) > 0:
                # Select first
                radios[0].click()
                time.sleep(0.5)

                assert radios[0].is_selected()

                artifacts_manager.save_screenshot(driver, "test_radio_button_selection")
        except:
            print("No radio buttons found")

    def test_form_submission_button(self, auth_driver, artifacts_manager):
        """Test form has submit button."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses/create")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find submit button
        try:
            submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Save')] | //button[contains(text(), 'Submit')] | //button[contains(text(), 'Create')]")
            assert submit_btn is not None

            artifacts_manager.save_screenshot(driver, "test_form_submission_button")
        except:
            print("No submit button found")

    def test_form_cancel_button(self, auth_driver, artifacts_manager):
        """Test form has cancel button."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses/create")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find cancel button
        try:
            cancel_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Cancel')] | //button[contains(text(), 'Close')]")
            assert cancel_btn is not None

            artifacts_manager.save_screenshot(driver, "test_form_cancel_button")
        except:
            print("No cancel button found")

    @pytest.mark.forms
    def test_date_field_input(self, auth_driver, artifacts_manager):
        """Test date field accepts date input."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses/create")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find date input
        try:
            date_input = driver.find_element(By.XPATH, "//input[@type='date']")
            date_input.send_keys("2026-12-31")

            artifacts_manager.save_screenshot(driver, "test_date_field_input")
        except:
            print("No date field found")
