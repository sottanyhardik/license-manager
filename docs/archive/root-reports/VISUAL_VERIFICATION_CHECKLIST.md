# Visual Verification Checklist: PDF/Excel Ledger Exports

**Purpose:** Verify that PDF and Excel ledger exports display correct currencies, formatting, and data reconciliation after recent ledger fixes (P/L sign, Purchase/Sale column naming, balance calculations).

**Status:** Ready to execute once exports are generated
**Date:** 2026-08-14

---

## 1. COLUMN HEADERS VERIFICATION

### PDF Headers (Landscape A4)
- [ ] `License No.` present and left-aligned
- [ ] `Type` present and centered
- [ ] `Exporter` present (supports multi-line)
- [ ] `License Date` present
- [ ] `Expiry` present
- [ ] `Purchase ($)` header present (dollar sign, USD values)
- [ ] `Sold ($)` header present (dollar sign, USD values)
- [ ] `Balance ($)` header present (dollar sign, USD values)
- [ ] `Purchase Amt (INR)` header present (rupee context)
- [ ] `Sale Amt (INR)` header present (rupee context)
- [ ] `P/L (INR)` header present (rupee context)
- [ ] `Status` header present

### Excel Headers (Sheet "License Summary")
- [ ] Row headers match PDF exactly
- [ ] Headers use bold white font on dark background
- [ ] All 12 columns visible without truncation
- [ ] Column widths auto-fit for readability

---

## 2. CURRENCY FORMATTING VERIFICATION

### INR Column Values (Purchase Amt, Sale Amt, P/L)
- [ ] Currency displayed as `₹` (rupee symbol), NOT `Rs`, NOT `$`
- [ ] Format: `₹45,83,719.00` (Indian number style with comma separators)
- [ ] Decimal places: 2 (e.g., `₹1,00,000.00`)
- [ ] No USD values (`$`) appear in INR columns
- [ ] "No Purchase" text appears correctly when purchase_amount = 0
- [ ] Dash (`-`) appears when sale_amount = 0 or not applicable

### USD Column Values (Purchase, Sold, Balance)
- [ ] Currency displayed as `$` (dollar sign)
- [ ] Format: `$100,000.00` (Indian-style grouping for readability)
- [ ] Decimal places: 2
- [ ] No rupee symbol (`₹`) appears in USD columns
- [ ] No "INR" text appears in USD columns

### Total Row Currency Formatting
- [ ] Total row has **bold** currency formatting
- [ ] Purchase Total uses `$` if USD data present
- [ ] Sale Total uses `$` if USD data present
- [ ] Balance Total uses `$` if USD data present
- [ ] Purchase Amt Total uses `₹` with bold formatting
- [ ] Sale Amt Total uses `₹` with bold formatting
- [ ] P/L Total uses `₹` with bold formatting

---

## 3. NUMBER FORMATTING (INDIAN STYLE)

### Examples of Correct Formatting
- `₹45,83,719.00` (not `₹4,583,719.00`)
- `₹10,00,000.00` (not `₹1,000,000.00`)
- `₹99,999.99` (not `₹99999.99`)
- `$45,83,719.00` (same separator style for USD)

### PDF Data Rows
- [ ] All monetary values use Indian grouping (comma every 2 digits from right, then every 3)
- [ ] No underscores or spaces used as separators
- [ ] Decimals always present (.00 minimum)

### Excel Data Rows
- [ ] All monetary values match PDF formatting
- [ ] Custom number format applied: `#,##,###.00` or equivalent
- [ ] No Excel auto-formatting overrides the custom format

---

## 4. PROFIT/LOSS (P/L) SIGN AND COLOR

### Correct P/L Behavior
- Positive profit: **Green text**, value shown as positive (e.g., `₹19,40,337.00`)
- Negative loss: **Red text**, value shown as negative (e.g., `-₹5,000.00`) or in red
- Zero/break-even: Black text, shown as `₹0.00`

### PDF P/L Column
- [ ] Profitable rows show green text
- [ ] Loss rows show red text
- [ ] P/L value sign matches color (no mixed signs/colors)
- [ ] Total P/L row uses bold green/red matching the sum
- [ ] "UNAVAILABLE" state handled (shown as dash or N/A if applicable)
- [ ] "BREAK_EVEN" state shown as `₹0.00` in black

### Excel P/L Column
- [ ] Profitable rows show green font (RGB: 46, 125, 50 or #2E7D32)
- [ ] Loss rows show red font (RGB: 211, 47, 47 or #D32F2F)
- [ ] Color matches PDF appearance
- [ ] Total P/L bold font matching color

---

## 5. ROW COUNT AND DATA INTEGRITY

### PDF Page Layout
- [ ] No rows cut off at page breaks (repeating header on new page if needed)
- [ ] Row count matches expected licenses (verify against UI)
- [ ] Total row present at bottom of table
- [ ] No duplicate rows
- [ ] No missing licenses from the filter criteria

### Excel Data Rows
- [ ] Data starts at correct row (after headers)
- [ ] All licenses from query params included
- [ ] No duplicate rows
- [ ] Total row immediately follows last license row
- [ ] Row count in sheet matches PDF count

### Reconciliation: UI ↔ PDF ↔ Excel
| Item | UI Row Count | PDF Row Count | Excel Row Count | Match? |
|------|--------------|---------------|-----------------|--------|
| Active Licenses | ??? | ??? | ??? | [ ] |
| Licenses w/ Purchase | ??? | ??? | ??? | [ ] |
| Licenses w/ No Purchase | ??? | ??? | ??? | [ ] |
| **TOTAL** | **???** | **???** | **???** | [ ] |

---

## 6. SPECIFIC DATA FIELDS VERIFICATION

### Per-License Row (Pick a sample license for detailed inspection)

**License:** [INSERT NUMBER]

#### PDF Row
- [ ] License number: `_____________`
- [ ] Type: `_____________`
- [ ] Exporter name: `_____________` (wrapped if long)
- [ ] License Date: `DD-MMM-YY` format (e.g., `14-Aug-26`)
- [ ] Expiry Date: `DD-MMM-YY` format
- [ ] Purchase (USD): `$_____________`
- [ ] Sold (USD): `$_____________`
- [ ] Balance (USD): `$_____________` (Purchase - Sold)
- [ ] Purchase Amt (INR): `₹_____________`
- [ ] Sale Amt (INR): `₹_____________`
- [ ] P/L (INR): `₹_____________` (green/red as appropriate)
- [ ] Status: `Act` or `Exp`

#### Excel Row (Same License)
- [ ] All values match PDF row exactly
- [ ] Formatting identical (currency symbol, number grouping, decimals)
- [ ] Colors match (green/red for P/L)

---

## 7. TOTAL ROW VERIFICATION

### PDF Total Row (Last Data Row)
- [ ] First cell displays `TOTAL` in bold
- [ ] Row is visually distinct (bold font, background fill if applicable)
- [ ] Columns 2-5 (Type, Exporter, License Date, Expiry): **EMPTY** or filled with totals context
- [ ] Purchase Total: `$SUM` (bold, Indian format)
- [ ] Sold Total: `$SUM` (bold, Indian format)
- [ ] Balance Total: `$SUM` (bold, Indian format, = Purchase - Sold)
- [ ] Purchase Amt Total: `₹SUM` (bold, Indian format)
- [ ] Sale Amt Total: `₹SUM` (bold, Indian format)
- [ ] P/L Total: `₹SUM` (bold, green/red matching sign)
- [ ] Status: **EMPTY**

### Calculations
- [ ] Purchase Total = Sum of all Purchase (USD) values
- [ ] Sold Total = Sum of all Sold (USD) values
- [ ] Balance Total = Purchase Total - Sold Total
- [ ] Purchase Amt Total = Sum of all Purchase Amt (INR) values
- [ ] Sale Amt Total = Sum of all Sale Amt (INR) values
- [ ] P/L Total = Sum of all P/L (INR) values

### Excel Total Row
- [ ] Matches PDF formatting (bold font)
- [ ] Has cell fill color (gray background: #ECF0F1)
- [ ] All totals use formulas (e.g., `=SUM(F2:F[last_row])`)
- [ ] Formula results match PDF totals exactly

---

## 8. SPECIAL CASES VERIFICATION

### Licenses with NO PURCHASE Transaction
- [ ] Purchase Amt (INR) shows `No Purchase` (not `₹0.00`, not "N/A")
- [ ] Sale Amt (INR) shows `-` (dash)
- [ ] P/L (INR) shows `-` (dash)
- [ ] Row background color (if applicable): light red/pink (#FFEBEE) for visual alert
- [ ] PDF includes count of "no purchase" licenses in header/footer
- [ ] Excel includes warning row: `⚠ WARNING: N license(s) with no purchase transactions`

### Licenses with NEGATIVE BALANCE
- [ ] Balance (USD) shown as negative (e.g., `-$5,000.00`) or in red
- [ ] Row background: red with white text (if styling applied)
- [ ] P/L calculation not affected by negative balance

### Licenses with ZERO Balance
- [ ] Balance (USD) shown as `$0.00` (not hidden, not empty)
- [ ] Calculation correct: (Purchase - Sold = 0)

---

## 9. FILTER AND CONTEXT VERIFICATION

### PDF Report Metadata
- [ ] Title: "LICENSE LEDGER - SUMMARY" or "LICENSE LEDGER - DETAILED" or "[COMPANY NAME] LEDGER"
- [ ] Date generated: shown in footer (current date/time)
- [ ] Filter info displayed (e.g., "License Type: DFIA", "Status: Active Only")
- [ ] License count shown (e.g., "Total: 42 licenses")
- [ ] Company name (if company-scoped export): shown at top

### Excel Report Metadata
- [ ] Title row: "LICENSE LEDGER - SUMMARY"
- [ ] Row 2: Filter info ("License Type = DFIA | Status = Active Only | Total = 42 licenses")
- [ ] Row 3: Warning (if applicable) about no-purchase licenses
- [ ] Headers in correct row

---

## 10. DARK MODE / PRINT MODE (If Applicable)

### PDF
- [ ] Header background color: dark (`#2c3e50`) with white text (readable in print)
- [ ] Body text: dark on light or light on dark (sufficient contrast)
- [ ] P/L colors: green/red readable in both screen and print

### Excel
- [ ] Background fills visible in screen view
- [ ] "Print Preview" shows correct colors and layout
- [ ] No color-dependent information (symbols + text confirm intent)

---

## 11. RECONCILIATION: UI ↔ PDF ↔ EXCEL

### Sample License Transaction Details (if detailed export)

**License:** [INSERT NUMBER]

| Column | UI Value | PDF Value | Excel Value | Match? |
|--------|----------|-----------|-------------|--------|
| Purchase Bill (₹) | ??? | ??? | ??? | [ ] |
| Sale Bill (₹) | ??? | ??? | ??? | [ ] |
| Opening Balance | ??? | ??? | ??? | [ ] |
| Running Balance | ??? | ??? | ??? | [ ] |
| Current Balance | ??? | ??? | ??? | [ ] |

---

## 12. DEFECT LOG

If any visual issue found, record here:

| Row | Column | Expected | Actual | Severity | Notes |
|-----|--------|----------|--------|----------|-------|
| [#] | [Col] | [Value] | [Value] | BLOCKER/MAJOR/MINOR | [Description] |
|  |  |  |  |  |  |
|  |  |  |  |  |  |

---

## 13. EXECUTION LOG

**Tester Name:** _________________
**Date:** _________________
**Time:** _________________

**Exports Tested:**
- [ ] PDF Summary (all licenses)
- [ ] PDF Detailed (with transactions, if applicable)
- [ ] PDF Company-Scoped (if applicable)
- [ ] Excel Summary
- [ ] Excel Detailed (if applicable)
- [ ] Excel Company-Scoped (if applicable)

**Filter Criteria Used:**
- License Type: `_________________`
- Active Only: `[ ] Yes [ ] No`
- Company (if scoped): `_________________`

**Overall Result:**
- [ ] **PASS** - All checks satisfied, no blockers
- [ ] **PASS with MINORS** - All checks satisfied, minor cosmetic issues only
- [ ] **FAIL** - One or more blocker issues found (see defect log)

**Notes:**
```
[Add any additional observations, environment info, or test conditions here]
```

---

## 14. FINAL SIGN-OFF

**Verification completed by:** _________________
**Date & Time:** _________________
**Approved by PM/Tech Lead:** _________________

**Summary:**
> [Paste key findings, e.g., "All currency symbols correct (₹ in INR cols, $ in USD cols), totals reconcile with UI, P/L colors accurate. 3 active licenses, 1 no-purchase alert shown correctly."]

---

## Appendix A: Expected Data Structure

### PDF Columns (12 total)
1. License No. (string, max 14 chars)
2. Type (string, max 6 chars)
3. Exporter (string, wrapped)
4. License Date (DD-MMM-YY)
5. Expiry (DD-MMM-YY)
6. Purchase ($) - USD
7. Sold ($) - USD
8. Balance ($) - USD
9. Purchase Amt (INR) - Indian currency
10. Sale Amt (INR) - Indian currency
11. P/L (INR) - Indian currency, colored
12. Status (Act/Exp)

### Excel Columns (same 12)
Rows:
- Row 1: Title (merged A-L)
- Row 2: Filter info (merged A-L)
- Row 3: No-purchase warning (merged A-L, if applicable)
- Row 4: (blank)
- Row 5: Headers
- Row 6+: Data rows
- Last row: TOTAL row

---

## Appendix B: Currency Symbol Reference

| Currency | Symbol | Code | Used In |
|----------|--------|------|---------|
| USD | $ | USD | Purchase ($), Sold ($), Balance ($) columns |
| INR | ₹ | INR | Purchase Amt (INR), Sale Amt (INR), P/L (INR) columns |

**Incorrect symbols to watch for:**
- `Rs` or `Rs.` (old Indian notation)
- `₨` (Pakistani rupee, wrong country)
- Missing symbol entirely

---

## Appendix C: Indian Number Formatting Examples

```
Amount         Correct Format    Incorrect Format
100            ₹100.00          ₹100
1,000          ₹1,000.00        ₹1000.00
10,000         ₹10,000.00       ₹10000.00
100,000        ₹1,00,000.00     ₹100,000.00
1,000,000      ₹10,00,000.00    ₹1,000,000.00
10,000,000     ₹1,00,00,000.00  ₹10,000,000.00
45,837,190     ₹45,83,71,900.00 ₹45,837,190.00
```

---

**Checklist Version:** 1.0
**Last Updated:** 2026-08-14
