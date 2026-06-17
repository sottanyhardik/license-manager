# End-to-end smoke tests

Live-system regression tests. Run these after every backend or frontend change
to confirm nothing 500s and no React page is throwing into the ErrorBoundary.

## What they cover

- **`test_api_smoke.py`** — pytest + `requests`. Hits every backend endpoint
  that has historically broken when fields were moved between
  `LicenseDetailsModel` and its OneToOne sub-tables
  (`LicenseBalance` / `LicenseFlags` / `LicenseNotes` / `LicenseOwnership`),
  including every filter that touches a moved field (`is_active`,
  `is_expired`, `balance_cif_min`, `status=...`, `has_balance`).

- **`test_pages_selenium.py`** — pytest + Selenium (headless Chrome). Loads
  each protected route in a real browser and asserts:
  - The route renders a landmark element.
  - The ErrorBoundary fallback ("Something went wrong") is NOT shown.
  - The browser console has no `SEVERE` entries (the TDZ ReferenceError that
    broke ItemPivotReport / ItemReport would land here).
  - For ItemPivotReport: clicking the first norm tab loads the report (or an
    empty-state card) without crashing.
  - For ItemReport: typing into the HSN filter fires the debounced fetch
    without crashing.

## Prerequisites

Both servers must be running:

```bash
# Terminal 1 — backend
cd backend
DEBUG=true python manage.py runserver

# Terminal 2 — frontend
cd frontend
npm run dev
```

Install test deps into a venv of your choice:

```bash
pip install -r tests/e2e/requirements.txt
```

Selenium 4 ships with `selenium-manager`, which auto-downloads a matching
chromedriver — no manual install needed. Chrome itself must be installed.

## Running

```bash
# Everything
pytest tests/e2e -v

# Just the API checks (fast — no browser)
pytest tests/e2e/test_api_smoke.py -v

# Just the UI checks
pytest tests/e2e/test_pages_selenium.py -v

# A single page
pytest tests/e2e/test_pages_selenium.py -v -k item-pivot

# Headed (watch the browser drive itself)
LM_HEADLESS=0 pytest tests/e2e/test_pages_selenium.py -v
```

## Overrides

| Env var            | Default                   | Purpose                        |
|--------------------|---------------------------|--------------------------------|
| `LM_BACKEND_URL`   | `http://localhost:8000`   | Django dev server URL          |
| `LM_FRONTEND_URL`  | `http://localhost:5173`   | Vite dev server URL            |
| `LM_USERNAME`      | `hardik`                  | Login user                     |
| `LM_PASSWORD`      | `admin@123`               | Login password                 |
| `LM_HEADLESS`      | `1`                       | Set `0` to see the browser     |

Tests are skipped (not failed) when a server isn't reachable, so CI without
the stack up just produces "skipped", not red.

## Adding new tests

- **New endpoint?** Add a parametrize entry in `test_license_viewsets` or a
  fresh test function in `test_api_smoke.py`.
- **New frontend route?** Add it to the `PAGES` list in
  `test_pages_selenium.py`. The landmark-selector argument is a CSS selector
  that proves the page mounted — keep it generic so layout tweaks don't
  break the test.
- **A user-flow regression?** Add a dedicated `test_<flow>()` that drives the
  UI like the existing `test_item_pivot_click_first_norm`.
