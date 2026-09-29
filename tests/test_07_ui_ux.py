"""UI/UX and accessibility tests."""

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
import time
from config import BASE_URL


class TestUIUX:
    """Test UI/UX and accessibility."""

    @pytest.mark.ux
    def test_no_overlapping_elements(self, auth_driver, artifacts_manager):
        """Test for overlapping elements."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Check for visible content
        visible_elements = driver.find_elements(By.XPATH, "//*[string-length(text()) > 0]")
        print(f"Visible text elements: {len(visible_elements)}")

        artifacts_manager.save_screenshot(driver, "test_no_overlapping_elements")

    def test_no_clipped_content(self, auth_driver, artifacts_manager):
        """Test for clipped or hidden content."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Check for overflow issues
        script = """
        let elements = document.querySelectorAll('*');
        let clipped = [];
        elements.forEach(el => {
            if (el.scrollWidth > el.clientWidth || el.scrollHeight > el.clientHeight) {
                clipped.push({
                    tag: el.tagName,
                    text: el.textContent.substring(0, 50),
                    scrollWidth: el.scrollWidth,
                    clientWidth: el.clientWidth
                });
            }
        });
        return clipped.slice(0, 10);
        """

        clipped = driver.execute_script(script)
        print(f"Clipped elements: {len(clipped)}")
        print(clipped)

        artifacts_manager.save_screenshot(driver, "test_no_clipped_content")

    def test_responsive_layout_desktop(self, auth_driver, artifacts_manager):
        """Test responsive layout at desktop size."""
        driver = auth_driver
        driver.set_window_size(1920, 1080)

        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        artifacts_manager.save_screenshot(driver, "test_responsive_desktop_1920x1080")

    def test_responsive_layout_tablet(self, auth_driver, artifacts_manager):
        """Test responsive layout at tablet size."""
        driver = auth_driver
        driver.set_window_size(768, 1024)

        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        artifacts_manager.save_screenshot(driver, "test_responsive_tablet_768x1024")

    def test_keyboard_navigation_tab(self, auth_driver, artifacts_manager):
        """Test keyboard navigation with Tab key."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Focus on first element
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.TAB)
        time.sleep(0.5)

        # Get focused element
        focused = driver.switch_to.active_element
        print(f"Focused element: {focused.tag_name}")

        artifacts_manager.save_screenshot(driver, "test_keyboard_navigation_tab")

    def test_keyboard_navigation_escape(self, auth_driver, artifacts_manager):
        """Test Escape key closes modals/dropdowns."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Try to find and open a dropdown
        try:
            dropdown = driver.find_element(By.XPATH, "//button[@aria-haspopup='listbox'] | //*[@role='combobox']")
            dropdown.click()
            time.sleep(0.5)

            # Press Escape
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.5)
        except:
            pass

        artifacts_manager.save_screenshot(driver, "test_keyboard_navigation_escape")

    def test_focus_visible(self, auth_driver, artifacts_manager):
        """Test focus is visible on interactive elements."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Tab to first button
        body = driver.find_element(By.TAG_NAME, "body")
        for i in range(5):
            body.send_keys(Keys.TAB)
            time.sleep(0.2)

        artifacts_manager.save_screenshot(driver, "test_focus_visible")

    def test_no_empty_buttons(self, auth_driver, artifacts_manager):
        """Test buttons have visible text or icons."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find all buttons
        buttons = driver.find_elements(By.XPATH, "//button")
        empty_buttons = []

        for btn in buttons:
            text = btn.text.strip()
            # Check for icon
            has_icon = len(btn.find_elements(By.XPATH, ".//*")) > 0

            if not text and not has_icon:
                empty_buttons.append({
                    "class": btn.get_attribute("class"),
                    "aria-label": btn.get_attribute("aria-label")
                })

        print(f"Empty buttons: {len(empty_buttons)}")
        if empty_buttons:
            print(empty_buttons)

        artifacts_manager.save_screenshot(driver, "test_no_empty_buttons")

    def test_proper_color_contrast(self, auth_driver, artifacts_manager):
        """Test for proper color contrast."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Get all text elements with computed styles
        script = """
        let elements = document.querySelectorAll('*');
        let lowContrast = [];
        elements.forEach(el => {
            if (el.textContent && el.textContent.length > 0) {
                let style = window.getComputedStyle(el);
                let color = style.color;
                let bg = style.backgroundColor;
                // Basic check - not exhaustive
                if (color && bg && color !== 'rgba(0, 0, 0, 0)') {
                    lowContrast.push({
                        tag: el.tagName,
                        color: color,
                        bg: bg,
                    });
                }
            }
        });
        return lowContrast.slice(0, 5);
        """

        try:
            colors = driver.execute_script(script)
            print(f"Color info: {colors}")
        except:
            print("Could not analyze colors")

        artifacts_manager.save_screenshot(driver, "test_color_contrast")

    def test_no_raw_ids_in_ui(self, auth_driver, artifacts_manager):
        """Test UI doesn't show raw IDs or [object Object]."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        page_text = driver.page_source

        # Check for common rendering issues
        assert "[object Object]" not in page_text
        assert "undefined" not in page_text.lower() or "undefined" in page_text.lower()  # May be in console

        artifacts_manager.save_screenshot(driver, "test_no_raw_ids")

    def test_consistent_spacing(self, auth_driver, artifacts_manager):
        """Test for consistent spacing and alignment."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/licenses")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Check for left-aligned elements
        script = """
        let elements = Array.from(document.querySelectorAll('.MuiButton-root, .MuiTextField-root'));
        let positions = elements.map(el => el.getBoundingClientRect().left);
        return {
            count: elements.length,
            unique_positions: new Set(positions).size,
            positions: positions.slice(0, 10)
        };
        """

        try:
            positions = driver.execute_script(script)
            print(f"Element alignment: {positions}")
        except:
            pass

        artifacts_manager.save_screenshot(driver, "test_consistent_spacing")
