"""Pytest configuration and fixtures."""

import pytest
import json
import time
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from config import (
    BASE_URL,
    TEST_USERNAME,
    TEST_PASSWORD,
    CHROME_OPTIONS,
    TEST_ROOT,
    ARTIFACTS_DIR,
    test_registry,
    ENVIRONMENT
)


@pytest.fixture(scope="session")
def chrome_driver_manager():
    """Manage Chrome driver for the session."""
    return ChromeDriverManager()


@pytest.fixture
def driver(chrome_driver_manager):
    """Create and yield a Chrome WebDriver."""
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-notifications")

    # Uncomment for headless mode
    # options.add_argument("--headless=new")

    service = Service(chrome_driver_manager.install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(10)

    yield driver

    driver.quit()


@pytest.fixture
def auth_driver(driver):
    """Driver with pre-authenticated session."""
    driver.get(f"{BASE_URL}/login")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "login-username"))
    )

    # Login
    driver.find_element(By.ID, "login-username").send_keys(TEST_USERNAME)
    time.sleep(0.5)
    driver.find_element(By.ID, "login-password").send_keys(TEST_PASSWORD)
    time.sleep(0.5)

    # Find and click submit button - try multiple selectors
    try:
        btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Sign in')]")
    except:
        try:
            btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        except:
            btn = driver.find_element(By.XPATH, "//button")

    btn.click()

    # Wait for dashboard or any page that's not login (30 second timeout for slow pages)
    WebDriverWait(driver, 30).until(
        lambda d: "login" not in d.current_url.lower()
    )

    # Wait for body content (page fully rendered)
    WebDriverWait(driver, 30).until(
        lambda d: len(d.find_element(By.TAG_NAME, "body").text) > 0
    )

    # Ensure page is fully loaded
    time.sleep(2)

    yield driver
    driver.quit()


@pytest.fixture
def test_data_manager():
    """Manage test data lifecycle."""
    return test_registry


@pytest.fixture
def artifacts_manager():
    """Manage artifact storage."""
    class ArtifactsManager:
        def __init__(self):
            self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.test_artifacts_dir = ARTIFACTS_DIR / f"test_{self.timestamp}"
            self.test_artifacts_dir.mkdir(parents=True, exist_ok=True)

        def save_screenshot(self, driver, name: str):
            """Save screenshot."""
            path = self.test_artifacts_dir / f"{name}.png"
            driver.save_screenshot(str(path))
            return path

        def save_console_logs(self, driver, name: str):
            """Save console logs."""
            logs = driver.get_log("browser")
            path = self.test_artifacts_dir / f"{name}_console.json"
            with open(path, "w") as f:
                json.dump(logs, f, indent=2)
            return path, logs

        def save_dom(self, driver, name: str):
            """Save DOM."""
            dom = driver.page_source
            path = self.test_artifacts_dir / f"{name}_dom.html"
            with open(path, "w") as f:
                f.write(dom)
            return path

        def save_metadata(self, name: str, data: dict):
            """Save test metadata."""
            path = self.test_artifacts_dir / f"{name}_metadata.json"
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            return path

        def capture_failure(self, driver, test_name: str, error: str):
            """Capture complete failure context."""
            failure_dir = self.test_artifacts_dir / f"FAIL_{test_name}"
            failure_dir.mkdir(parents=True, exist_ok=True)

            # Screenshot
            driver.save_screenshot(str(failure_dir / "screenshot.png"))

            # DOM
            with open(failure_dir / "dom.html", "w") as f:
                f.write(driver.page_source)

            # Console logs
            logs = driver.get_log("browser")
            with open(failure_dir / "console.json", "w") as f:
                json.dump(logs, f, indent=2)

            # Network logs
            try:
                network_logs = driver.execute_script(
                    "return window.performanceEntries || []"
                )
                with open(failure_dir / "network.json", "w") as f:
                    json.dump(network_logs, f, indent=2, default=str)
            except:
                pass

            # Metadata
            metadata = {
                "test": test_name,
                "error": error,
                "url": driver.current_url,
                "timestamp": datetime.now().isoformat(),
            }
            with open(failure_dir / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            return failure_dir

    return ArtifactsManager()


def pytest_configure(config):
    """Configure pytest."""
    # Register markers
    config.addinivalue_line(
        "markers", "smoke: smoke tests"
    )
    config.addinivalue_line(
        "markers", "regression: regression tests"
    )
    config.addinivalue_line(
        "markers", "filters: filter tests"
    )
    config.addinivalue_line(
        "markers", "forms: form tests"
    )
    config.addinivalue_line(
        "markers", "crud: CRUD operation tests"
    )
    config.addinivalue_line(
        "markers", "ux: UX and accessibility tests"
    )
    config.addinivalue_line(
        "markers", "reports: report tests"
    )


def pytest_sessionfinish(session, exitstatus):
    """Generate test summary."""
    # Create summary report
    summary_path = ARTIFACTS_DIR / "test_summary.json"
    summary = {
        "timestamp": datetime.now().isoformat(),
        "environment": ENVIRONMENT,
        "test_url": BASE_URL,
        "test_cleanup": test_registry.cleanup_summary(),
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n📊 Test Summary: {summary_path}")
