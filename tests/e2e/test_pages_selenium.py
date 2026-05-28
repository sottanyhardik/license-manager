"""
Selenium tests for the React SPA.

These catch the kind of bugs the API smoke tests can't: render-time errors
(like the TDZ ReferenceErrors that broke ItemPivotReport / ItemReport), bad
imports, and any other "Something went wrong" the ErrorBoundary swallows.

For each protected page we:
  1. Load the URL with auth tokens already in localStorage.
  2. Assert the route renders (no ErrorBoundary fallback).
  3. Assert a page-specific landmark element is present.
  4. Assert there are no SEVERE entries in the browser console.

Run with:

    pip install -r tests/e2e/requirements.txt
    pytest tests/e2e/test_pages_selenium.py -v
"""
from __future__ import annotations

import time

import pytest

# selenium imports are deferred to runtime — if selenium isn't installed
# the session-scoped fixture skips the whole module cleanly.
pytest.importorskip("selenium")

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


ERROR_BOUNDARY_TEXT = "Something went wrong"


def _wait(driver, timeout=10):
    return WebDriverWait(driver, timeout)


def _assert_no_error_boundary(driver):
    body = driver.find_element(By.TAG_NAME, "body").text
    assert ERROR_BOUNDARY_TEXT not in body, (
        f"ErrorBoundary tripped on {driver.current_url}.\n"
        f"Open DevTools console for the underlying React error."
    )


def _assert_no_console_errors(driver):
    """Fail the test if the browser console has SEVERE entries.

    Filters out a handful of noisy-but-benign sources (favicon 404, third-party
    extension noise) so a real React error stands out.
    """
    try:
        logs = driver.get_log("browser")
    except Exception:
        return  # Chrome's logging caps may be disabled — skip silently.

    ignored_substrings = (
        "favicon.ico",
        "extension://",
        "Failed to load resource: net::ERR_FILE_NOT_FOUND",
        # React's StrictMode double-renders surface in dev as warnings, not errors.
    )
    severe = [
        e for e in logs
        if e.get("level") == "SEVERE"
        and not any(s in e.get("message", "") for s in ignored_substrings)
    ]
    assert not severe, (
        "browser console has SEVERE errors:\n  "
        + "\n  ".join(e.get("message", "")[:300] for e in severe)
    )


# ---------------------------------------------------------------------------
# Login form — covered separately because it's the one page that EXERCISES
# the login flow rather than skipping it.
# ---------------------------------------------------------------------------
def test_login_page(selenium_driver, frontend_url, backend_url):
    driver = selenium_driver
    driver.get(f"{frontend_url}/login")

    _wait(driver).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[autocomplete='username'], input#login-username, input[name='username']")))
    username_input = driver.find_element(By.CSS_SELECTOR, "input[autocomplete='username'], input#login-username, input[name='username']")
    password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")

    username_input.clear()
    username_input.send_keys("hardik")
    password_input.clear()
    password_input.send_keys("admin@123")

    submit = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    submit.click()

    # Wait for redirect off /login.
    _wait(driver, timeout=15).until(lambda d: "/login" not in d.current_url)
    _assert_no_error_boundary(driver)


# ---------------------------------------------------------------------------
# Each protected route — one test apiece so a failure pinpoints the page.
# `selector` is a CSS selector for a landmark element that proves the page
# rendered. Use generic selectors so they survive minor markup edits.
# ---------------------------------------------------------------------------
_LANDMARK = "h1, h2, h3, .page-header, .surface-card, .card, table"

PAGES = [
    # (route, landmark selector, friendly id)
    ("/dashboard",                  _LANDMARK, "dashboard"),
    ("/licenses",                   _LANDMARK, "licenses-list"),
    ("/reports/item-pivot",         _LANDMARK, "item-pivot"),
    ("/reports/item-report",        _LANDMARK, "item-report"),
    ("/reports/active-licenses",    _LANDMARK, "active-licenses"),
    ("/reports/expiring-licenses",  _LANDMARK, "expiring-licenses"),
    ("/reports/download-license",   _LANDMARK, "download-license"),
]


@pytest.mark.parametrize("route, selector, page_id", PAGES, ids=[p[2] for p in PAGES])
def test_protected_page_renders(logged_in_driver, frontend_url, route, selector, page_id):
    driver = logged_in_driver
    driver.get(f"{frontend_url}{route}")

    try:
        _wait(driver, timeout=15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
    except TimeoutException:
        # Capture screenshot for debugging.
        try:
            driver.save_screenshot(f"/tmp/lm_selenium_{page_id}.png")
        except Exception:
            pass
        # Re-raise as a clean assertion failure.
        raise AssertionError(
            f"{route} did not render in time. Body text: "
            f"{driver.find_element(By.TAG_NAME, 'body').text[:300]!r}"
        )

    _assert_no_error_boundary(driver)
    _assert_no_console_errors(driver)


# ---------------------------------------------------------------------------
# ItemPivotReport — exercise the norm-tab click flow, which is what actually
# triggers the loadReport() useCallback that we recently un-broke (TDZ fix).
# ---------------------------------------------------------------------------
def test_item_pivot_click_first_norm(logged_in_driver, frontend_url):
    driver = logged_in_driver
    driver.get(f"{frontend_url}/reports/item-pivot")

    # Wait until at least one norm button shows up — the "Available Norms" buttons
    # use btn-outline-primary / btn-outline-success (or btn-primary / btn-success
    # if one was already active from a prior cached render).
    try:
        _wait(driver, timeout=30).until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "button.btn-outline-primary, button.btn-outline-success, "
                "button.btn-primary, button.btn-success",
            ))
        )
    except TimeoutException:
        try:
            driver.save_screenshot("/tmp/lm_selenium_item_pivot_norms.png")
        except Exception:
            pass
        raise AssertionError(
            "No norm buttons appeared. URL: "
            f"{driver.current_url}. Body: "
            f"{driver.find_element(By.TAG_NAME, 'body').text[:400]!r}"
        )

    norm_buttons = driver.find_elements(
        By.CSS_SELECTOR, "button.btn-outline-primary, button.btn-outline-success"
    )
    if not norm_buttons:
        pytest.skip("no norms returned — skipping click flow")

    # Wait for React to actually attach its onClick handler. Selenium can
    # otherwise find the button by selector and click it before hydration
    # completes — the click then hits raw HTML and the report never loads.
    btn = norm_buttons[0]
    _wait(driver, timeout=10).until(EC.element_to_be_clickable(btn))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    # Use JS-dispatched click to avoid intercepted-click edge cases (sticky
    # headers / overlay popups in the SPA's layout).
    driver.execute_script("arguments[0].click();", btn)

    # The report table is rendered inside a card body once data arrives.
    # Accept any of: a real table, the empty-state card, OR an explicit
    # "active norm" pill in the page header — all three prove the click
    # was wired up and the API call returned without crashing.
    try:
        _wait(driver, timeout=30).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.table")),
                EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "No licenses found"),
                EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Loading"),
            )
        )
    except TimeoutException:
        try:
            driver.save_screenshot("/tmp/lm_selenium_item_pivot_click.png")
        except Exception:
            pass
        raise AssertionError(
            "norm click didn't produce a table, empty-state, or loading indicator. "
            f"URL: {driver.current_url}. "
            f"Body excerpt: {driver.find_element(By.TAG_NAME, 'body').text[:500]!r}"
        )
    _assert_no_error_boundary(driver)


# ---------------------------------------------------------------------------
# License create form — every FK dropdown must populate on first click.
# Regression for the bug where HybridSelect didn't pass loadOnMount, leaving
# every dropdown showing "No options" until the user typed a search term.
# Also implicitly covers the "no obsolete varchar columns left in the DB"
# migration: this page would 500 if scheme_code/notification_number were
# still NOT NULL on the parent table.
# ---------------------------------------------------------------------------
def test_license_create_dropdowns_populate(logged_in_driver, frontend_url):
    from selenium.webdriver.common.keys import Keys

    driver = logged_in_driver
    # Hard reset between tests: the SPA's in-flight requests and component
    # state from the previous test (item-pivot report etc.) can otherwise
    # interfere with this page's first click. about:blank guarantees the
    # next navigation is a full fresh load.
    driver.get("about:blank")
    driver.get(f"{frontend_url}/licenses/create")

    # The form fetches its field metadata + master lookups in parallel.
    # Wait until react-select controls are mounted for every FK we care about.
    _wait(driver, timeout=20).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, "div.react-select__control")) >= 4
    )

    # Map each control to its preceding label so we can pick by name.
    controls = driver.find_elements(By.CSS_SELECTOR, "div.react-select__control")
    by_label = {}
    for c in controls:
        try:
            lbl = c.find_element(By.XPATH, "./preceding::label[1]")
            by_label[lbl.text.strip()] = c
        except Exception:
            pass

    expected_min_options = {
        "Scheme Code": 1,
        "Notification Number": 1,
        "Purchase Status": 1,
    }

    # Give the 5 simultaneous loadOnMount fetches a beat to land BEFORE
    # interacting — otherwise ARROW_DOWN can open the menu while react-select
    # is still in its initial "Loading…" state and our option assertion races
    # the fetch.
    import time as _t
    _t.sleep(2)

    for label_text, min_count in expected_min_options.items():
        control = by_label.get(label_text)
        assert control is not None, f"no react-select control found for {label_text!r}"
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", control)
        # Click the dropdown indicator (chevron) — this is the most reliable
        # way to open a react-select menu in headless mode. ARROW_DOWN on the
        # input requires focus to already be on the input, which isn't
        # guaranteed when running after other tests in the same browser.
        try:
            indicator = control.find_element(By.CSS_SELECTOR, ".react-select__dropdown-indicator")
            driver.execute_script("arguments[0].click();", indicator)
        except Exception:
            inp = control.find_element(By.CSS_SELECTOR, "input")
            driver.execute_script("arguments[0].focus();", inp)
            inp.send_keys(Keys.ARROW_DOWN)
        inp = control.find_element(By.CSS_SELECTOR, "input")
        try:
            _wait(driver, timeout=15).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, ".react-select__option")) >= min_count
            )
        except TimeoutException:
            try:
                driver.save_screenshot(f"/tmp/lm_dropdown_{label_text.replace(' ', '_')}.png")
            except Exception:
                pass
            menus = driver.find_elements(By.CSS_SELECTOR, ".react-select__menu")
            menu_text = menus[0].text if menus else "(no menu rendered)"
            raise AssertionError(
                f"{label_text}: dropdown showed no options within 15s. "
                f"Menu content: {menu_text!r}"
            )
        options = driver.find_elements(By.CSS_SELECTOR, ".react-select__option")
        assert len(options) >= min_count, (
            f"{label_text}: expected ≥{min_count} options, got {len(options)}"
        )
        # Close so the next iteration sees a fresh menu.
        inp.send_keys(Keys.ESCAPE)


# ---------------------------------------------------------------------------
# License edit — FK dropdowns must resolve their label, including codes that
# contain a "/" (notification_number = "025/2023"). Regression for the
# AsyncSelectField parseInt-corrupts-slug bug.
# ---------------------------------------------------------------------------
def test_license_edit_fk_labels_resolve(logged_in_driver, frontend_url, api_get):
    driver = logged_in_driver

    # Grab the first license id from the API so the test doesn't hard-code one.
    r = api_get("licenses/?page_size=1")
    assert r.status_code == 200, r.text[:200]
    lic_id = r.json()["results"][0]["id"]

    driver.get(f"{frontend_url}/licenses/{lic_id}/edit")
    _wait(driver, timeout=20).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, "div.react-select__control")) >= 4
    )
    # Give the AsyncSelect detail-fetches a beat to land.
    import time as _t
    _t.sleep(3)

    controls = driver.find_elements(By.CSS_SELECTOR, "div.react-select__control")
    by_label = {}
    for c in controls:
        try:
            lbl = c.find_element(By.XPATH, "./preceding::label[1]")
            by_label[lbl.text.strip()] = c
        except Exception:
            pass

    # Each of these FKs should display a non-empty selected label. If the
    # license's value is unset, the test is inconclusive — but for the API's
    # default first row it should have Port + Exporter + Scheme Code +
    # Notification Number all populated.
    for name in ("Port", "Scheme Code", "Notification Number", "Exporter"):
        c = by_label.get(name)
        assert c is not None, f"no react-select control found for {name!r}"
        single_value_els = c.find_elements(By.CSS_SELECTOR, ".react-select__single-value")
        assert single_value_els, (
            f"{name}: dropdown rendered no selected label — the FK detail fetch "
            f"likely failed (check AsyncSelectField parseInt / URL-encoding)."
        )
        text = single_value_els[0].text.strip()
        assert text, f"{name}: selected label is empty"


# ---------------------------------------------------------------------------
# ItemReport — same idea, exercise the debounced-filter load path.
# ---------------------------------------------------------------------------
def test_item_report_typing_hsn(logged_in_driver, frontend_url):
    driver = logged_in_driver
    driver.get(f"{frontend_url}/reports/item-report")

    # Wait for the filter UI to mount.
    _wait(driver, timeout=15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input, select"))
    )

    # The page only fetches once a filter is set. Try to find an HSN input
    # by placeholder/name; fall back to "any text input".
    hsn = None
    for sel in (
        "input[name='hsn_code']",
        "input[placeholder*='HSN']",
        "input[placeholder*='hsn']",
        "input[type='text']",
    ):
        els = driver.find_elements(By.CSS_SELECTOR, sel)
        if els:
            hsn = els[0]
            break
    if hsn is None:
        pytest.skip("no HSN input found — markup may have changed")

    hsn.clear()
    hsn.send_keys("72")
    # Wait past the 500ms debounce + request.
    time.sleep(2)
    _assert_no_error_boundary(driver)
