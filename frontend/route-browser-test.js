#!/usr/bin/env node
/* global require */
/**
 * Comprehensive route browser testing script
 * Tests all 30+ filterable routes in the License Manager app
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost:5173';

// List of all routes to test
const ROUTES = [
  // Master List Routes
  { path: '/licenses', name: 'Licenses', category: 'Master List' },
  { path: '/allotments', name: 'Allotments', category: 'Master List' },
  { path: '/bill-of-entries', name: 'Bill of Entries', category: 'Master List' },
  { path: '/trades', name: 'Trades', category: 'Master List' },
  { path: '/incentive-licenses', name: 'Incentive Licenses', category: 'Master List' },
  { path: '/masters/company', name: 'Masters - Company', category: 'Master List' },

  // Report Routes
  { path: '/reports/parle/sion-e1', name: 'SION E1 Report', category: 'Report' },
  { path: '/reports/parle/sion-e5', name: 'SION E5 Report', category: 'Report' },
  { path: '/reports/parle/sion-e126', name: 'SION E126 Report', category: 'Report' },
  { path: '/reports/parle/sion-e132', name: 'SION E132 Report', category: 'Report' },
  { path: '/reports/expiring-licenses', name: 'Expiring Licenses Report', category: 'Report' },
  { path: '/reports/active-licenses', name: 'Active Licenses Report', category: 'Report' },
  { path: '/reports/download-license', name: 'Download License Report', category: 'Report' },
  { path: '/reports/item-pivot', name: 'Item Pivot Report', category: 'Report' },
  { path: '/reports/item-report', name: 'Item Report', category: 'Report' },
  { path: '/reports/planned-report', name: 'Planned Report', category: 'Report' },
  { path: '/reports/license-purchase-profit', name: 'License Purchase Profit Report', category: 'Report' },

  // Ledger Routes
  { path: '/license-ledger', name: 'License Ledger', category: 'Ledger' },
  { path: '/license-ledger/download-requests', name: 'Download Requests', category: 'Ledger' },
  { path: '/license-ledger/package-readiness/test-job', name: 'Package Readiness', category: 'Ledger' },

  // Admin Routes
  { path: '/admin/users', name: 'Users', category: 'Admin' },
  { path: '/admin/activity-log', name: 'Activity Log', category: 'Admin' },

  // Other Routes
  { path: '/reconciliation', name: 'Reconciliation', category: 'Other' },
  { path: '/reconciliation-issues', name: 'Reconciliation Issues', category: 'Other' },
  { path: '/planning', name: 'Planning', category: 'Other' },
  { path: '/dashboard', name: 'Dashboard', category: 'Core' },
];

async function testRoute(browser, route, results) {
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // Set up console and network error logging
    const consoleErrors = [];
    const networkErrors = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push({
          type: msg.type(),
          text: msg.text(),
        });
      }
    });

    page.on('response', (response) => {
      if (!response.ok() && response.status() >= 400) {
        networkErrors.push({
          status: response.status(),
          url: response.url(),
        });
      }
    });

    // Navigate to the route
    const startTime = Date.now();
    const response = await page.goto(`${BASE_URL}${route.path}`, {
      waitUntil: 'networkidle',
      timeout: 30000,
    });
    const loadTime = Date.now() - startTime;

    // Check if page loaded successfully
    const statusOk = response && response.ok();
    const title = await page.title();
    const url = page.url();

    // Take a screenshot
    const screenshotPath = path.join(
      '/tmp',
      `route-${route.path.replace(/\//g, '-')}-${Date.now()}.png`
    );
    await page.screenshot({ path: screenshotPath });

    // Check for filter controls
    const hasFilters = await page.locator('[data-testid="filter"], .filter, [class*="filter"]').count() > 0;
    const hasActiveFilters = await page.locator('[data-testid="active-filters"], [class*="active-filter"]').count() > 0;

    // Check for loading state (should be gone)
    const isLoading = await page.locator('[data-testid="loader"], [class*="loading"]').isVisible().catch(() => false);

    // Collect errors from the page
    const bodyText = await page.textContent('body');
    const hasErrorMessage = bodyText.includes('Error') || bodyText.includes('error');

    results.push({
      route: route.path,
      name: route.name,
      category: route.category,
      loads: statusOk,
      statusCode: response?.status(),
      title,
      url,
      loadTime,
      consoleErrors: consoleErrors.length > 0,
      consoleErrorCount: consoleErrors.length,
      consoleErrorDetails: consoleErrors,
      networkErrors: networkErrors.length > 0,
      networkErrorCount: networkErrors.length,
      networkErrorDetails: networkErrors,
      hasFilters,
      hasActiveFilters,
      isLoading,
      hasErrorMessage,
      screenshot: screenshotPath,
    });

    console.log(`✓ Tested: ${route.path}`);
  } catch (error) {
    results.push({
      route: route.path,
      name: route.name,
      category: route.category,
      loads: false,
      error: error.message,
      errorType: error.name,
      consoleErrorCount: 0,
      networkErrorCount: 0,
    });

    console.error(`✗ Failed: ${route.path} - ${error.message}`);
  } finally {
    await context.close();
  }
}

async function main() {
  console.log('Starting browser route testing...\n');

  let browser;
  try {
    browser = await chromium.launch({
      headless: true,
      args: ['--disable-blink-features=AutomationControlled'],
    });

    const results = [];

    // Test each route
    for (const route of ROUTES) {
      await testRoute(browser, route, results);
    }

    // Generate report
    generateReport(results);
  } catch (error) {
    console.error('Test suite error:', error.message);
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

function generateReport(results) {
  const reportPath = '/Users/drushahardiksottany/Developer/projects/license-manager/ROUTE_BROWSER_TEST_REPORT.md';

  let report = '# Route Browser Testing Report\n\n';
  report += `Generated: ${new Date().toISOString()}\n`;
  report += `Total Routes Tested: ${results.length}\n`;
  report += `Passed: ${results.filter((r) => r.loads).length}\n`;
  report += `Failed: ${results.filter((r) => !r.loads).length}\n\n`;

  // Summary table
  report += '## Summary\n\n';
  report += '| Route | Name | Category | Loads | Status Code | Console Errors | Network Errors | Filters | Load Time | Status |\n';
  report += '|-------|------|----------|-------|-------------|---|---|---------|----------|--------|\n';

  results.forEach((result) => {
    const status = result.loads ? '✅ PASS' : '❌ FAIL';
    const consoleErrorsStr = result.consoleErrorCount > 0 ? `⚠️ (${result.consoleErrorCount})` : '✅';
    const networkErrorsStr = result.networkErrorCount > 0 ? `⚠️ (${result.networkErrorCount})` : '✅';
    const filtersStr = result.hasFilters ? '✅' : '⚠️ (none)';
    const loadTimeStr = result.loadTime ? `${result.loadTime}ms` : 'N/A';

    report += `| \`${result.route}\` | ${result.name} | ${result.category} | ${result.loads ? '✅' : '❌'} | ${result.statusCode || 'N/A'} | ${consoleErrorsStr} | ${networkErrorsStr} | ${filtersStr} | ${loadTimeStr} | ${status} |\n`;
  });

  // Detailed failures
  const failures = results.filter((r) => !r.loads);
  if (failures.length > 0) {
    report += '\n## Failures\n\n';
    failures.forEach((failure) => {
      report += `### ${failure.route}\n\n`;
      report += `- **Name**: ${failure.name}\n`;
      report += `- **Category**: ${failure.category}\n`;
      report += `- **Error**: ${failure.error}\n`;
      report += `- **Error Type**: ${failure.errorType}\n\n`;
    });
  }

  // Routes with console errors
  const consoleErrorRoutes = results.filter((r) => r.consoleErrors && r.loads);
  if (consoleErrorRoutes.length > 0) {
    report += '\n## Routes with Console Errors\n\n';
    consoleErrorRoutes.forEach((route) => {
      report += `### ${route.route}\n\n`;
      route.consoleErrorDetails.forEach((err) => {
        report += `- ${err.text}\n`;
      });
      report += '\n';
    });
  }

  // Routes with network errors
  const networkErrorRoutes = results.filter((r) => r.networkErrors && r.loads);
  if (networkErrorRoutes.length > 0) {
    report += '\n## Routes with Network Errors\n\n';
    networkErrorRoutes.forEach((route) => {
      report += `### ${route.route}\n\n`;
      route.networkErrorDetails.forEach((err) => {
        report += `- HTTP ${err.status}: ${err.url}\n`;
      });
      report += '\n';
    });
  }

  // Routes without filters
  const noFilterRoutes = results.filter((r) => !r.hasFilters && r.loads);
  if (noFilterRoutes.length > 0) {
    report += '\n## Routes Without Filters\n\n';
    noFilterRoutes.forEach((route) => {
      report += `- ${route.route}\n`;
    });
    report += '\n';
  }

  fs.writeFileSync(reportPath, report);
  console.log(`\nReport saved to: ${reportPath}`);
}

// Run tests
main().catch(console.error);
