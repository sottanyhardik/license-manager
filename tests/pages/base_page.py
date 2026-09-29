"""Base page class for all page objects."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time


class BasePage:
    """Base class for all page objects."""

    def __init__(self, driver: webdriver.Chrome, base_url: str = None):
        self.driver = driver
        self.base_url = base_url or "http://localhost:5173"
        self.wait = WebDriverWait(driver, 15)
        self.short_wait = WebDriverWait(driver, 5)
        self.actions = ActionChains(driver)

    def get(self, path: str = None):
        """Navigate to page."""
        if path:
            self.driver.get(f"{self.base_url}{path}")
        return self

    def wait_for_element(self, by: By, value: str, timeout: int = 15):
        """Wait for element presence."""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    def wait_for_visibility(self, by: By, value: str, timeout: int = 15):
        """Wait for element visibility."""
        return WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located((by, value))
        )

    def wait_for_clickable(self, by: By, value: str, timeout: int = 15):
        """Wait for element clickable."""
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )

    def find(self, by: By, value: str):
        """Find element."""
        return self.driver.find_element(by, value)

    def find_all(self, by: By, value: str):
        """Find all elements."""
        return self.driver.find_elements(by, value)

    def click(self, by: By, value: str):
        """Click element."""
        element = self.wait_for_clickable(by, value)
        element.click()
        return self

    def type_text(self, by: By, value: str, text: str):
        """Type text in element."""
        element = self.wait_for_element(by, value)
        element.clear()
        element.send_keys(text)
        return self

    def get_text(self, by: By, value: str):
        """Get element text."""
        element = self.wait_for_element(by, value)
        return element.text

    def get_attribute(self, by: By, value: str, attribute: str):
        """Get element attribute."""
        element = self.wait_for_element(by, value)
        return element.get_attribute(attribute)

    def is_element_visible(self, by: By, value: str, timeout: int = 5):
        """Check if element is visible."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((by, value))
            )
            return True
        except:
            return False

    def is_element_present(self, by: By, value: str, timeout: int = 5):
        """Check if element is present."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return True
        except:
            return False

    def wait_for_url_contains(self, substring: str, timeout: int = 15):
        """Wait for URL to contain substring."""
        WebDriverWait(self.driver, timeout).until(
            EC.url_contains(substring)
        )
        return self

    def wait_for_url(self, url: str, timeout: int = 15):
        """Wait for exact URL."""
        WebDriverWait(self.driver, timeout).until(
            EC.url_to_be(url)
        )
        return self

    def get_current_url(self):
        """Get current URL."""
        return self.driver.current_url

    def refresh(self):
        """Refresh page."""
        self.driver.refresh()
        return self

    def wait_for_page_load(self):
        """Wait for page to fully load."""
        WebDriverWait(self.driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return self

    def get_console_errors(self):
        """Get browser console errors."""
        logs = self.driver.get_log("browser")
        errors = [log for log in logs if log["level"] == "SEVERE"]
        return errors

    def has_console_errors(self):
        """Check for console errors."""
        return len(self.get_console_errors()) > 0

    def take_screenshot(self, filename: str):
        """Take screenshot."""
        self.driver.save_screenshot(filename)
        return self

    def scroll_to_element(self, by: By, value: str):
        """Scroll to element."""
        element = self.find(by, value)
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(0.5)
        return self

    def execute_script(self, script: str, *args):
        """Execute JavaScript."""
        return self.driver.execute_script(script, *args)

    def switch_to_iframe(self, by: By, value: str):
        """Switch to iframe."""
        iframe = self.wait_for_element(by, value)
        self.driver.switch_to.frame(iframe)
        return self

    def switch_to_default_content(self):
        """Switch back to default content."""
        self.driver.switch_to.default_content()
        return self
