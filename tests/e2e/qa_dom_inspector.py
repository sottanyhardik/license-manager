#!/usr/bin/env python3
"""
DOM Inspector: Find actual button and form selectors.
Debug tool to understand the React-rendered DOM structure.
"""

import os
import time
import requests
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


def inspect_licenses_page():
    """Inspect the licenses page structure."""

    # Auth
    r = requests.post(
        "http://localhost:8000/api/auth/login/",
        json={"username": "hardik", "password": "admin@123"},
        timeout=10,
    )
    if r.status_code != 200:
        print("Auth failed")
        return

    token = r.json()["access"]

    # Browser
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)

    try:
        # Navigate
        driver.get("http://localhost:5173/login")
        driver.execute_script(
            "localStorage.setItem('access', arguments[0]);",
            token,
        )

        driver.get("http://localhost:5173/licenses")
        time.sleep(2)

        # Inspect
        print("="*70)
        print("LICENSES PAGE DOM STRUCTURE")
        print("="*70)

        # All buttons on page
        buttons = driver.find_elements(By.TAG_NAME, "button")
        print(f"\n[BUTTONS] Total: {len(buttons)}")
        for i, btn in enumerate(buttons[:10]):
            print(f"  {i}: text='{btn.text}' | classes='{btn.get_attribute('class')}' | type='{btn.get_attribute('type')}'")

        # All links
        links = driver.find_elements(By.TAG_NAME, "a")
        print(f"\n[LINKS] Total: {len(links)}")
        for i, link in enumerate(links[:10]):
            href = link.get_attribute("href")
            print(f"  {i}: text='{link.text}' | href='{href}'")

        # All inputs
        inputs = driver.find_elements(By.TAG_NAME, "input")
        print(f"\n[INPUTS] Total: {len(inputs)}")
        for i, inp in enumerate(inputs[:5]):
            print(f"  {i}: type='{inp.get_attribute('type')}' | placeholder='{inp.get_attribute('placeholder')}'")

        # All tables
        tables = driver.find_elements(By.TAG_NAME, "table")
        print(f"\n[TABLES] Total: {len(tables)}")

        # All divs with role=button
        role_buttons = driver.find_elements(By.XPATH, "//*[@role='button']")
        print(f"\n[ROLE=BUTTON] Total: {len(role_buttons)}")
        for i, btn in enumerate(role_buttons[:5]):
            print(f"  {i}: '{btn.text}' | classes='{btn.get_attribute('class')}'")

        # Check for create-related buttons
        print("\n[CREATE-RELATED ELEMENTS]")
        for selector in [
            ("button with 'Create'", "//button[contains(., 'Create')]"),
            ("button with 'Add'", "//button[contains(., 'Add')]"),
            ("button with 'New'", "//button[contains(., 'New')]"),
            ("a with 'Create'", "//a[contains(., 'Create')]"),
            ("a with 'Add'", "//a[contains(., 'Add')]"),
            ("a with '+' or 'plus'", "//*[contains(@aria-label, 'Create') or contains(@aria-label, 'Add')]"),
        ]:
            try:
                elems = driver.find_elements(By.XPATH, selector[1])
                print(f"  ✓ {selector[0]}: {len(elems)} found")
                if elems:
                    print(f"    → {elems[0].tag_name}: {elems[0].text}")
            except:
                print(f"  ✗ {selector[0]}: not found")

        # Get page HTML (first 3000 chars) to inspect structure
        print("\n[PAGE STRUCTURE EXCERPT]")
        html = driver.page_source

        # Find any header/toolbar section
        if "<header" in html:
            start = html.find("<header")
            end = html.find("</header>") + 9
            print("Header section found")

        # Look for navbar/menu
        if "nav" in html.lower():
            print("Navigation element found")

        # List first 20 actual page content lines
        lines = html.split("\n")
        print(f"Total lines: {len(lines)}")
        print("First 30 non-empty lines:")
        count = 0
        for line in lines:
            if line.strip() and count < 30:
                print(f"  {line[:100]}")
                count += 1

        print("\n[PAGE TITLE]")
        try:
            title = driver.find_element(By.TAG_NAME, "h1")
            print(f"  H1: {title.text}")
        except:
            pass

    finally:
        driver.quit()


if __name__ == "__main__":
    inspect_licenses_page()
