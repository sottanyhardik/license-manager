#!/usr/bin/env node
/**
 * Authenticated route browser testing script
 * Tests all routes while logged in
 */

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'http://localhost:5173';
const LOGIN_URL = `${BASE_URL}/login`;

// Test credentials from conftest.py
const USERNAME = process.env.LM_USERNAME || 'hardik';
const PASSWORD = process.env.LM_PASSWORD || 'admin@123';

// All routes to test
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

async function login(page) {
  console.log('Logging in...');

  await page.goto(LOGIN_URL, { waitUntil: 'networkidle', timeout: 30000 });

  // Fill in login form
  await page.fill('#login-username', USERNAME);
  await page.fill('#login-password', PASSWORD);

  // Submit form
  const submitButton = page.locator('button[type="submit"]');
  await submitButton.click();

  // Wait for redirect to dashboard
  await page.waitForURL(`${BASE_URL}/dashboard`, { timeout: 30000 });
  console.log('✓ Logged in successfully\n');
}

async function testRoute(page, route, results) {
  try {
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

    // Check for filter controls with different patterns
    const filterPatterns = {
      byDataTestId: await page.locator('[data-testid*="filter"]').count(),
      byClass: await page.locator('[class*="filter"]').count(),
      byAriaLabel: await page.locator('[aria-label*="filter" i]').count(),
      bySearchInput: await page.locator('input[placeholder*="search" i], input[placeholder*="filter" i]').count(),
      selectElements: await page.locator('select').count(),
      checkboxes: await page.locator('input[type="checkbox"]').count(),
    };

    const hasAnyFilters = Object.values(filterPatterns).some(v => v > 0);

    // Get all console errors
    const consoleErrors = [];
    const consoleWarnings = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      } else if (msg.type() === 'warning') {
        consoleWarnings.push(msg.text());
      }
    });

    // Get any network errors
    const networkErrors = [];
    page.on('response', (response) => {
      if (response.status() >= 400 && response.status() < 600) {
        networkErrors.push({
          status: response.status(),
          url: response.url(),
        });
      }
    });

    results.push({
      route: route.path,
      name: route.name,
      category: route.category,
      loads: statusOk,
      statusCode: response?.status(),
      title,
      url,
      loadTime,
      hasFilters: hasAnyFilters,
      filterDetails: filterPatterns,
      consoleErrorCount: consoleErrors.length,
      consoleWarningCount: consoleWarnings.length,
      networkErrorCount: networkErrors.length,
    });

    const status = statusOk && hasAnyFilters ? '✅' : statusOk ? '⚠️' : '❌';
    console.log(`${status} ${route.path} (${loadTime}ms, filters: ${hasAnyFilters ? 'yes' : 'no'})`);
  } catch (error) {
    results.push({
      route: route.path,
      name: route.name,
      category: route.category,
      loads: false,
      error: error.message,
    });

    console.error(`❌ ${route.path} - ${error.message}`);
  }
}

async function main() {
  console.log('Starting authenticated route browser testing...\n');

  let browser;
  try {
    browser = await chromium.launch({ headless: true });

    // Create a persistent context to maintain login
    const context = await browser.newContext();
    const page = await context.newPage();

    // Log in once
    await login(page);

    const results = [];

    // Test each route
    for (const route of ROUTES) {
      await testRoute(page, route, results);
    }

    await context.close();

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
  const reportPath = '/Users/drushahardiksottany/Developer/projects/license-manager/ROUTE_AUTHENTICATED_TEST_REPORT.md';

  let report = '# Authenticated Route Browser Testing Report\n\n';
  report += `Generated: ${new Date().toISOString()}\n\n`;
  report += `Total Routes Tested: ${results.length}\n`;
  report += `Passed: ${results.filter((r) => r.loads).length}\n`;
  report += `Failed: ${results.filter((r) => !r.loads).length}\n`;
  report += `Routes with Filters: ${results.filter((r) => r.hasFilters && r.loads).length}\n\n`;

  // Summary table
  report += '## Summary\n\n';
  report += '| Route | Name | Category | Loads | Filters | Load Time | Console Issues | Status |\n';
  report += '|-------|------|----------|-------|---------|-----------|---|--------|\n';

  results.forEach((result) => {
    const status = result.loads ? '✅ PASS' : '❌ FAIL';
    const filtersStr = result.hasFilters ? '✅' : '⚠️ none';
    const loadTimeStr = result.loadTime ? `${result.loadTime}ms` : 'N/A';
    const consoleIssues = result.consoleErrorCount > 0 ? `❌ ${result.consoleErrorCount} errors` : '✅';

    report += `| \`${result.route}\` | ${result.name} | ${result.category} | ${result.loads ? '✅' : '❌'} | ${filtersStr} | ${loadTimeStr} | ${consoleIssues} | ${status} |\n`;
  });

  // Routes with filters
  const withFilters = results.filter((r) => r.hasFilters && r.loads);
  if (withFilters.length > 0) {
    report += '\n## Routes with Filters Detected\n\n';
    withFilters.forEach((route) => {
      report += `- **${route.name}** (\`${route.route}\`)\n`;
      report += `  - Data-TestID elements: ${route.filterDetails.byDataTestId}\n`;
      report += `  - Class-based filters: ${route.filterDetails.byClass}\n`;
      report += `  - Search inputs: ${route.filterDetails.bySearchInput}\n`;
      report += `  - Select elements: ${route.filterDetails.selectElements}\n`;
      report += `  - Checkboxes: ${route.filterDetails.checkboxes}\n`;
    });
  }

  // Routes without filters
  const noFilters = results.filter((r) => !r.hasFilters && r.loads);
  if (noFilters.length > 0) {
    report += '\n## Routes Without Filters\n\n';
    noFilters.forEach((route) => {
      report += `- ${route.route}\n`;
    });
  }

  // Failed routes
  const failures = results.filter((r) => !r.loads);
  if (failures.length > 0) {
    report += '\n## Failed Routes\n\n';
    failures.forEach((failure) => {
      report += `### ${failure.route}\n\n`;
      report += `- **Name**: ${failure.name}\n`;
      report += `- **Error**: ${failure.error}\n\n`;
    });
  }

  fs.writeFileSync(reportPath, report);
  console.log(`\n✓ Report saved to: ${reportPath}`);
}

// Run tests
main().catch(console.error);
