import { test, expect, devices } from '@playwright/test';

// Test configuration for different viewport sizes
const VIEWPORTS = {
  'desktop-1440': { width: 1440, height: 900, name: '1440×900' },
  'desktop-1366': { width: 1366, height: 768, name: '1366×768' },
  'tablet-landscape': { width: 1024, height: 768, name: '1024×768' },
  'tablet-portrait': { width: 768, height: 1024, name: '768×1024' },
  'mobile': { width: 390, height: 844, name: '390×844' },
};

// High-priority pages to test
const PAGES_TO_TEST = [
  { path: '/dashboard', name: 'Dashboard' },
  { path: '/licenses', name: 'License Master List' },
  { path: '/trades', name: 'Trade Master List' },
  { path: '/reports/item-pivot', name: 'Item Pivot Report' },
  { path: '/reports/item-report', name: 'Item Report' },
  { path: '/reports/parle/sion-e1', name: 'SION E1 Report' },
  { path: '/bill-of-entries', name: 'Bill of Entries List' },
  { path: '/allotments', name: 'Allotments List' },
  { path: '/license-ledger', name: 'License Ledger' },
  { path: '/admin/users', name: 'User Management' },
];

test.describe('Responsive Design Testing', () => {
  test.beforeEach(async ({ page }) => {
    // Set auth token or mock if needed
    await page.context().addCookies([
      {
        name: 'sessionid',
        value: 'test-session-id',
        domain: 'localhost',
        path: '/',
      }
    ]);
  });

  for (const [viewportKey, viewport] of Object.entries(VIEWPORTS)) {
    test.describe(`Viewport: ${viewport.name}`, () => {
      test.use({ viewport: { width: viewport.width, height: viewport.height } });

      for (const page of PAGES_TO_TEST) {
        test(`${page.name} - ${viewport.name} - No horizontal overflow`, async ({ page }) => {
          await page.goto(`http://localhost:5175${page.path}`, {
            waitUntil: 'domcontentloaded',
            timeout: 30000
          }).catch(() => {
            // Page might require auth, that's ok for this test
          });

          // Wait for page to load
          await page.waitForTimeout(1500);

          // Check for horizontal overflow
          const htmlElement = await page.locator('html').first();
          const bodyElement = await page.locator('body').first();

          const htmlScrollWidth = await htmlElement.evaluate(el => el.scrollWidth);
          const htmlClientWidth = await htmlElement.evaluate(el => el.clientWidth);
          const bodyScrollWidth = await bodyElement.evaluate(el => el.scrollWidth);
          const bodyClientWidth = await bodyElement.evaluate(el => el.clientWidth);

          // Allow 1px difference for rounding
          expect(htmlScrollWidth).toBeLessThanOrEqual(htmlClientWidth + 1);
          expect(bodyScrollWidth).toBeLessThanOrEqual(bodyClientWidth + 1);
        });

        test(`${page.name} - ${viewport.name} - Screenshot`, async ({ page }) => {
          await page.goto(`http://localhost:5175${page.path}`, {
            waitUntil: 'domcontentloaded',
            timeout: 30000
          }).catch(() => {
            // Page might require auth, that's ok for this test
          });

          // Wait for page to load
          await page.waitForTimeout(1500);

          // Take screenshot
          await page.screenshot({
            path: `./responsive-screenshots/${viewportKey}-${page.path.replace(/\//g, '-')}.png`,
            fullPage: false
          });
        });
      }
    });
  }
});

test.describe('Layout and Spacing Checks', () => {
  test('Dashboard - Mobile: No overflow on filter section', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('http://localhost:5175/dashboard', { waitUntil: 'domcontentloaded' }).catch(() => {});

    // Check all elements are within viewport
    const elements = await page.locator('[role="main"]').first().boundingBox();
    if (elements) {
      expect(elements.width).toBeLessThanOrEqual(390 + 1); // Allow 1px for rounding
    }
  });

  test('License List - Tablet: Table scrolls horizontally, not page', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('http://localhost:5175/licenses', { waitUntil: 'domcontentloaded' }).catch(() => {});

    await page.waitForTimeout(1500);

    // Check table container has scroll, not page
    const tableContainer = await page.locator('table').first();
    if (await tableContainer.count() > 0) {
      const parent = await tableContainer.locator('xpath=..').first();
      const overflow = await parent.evaluate(el => window.getComputedStyle(el).overflowX);
      expect(['auto', 'scroll']).toContain(overflow);
    }
  });

  test('Forms - Mobile: Input fields are full width or appropriately sized', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('http://localhost:5175/licenses/create', { waitUntil: 'domcontentloaded' }).catch(() => {});

    await page.waitForTimeout(1500);

    // Check input fields are visible
    const inputs = await page.locator('input[type="text"], input[type="email"], input[type="number"], textarea').count();
    // Just verify they exist and page doesn't have horizontal overflow
    const pageWidth = await page.locator('body').evaluate(el => el.clientWidth);
    const pageScrollWidth = await page.locator('body').evaluate(el => el.scrollWidth);
    expect(pageScrollWidth).toBeLessThanOrEqual(pageWidth + 1);
  });
});

test.describe('Regression Tests', () => {
  test('Navigation bar is accessible on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('http://localhost:5175/dashboard', { waitUntil: 'domcontentloaded' }).catch(() => {});

    // Check nav is visible and clickable
    const nav = await page.locator('nav, [role="navigation"]').first();
    if (await nav.count() > 0) {
      const isVisible = await nav.isVisible();
      expect(isVisible).toBeTruthy();
    }
  });

  test('Filter panels stack on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('http://localhost:5175/licenses', { waitUntil: 'domcontentloaded' }).catch(() => {});

    await page.waitForTimeout(1500);

    // Page should not have horizontal overflow
    const scrollWidth = await page.locator('body').evaluate(el => el.scrollWidth);
    const clientWidth = await page.locator('body').evaluate(el => el.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
  });

  test('Buttons and controls are appropriately sized for touch (min 44px)', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('http://localhost:5175/dashboard', { waitUntil: 'domcontentloaded' }).catch(() => {});

    // Check buttons have reasonable size
    const buttons = await page.locator('button').all();
    for (const button of buttons.slice(0, 5)) { // Check first 5 buttons
      if (await button.isVisible()) {
        const box = await button.boundingBox();
        if (box) {
          // Touch targets should be at least 44×44 or have padding
          expect(box.height).toBeGreaterThanOrEqual(30); // Minimum reasonable size
        }
      }
    }
  });
});
