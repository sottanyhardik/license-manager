"""Route discovery and page load tests."""

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from config import BASE_URL


class TestRouteDiscovery:
    """Test all routes load without errors."""

    # Main navigation routes
    MAIN_ROUTES = [
        ("/dashboard", "Dashboard"),
        ("/licenses", "Licenses"),
        ("/allotments", "Allotments"),
        ("/bill-of-entries", "Bill of Entries"),
        ("/trades", "Trades"),
        ("/incentive-licenses", "Incentive Licenses"),
        ("/license-ledger", "License Ledger"),
        ("/reconciliation", "Reconciliation"),
        ("/admin/users", "Users"),
        ("/profile", "Profile"),
    ]

    # Report routes
    REPORT_ROUTES = [
        ("/reports/parle/sion-e1", "SION E1"),
        ("/reports/parle/sion-e5", "SION E5"),
        ("/reports/parle/sion-e126", "SION E126"),
        ("/reports/parle/sion-e132", "SION E132"),
        ("/reports/expiring-licenses", "Expiring Licenses"),
        ("/reports/active-licenses", "Active Licenses"),
        ("/reports/download-license", "Download License"),
        ("/reports/item-pivot", "Item Pivot"),
        ("/reports/item-report", "Item Report"),
        ("/reports/planned-report", "Planned Report"),
        ("/reports/license-purchase-profit", "License Purchase Profit"),
    ]

    @pytest.mark.smoke
    @pytest.mark.parametrize("route,name", MAIN_ROUTES)
    def test_main_routes_load(self, auth_driver, artifacts_manager, route, name):
        """Test main routes load without errors."""
        driver = auth_driver
        driver.get(f"{BASE_URL}{route}")

        # Wait for page load
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Verify no redirect to 404
        assert "/404" not in driver.current_url
        assert "401" not in driver.current_url

        # Verify no fatal JavaScript errors
        console_logs = driver.get_log("browser")
        severe_errors = [log for log in console_logs if log["level"] == "SEVERE"]

        artifacts_manager.save_screenshot(driver, f"test_route_{route.strip('/')}")

        assert len(severe_errors) == 0, f"SEVERE console errors on {route}: {severe_errors}"

    @pytest.mark.parametrize("route,name", REPORT_ROUTES)
    def test_report_routes_load(self, auth_driver, artifacts_manager, route, name):
        """Test report routes load."""
        driver = auth_driver
        driver.get(f"{BASE_URL}{route}")

        # Wait for page load
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Verify page loaded
        assert "/404" not in driver.current_url
        assert "401" not in driver.current_url

        artifacts_manager.save_screenshot(driver, f"test_report_route_{route.split('/')[-1]}")

    @pytest.mark.smoke
    def test_root_redirects_to_dashboard(self, auth_driver, artifacts_manager):
        """Test root redirects to dashboard."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/")

        WebDriverWait(driver, 10).until(
            lambda d: "dashboard" in d.current_url
        )

        artifacts_manager.save_screenshot(driver, "test_root_redirect")

    @pytest.mark.smoke
    def test_404_page(self, auth_driver, artifacts_manager):
        """Test 404 page."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/nonexistent-page-12345")

        # Should show 404 page or redirect
        WebDriverWait(driver, 10).until(
            lambda d: "404" in d.current_url or "not found" in d.page_source.lower()
        )

        artifacts_manager.save_screenshot(driver, "test_404_page")

    def test_navigation_from_sidebar(self, auth_driver, artifacts_manager):
        """Test navigation from sidebar."""
        driver = auth_driver
        driver.get(f"{BASE_URL}/dashboard")

        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Find sidebar links
        sidebar_links = driver.find_elements(By.XPATH, "//nav//a | //aside//a")

        artifacts_manager.save_metadata("test_navigation_from_sidebar", {
            "sidebar_links_count": len(sidebar_links),
            "links": [link.get_attribute("href") for link in sidebar_links if link.get_attribute("href")]
        })

        assert len(sidebar_links) > 0

    @pytest.mark.smoke
    def test_no_blank_pages(self, auth_driver, artifacts_manager):
        """Test that pages don't load blank."""
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

            # Check for content
            body_text = driver.find_element(By.TAG_NAME, "body").text
            assert len(body_text) > 0, f"Blank page at {route}"

            artifacts_manager.save_screenshot(driver, f"test_no_blank_{route.strip('/')}")
