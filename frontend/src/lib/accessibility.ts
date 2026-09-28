/**
 * Accessibility Testing Utilities
 *
 * Shared helpers for accessibility testing and validation
 * Used by component tests, integration tests, and accessibility audit suite
 */

/**
 * WCAG 2.1 Level AA Contrast Ratios
 */
export const CONTRAST_RATIOS = {
  NORMAL: 4.5,      // Normal text < 18pt or < 14pt bold
  LARGE: 3.0,       // Large text >= 18pt or >= 14pt bold
  GRAPHICS: 3.0,    // UI components and graphics
  AAA_NORMAL: 7.0,  // AAA level - normal text
  AAA_LARGE: 4.5,   // AAA level - large text
} as const;

/**
 * WCAG 2.1 Level AA Touch Target Size
 */
export const TOUCH_TARGET_SIZE = 44; // pixels (minimum)

/**
 * WCAG 2.1 Level AA Focus Indicator Requirements
 */
export const FOCUS_INDICATOR = {
  MIN_WIDTH: 2,     // pixels
  MIN_CONTRAST: 3,  // 3:1 ratio
} as const;

/**
 * Heading Level Hierarchy
 */
export type HeadingLevel = 1 | 2 | 3 | 4 | 5 | 6;

/**
 * Calculate contrast ratio between two colors
 * Formula: (L1 + 0.05) / (L2 + 0.05)
 * Where L is relative luminance
 *
 * @param foreground - Hex color code for foreground
 * @param background - Hex color code for background
 * @returns Contrast ratio (e.g., 4.5)
 */
export function getContrastRatio(foreground: string, background: string): number {
  const fgLuminance = getRelativeLuminance(foreground);
  const bgLuminance = getRelativeLuminance(background);

  const lighter = Math.max(fgLuminance, bgLuminance);
  const darker = Math.min(fgLuminance, bgLuminance);

  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Calculate relative luminance for a color
 * Used in contrast ratio calculation
 *
 * @param hex - Hex color code
 * @returns Relative luminance (0-1)
 */
export function getRelativeLuminance(hex: string): number {
  // Convert hex to RGB
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;

  // Apply gamma correction
  const r_ = r <= 0.03928 ? r / 12.92 : Math.pow((r + 0.055) / 1.055, 2.4);
  const g_ = g <= 0.03928 ? g / 12.92 : Math.pow((g + 0.055) / 1.055, 2.4);
  const b_ = b <= 0.03928 ? b / 12.92 : Math.pow((b + 0.055) / 1.055, 2.4);

  // Return relative luminance
  return 0.2126 * r_ + 0.7152 * g_ + 0.0722 * b_;
}

/**
 * Check if contrast ratio meets WCAG AA standard
 *
 * @param ratio - Contrast ratio
 * @param isLargeText - Whether text is >= 18pt or >= 14pt bold
 * @param level - WCAG level ('AA' or 'AAA')
 * @returns Boolean indicating compliance
 */
export function meetsContrastStandard(
  ratio: number,
  isLargeText: boolean = false,
  level: 'AA' | 'AAA' = 'AA'
): boolean {
  if (level === 'AAA') {
    return isLargeText ? ratio >= CONTRAST_RATIOS.AAA_LARGE : ratio >= CONTRAST_RATIOS.AAA_NORMAL;
  }
  return isLargeText ? ratio >= CONTRAST_RATIOS.LARGE : ratio >= CONTRAST_RATIOS.NORMAL;
}

/**
 * Validate heading hierarchy
 * Checks that headings don't skip levels (e.g., h1 > h3 without h2)
 *
 * @param headingLevels - Array of heading levels [1, 2, 2, 3]
 * @param allowedGap - Maximum allowed level jump (default 1)
 * @returns Array of issues found
 */
export function validateHeadingHierarchy(
  headingLevels: HeadingLevel[],
  allowedGap: number = 1
): string[] {
  const issues: string[] = [];

  // First heading should be h1
  if (headingLevels.length > 0 && headingLevels[0] !== 1) {
    issues.push(`First heading is h${headingLevels[0]}, should be h1`);
  }

  // Check for skipped levels
  for (let i = 1; i < headingLevels.length; i++) {
    const gap = Math.abs(headingLevels[i] - headingLevels[i - 1]);
    if (gap > allowedGap) {
      issues.push(
        `Heading hierarchy skips from h${headingLevels[i - 1]} to h${headingLevels[i]} at position ${i}`
      );
    }
  }

  return issues;
}

/**
 * Check if element is keyboard accessible
 * Element should be focusable or clickable
 *
 * @param element - DOM element to check
 * @returns Boolean indicating keyboard accessibility
 */
export function isKeyboardAccessible(element: Element): boolean {
  const tagName = element.tagName.toLowerCase();
  const tabIndex = element.getAttribute('tabindex');

  // Naturally focusable elements
  const focusableElements = ['a', 'button', 'input', 'select', 'textarea'];

  if (focusableElements.includes(tagName)) {
    // Check if not disabled
    return !(element as HTMLFormElement).disabled;
  }

  // Check for custom tabindex (should be 0 or positive, not -1)
  if (tabIndex !== null) {
    const tabIndexNum = parseInt(tabIndex, 10);
    return tabIndexNum >= 0;
  }

  // Check for clickable roles
  const role = element.getAttribute('role');
  const clickableRoles = ['button', 'link', 'checkbox', 'radio', 'menuitem'];

  if (role && clickableRoles.includes(role)) {
    return true;
  }

  return false;
}

/**
 * Get accessible name of element (as screen reader would announce)
 * Order: aria-labelledby > aria-label > label > placeholder > text content > title
 *
 * @param element - DOM element
 * @returns Accessible name string
 */
export function getAccessibleName(element: Element): string {
  // Check aria-labelledby
  const labelledBy = element.getAttribute('aria-labelledby');
  if (labelledBy) {
    const labels = labelledBy.split(' ').map(id =>
      document.getElementById(id)?.textContent?.trim()
    );
    const validLabel = labels.find(l => l);
    if (validLabel) return validLabel;
  }

  // Check aria-label
  const ariaLabel = element.getAttribute('aria-label');
  if (ariaLabel?.trim()) return ariaLabel.trim();

  // Check associated label (for form elements)
  if (element instanceof HTMLFormElement) {
    const id = element.id;
    if (id) {
      const label = document.querySelector(`label[for="${id}"]`);
      if (label?.textContent) return label.textContent.trim();
    }
  }

  // Check placeholder
  if (element instanceof HTMLInputElement) {
    if (element.placeholder?.trim()) return element.placeholder.trim();
  }

  // Check text content
  const text = element.textContent?.trim();
  if (text) return text;

  // Check title
  const title = element.getAttribute('title');
  if (title?.trim()) return title.trim();

  return '';
}

/**
 * Validate form field accessibility
 * Checks label association, error message, required indicator
 *
 * @param input - Form input element
 * @returns Issues found
 */
export function validateFormFieldAccessibility(input: Element): string[] {
  const issues: string[] = [];

  // Check for label
  const inputId = input.getAttribute('id');
  const ariaLabel = input.getAttribute('aria-label');
  const ariaLabelledBy = input.getAttribute('aria-labelledby');

  let hasLabel = !!ariaLabel || !!ariaLabelledBy;

  if (inputId && !hasLabel) {
    const label = document.querySelector(`label[for="${inputId}"]`);
    hasLabel = !!label;
  }

  if (!hasLabel) {
    issues.push('Form field lacks associated label');
  }

  // Check for error message association
  const ariaDescribedBy = input.getAttribute('aria-describedby');
  if (!ariaDescribedBy) {
    // Warn but not an error for all fields (some may not have errors)
    // issues.push('Form field lacks aria-describedby for error messages');
  }

  // Check aria-invalid if there's an error
  const isInvalid = input.getAttribute('aria-invalid');
  if (isInvalid === 'true' && !ariaDescribedBy) {
    issues.push('Invalid form field should have aria-describedby pointing to error message');
  }

  return issues;
}

/**
 * Check if element has visible focus indicator
 *
 * @param element - DOM element to check
 * @returns Boolean indicating presence of focus indicator
 */
export function hasFocusIndicator(element: Element): boolean {
  const styles = window.getComputedStyle(element);

  // Check for outline
  const outlineWidth = styles.outlineWidth;
  if (outlineWidth && outlineWidth !== 'none' && outlineWidth !== '0px') {
    return true;
  }

  // Check for box-shadow
  if (styles.boxShadow && styles.boxShadow !== 'none') {
    return true;
  }

  // Check for border change on focus
  // This would require :focus-visible state, which is harder to detect statically
  // Consider using browser devtools or visual testing for this

  return false;
}

/**
 * Validate image accessibility
 * Checks for alt text or aria-hidden
 *
 * @param img - Image element
 * @returns Issues found
 */
export function validateImageAccessibility(img: Element): string[] {
  const issues: string[] = [];

  const alt = img.getAttribute('alt');
  const ariaHidden = img.getAttribute('aria-hidden');

  // Image must have alt or be hidden
  if (alt === null && ariaHidden !== 'true') {
    issues.push('Image lacks alt text and is not marked aria-hidden="true"');
  }

  // If alt exists, it should not be empty (unless decorative)
  if (alt === '') {
    // Empty alt is okay for decorative images
    // But should ideally have aria-hidden="true" too
    if (ariaHidden !== 'true') {
      // This is a warning, not an error
      // issues.push('Empty alt should be paired with aria-hidden="true"');
    }
  }

  return issues;
}

/**
 * Validate table accessibility
 * Checks header scope attributes, captions, etc.
 *
 * @param table - Table element
 * @returns Issues found
 */
export function validateTableAccessibility(table: Element): string[] {
  const issues: string[] = [];

  // Check for table caption or aria-label
  const caption = table.querySelector('caption');
  const ariaLabel = table.getAttribute('aria-label');

  if (!caption && !ariaLabel) {
    issues.push('Table should have <caption> or aria-label');
  }

  // Check header cells have scope attribute
  const headers = table.querySelectorAll('th');
  headers.forEach((header, index) => {
    const scope = header.getAttribute('scope');
    if (!scope) {
      issues.push(`Table header ${index + 1} missing scope attribute (use scope="col" or scope="row")`);
    }
  });

  return issues;
}

/**
 * Validate button accessibility
 * Checks for descriptive text or aria-label
 *
 * @param button - Button element
 * @returns Issues found
 */
export function validateButtonAccessibility(button: Element): string[] {
  const issues: string[] = [];

  const text = button.textContent?.trim();
  const ariaLabel = button.getAttribute('aria-label');
  const title = button.getAttribute('title');

  // Button must have accessible name
  if (!text && !ariaLabel && !title) {
    issues.push('Button lacks descriptive text, aria-label, or title');
  }

  // Icon-only buttons need aria-label
  if (!text && ariaLabel?.trim() === '') {
    issues.push('Icon-only button has empty aria-label');
  }

  return issues;
}

/**
 * Get all focusable elements within a container
 *
 * @param container - Container element to search (default: document)
 * @returns Array of focusable elements
 */
export function getFocusableElements(container: Document | Element = document): Element[] {
  const selector = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
    'audio[controls]',
    'video[controls]',
  ].join(', ');

  return Array.from(container.querySelectorAll(selector));
}

/**
 * Test Tab key navigation order
 * Simulates tabbing through elements
 *
 * @param container - Container to test (default: document)
 * @returns Array of elements in tab order
 */
export function getTabOrder(container: Document | Element = document): Element[] {
  const focusable = getFocusableElements(container);

  // Sort by natural tab order
  // (tabindex > 0 first in order, then natural order, then tabindex = 0)
  return focusable.sort((a, b) => {
    const aTabIndex = parseInt(a.getAttribute('tabindex') || '0', 10);
    const bTabIndex = parseInt(b.getAttribute('tabindex') || '0', 10);

    // Positive tabindex takes precedence
    if (aTabIndex > 0 && bTabIndex > 0) {
      return aTabIndex - bTabIndex;
    }
    if (aTabIndex > 0) return -1;
    if (bTabIndex > 0) return 1;

    // Natural order for tabindex = 0 or not set
    return 0;
  });
}

/**
 * Validate aria-live regions
 * Checks that live regions are properly configured
 *
 * @param region - aria-live region element
 * @returns Issues found
 */
export function validateLiveRegion(region: Element): string[] {
  const issues: string[] = [];

  const ariaLive = region.getAttribute('aria-live');
  if (!ariaLive || !['polite', 'assertive', 'off'].includes(ariaLive)) {
    issues.push('aria-live should be "polite", "assertive", or "off"');
  }

  // aria-atomic should be set
  const ariaAtomic = region.getAttribute('aria-atomic');
  if (!ariaAtomic) {
    // This is optional but recommended
    // issues.push('aria-atomic should be specified for live regions');
  }

  return issues;
}

/**
 * Check if color is distinguishable from background
 * Useful for checking if color alone is used to convey meaning
 *
 * @param foreground - Foreground color (hex)
 * @param background - Background color (hex)
 * @param minRatio - Minimum contrast ratio required
 * @returns Boolean indicating if colors are distinguishable
 */
export function areColorsDistinguishable(
  foreground: string,
  background: string,
  minRatio: number = CONTRAST_RATIOS.NORMAL
): boolean {
  return getContrastRatio(foreground, background) >= minRatio;
}

/**
 * Validate dialog/modal accessibility
 *
 * @param dialog - Dialog element
 * @returns Issues found
 */
export function validateDialogAccessibility(dialog: Element): string[] {
  const issues: string[] = [];

  // Dialog should have role
  const role = dialog.getAttribute('role');
  if (role !== 'dialog' && role !== 'alertdialog') {
    issues.push('Dialog should have role="dialog" or role="alertdialog"');
  }

  // Dialog should be labeled
  const ariaLabelledBy = dialog.getAttribute('aria-labelledby');
  const ariaLabel = dialog.getAttribute('aria-label');

  if (!ariaLabelledBy && !ariaLabel) {
    issues.push('Dialog should have aria-labelledby or aria-label');
  }

  return issues;
}

/**
 * Get computed font size in pixels
 * Used to determine if text is "large" for contrast ratios
 *
 * @param element - Element to check
 * @returns Font size in pixels
 */
export function getFontSizeInPixels(element: Element): number {
  const styles = window.getComputedStyle(element);
  const fontSize = styles.fontSize;
  return parseFloat(fontSize);
}

/**
 * Check if text is considered "large" for WCAG
 * Large text = >= 18pt (24px) or >= 14pt (18.67px) bold
 *
 * @param element - Text element to check
 * @returns Boolean indicating if text is large
 */
export function isLargeText(element: Element): boolean {
  const fontSize = getFontSizeInPixels(element);
  const fontWeight = window.getComputedStyle(element).fontWeight;
  const fontWeightNum = parseInt(fontWeight, 10);

  // >= 18pt (24px)
  if (fontSize >= 24) return true;

  // >= 14pt (18.67px) and bold (700+)
  if (fontSize >= 18.67 && fontWeightNum >= 700) return true;

  return false;
}

/**
 * Accessibility test report generator
 * Collects and formats accessibility issues
 */
export class A11yTestReport {
  private issues: Map<string, string[]> = new Map();

  addIssue(category: string, issue: string) {
    if (!this.issues.has(category)) {
      this.issues.set(category, []);
    }
    this.issues.get(category)!.push(issue);
  }

  addIssues(category: string, issues: string[]) {
    issues.forEach(issue => this.addIssue(category, issue));
  }

  getReport(): { category: string; issues: string[] }[] {
    return Array.from(this.issues.entries()).map(([category, issues]) => ({
      category,
      issues,
    }));
  }

  hasCriticalIssues(): boolean {
    return this.issues.size > 0;
  }

  toString(): string {
    const report = this.getReport();
    if (report.length === 0) {
      return 'No accessibility issues found!';
    }

    return report
      .map(({ category, issues }) => `${category}:\n  - ${issues.join('\n  - ')}`)
      .join('\n\n');
  }
}

export default {
  CONTRAST_RATIOS,
  TOUCH_TARGET_SIZE,
  FOCUS_INDICATOR,
  getContrastRatio,
  getRelativeLuminance,
  meetsContrastStandard,
  validateHeadingHierarchy,
  isKeyboardAccessible,
  getAccessibleName,
  validateFormFieldAccessibility,
  hasFocusIndicator,
  validateImageAccessibility,
  validateTableAccessibility,
  validateButtonAccessibility,
  getFocusableElements,
  getTabOrder,
  validateLiveRegion,
  areColorsDistinguishable,
  validateDialogAccessibility,
  getFontSizeInPixels,
  isLargeText,
  A11yTestReport,
};
