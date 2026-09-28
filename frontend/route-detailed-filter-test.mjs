#!/usr/bin/env node
/**
 * Detailed filter inspection and testing
 * Checks for filter UI patterns in different ways
 */

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'http://localhost:5173';

// Focus on key routes with filters
const ROUTES_WITH_EXPECTED_FILTERS = [
  { path: '/licenses', name: 'Licenses' },
  { path: '/allotments', name: 'Allotments' },
  { path: '/reports/item-report', name: 'Item Report' },
  { path: '/license-ledger', name: 'License Ledger' },
  { path: '/admin/users', name: 'Users' },
  { path: '/admin/activity-log', name: 'Activity Log' },
];

async function inspectRoute(browser, route) {
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // Navigate
    await page.goto(`${BASE_URL}${route.path}`, {
      waitUntil: 'networkidle',
      timeout: 30000,
    });

    // Wait a bit for any JS to settle
    await page.waitForTimeout(1000);

    // Get the full HTML
    const html = await page.content();

    // Try various filter detection patterns
    const filters = {
      byDataTestId: await page.locator('[data-testid*="filter"]').count(),
      byClass: await page.locator('[class*="filter"]').count(),
      byAriaLabel: await page.locator('[aria-label*="filter" i]').count(),
      byDataRole: await page.locator('[role="search"]').count(),
      byInputElements: await page.locator('input[type="text"], input[type="search"], select').count(),
      bySearchClass: await page.locator('[class*="search"]').count(),
      byButtonsWithFilter: await page.locator('button:has-text("Filter")').count(),
      byCheckboxes: await page.locator('input[type="checkbox"]').count(),
      byRadios: await page.locator('input[type="radio"]').count(),
    };

    // Look for specific filter patterns
    const patterns = {
      hasTableFilters: html.includes('FilterIcon') || html.includes('filter-icon'),
      hasSearchBox: html.includes('search-box') || html.includes('search'),
      hasAdvancedFilter: html.includes('advanced-filter') || html.includes('AdvancedFilter'),
      hasQuickFilter: html.includes('quick-filter') || html.includes('QuickFilter'),
      hasActiveFilters: html.includes('active-filter') || html.includes('ActiveFilter'),
      hasFilterPanel: html.includes('filter-panel') || html.includes('FilterPanel'),
    };

    // Get all input elements and their attributes
    const inputs = await page.locator('input').all();
    const inputInfo = [];
    for (let i = 0; i < Math.min(inputs.length, 5); i++) {
      try {
        const placeholder = await inputs[i].getAttribute('placeholder');
        const name = await inputs[i].getAttribute('name');
        const id = await inputs[i].getAttribute('id');
        const type = await inputs[i].getAttribute('type');
        inputInfo.push({ type, name, id, placeholder });
      } catch (e) {
        // ignore
      }
    }

    // Get all buttons that might be filter-related
    const buttons = await page.locator('button').all();
    const filterLikeButtons = [];
    for (let i = 0; i < Math.min(buttons.length, 10); i++) {
      try {
        const text = await buttons[i].textContent();
        if (text && (text.toLowerCase().includes('filter') || text.toLowerCase().includes('search'))) {
          filterLikeButtons.push(text.trim());
        }
      } catch (e) {
        // ignore
      }
    }

    // Get all select elements
    const selects = await page.locator('select').all();
    const selectInfo = [];
    for (let i = 0; i < Math.min(selects.length, 5); i++) {
      try {
        const id = await selects[i].getAttribute('id');
        const name = await selects[i].getAttribute('name');
        selectInfo.push({ id, name });
      } catch (e) {
        // ignore
      }
    }

    // Take screenshot
    const screenshot = await page.screenshot({ path: `/tmp/filter-inspect-${route.path.replace(/\//g, '-')}.png` });

    const result = {
      route: route.path,
      name: route.name,
      filters,
      patterns,
      inputCount: inputs.length,
      selectCount: selects.length,
      buttonCount: buttons.length,
      filterLikeButtons,
      sampleInputs: inputInfo,
      sampleSelects: selectInfo,
    };

    return result;
  } catch (error) {
    return {
      route: route.path,
      name: route.name,
      error: error.message,
    };
  } finally {
    await context.close();
  }
}

async function main() {
  console.log('Starting detailed filter inspection...\n');

  let browser;
  try {
    browser = await chromium.launch({ headless: true });

    const results = [];

    for (const route of ROUTES_WITH_EXPECTED_FILTERS) {
      console.log(`Inspecting: ${route.path}`);
      const result = await inspectRoute(browser, route);
      results.push(result);
    }

    // Generate detailed report
    const reportPath = '/Users/drushahardiksottany/Developer/projects/license-manager/ROUTE_FILTER_INSPECTION_REPORT.md';

    let report = '# Route Filter Inspection Report\n\n';
    report += `Generated: ${new Date().toISOString()}\n\n`;

    results.forEach((result) => {
      report += `## ${result.name} (\`${result.route}\`)\n\n`;

      if (result.error) {
        report += `**Error**: ${result.error}\n\n`;
        return;
      }

      report += '### Filter Detection Results\n\n';
      report += '| Method | Count |\n';
      report += '|--------|-------|\n';
      Object.entries(result.filters).forEach(([key, count]) => {
        report += `| ${key} | ${count} |\n`;
      });

      report += '\n### Patterns Found\n\n';
      Object.entries(result.patterns).forEach(([key, found]) => {
        report += `- ${key}: ${found ? '✅' : '❌'}\n`;
      });

      report += `\n### DOM Element Count\n\n`;
      report += `- Input Elements: ${result.inputCount}\n`;
      report += `- Select Elements: ${result.selectCount}\n`;
      report += `- Buttons: ${result.buttonCount}\n`;

      if (result.sampleInputs.length > 0) {
        report += '\n### Sample Input Elements\n\n';
        result.sampleInputs.forEach((input) => {
          report += `- Type: ${input.type}, Name: ${input.name}, ID: ${input.id}, Placeholder: ${input.placeholder}\n`;
        });
      }

      if (result.sampleSelects.length > 0) {
        report += '\n### Sample Select Elements\n\n';
        result.sampleSelects.forEach((select) => {
          report += `- Name: ${select.name}, ID: ${select.id}\n`;
        });
      }

      if (result.filterLikeButtons.length > 0) {
        report += '\n### Filter-like Buttons Found\n\n';
        result.filterLikeButtons.forEach((btn) => {
          report += `- ${btn}\n`;
        });
      }

      report += '\n---\n\n';
    });

    fs.writeFileSync(reportPath, report);
    console.log(`\nDetailed report saved to: ${reportPath}`);
    console.log('\nSummary:');
    results.forEach((r) => {
      if (!r.error) {
        const hasAnyFilters = Object.values(r.filters).some((v) => v > 0) || Object.values(r.patterns).some((v) => v);
        console.log(`${r.route}: ${hasAnyFilters ? '✅ Filters detected' : '⚠️  No filters detected'}`);
      }
    });
  } catch (error) {
    console.error('Test suite error:', error.message);
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

main().catch(console.error);
