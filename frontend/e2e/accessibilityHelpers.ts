import { expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Enforce the release-blocking axe impact levels on a fully rendered route.
 *
 * The browser fixtures deliberately exercise the real app shell with local
 * deterministic API responses.  Keeping this in one helper makes the
 * severity policy explicit: serious and critical WCAG violations fail the
 * workflow, while lower-impact findings remain available in the HTML report
 * for follow-up without masking a release blocker.
 */
export async function expectNoSeriousOrCriticalAxeViolations(page: Page, include?: string) {
  let builder = new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]);
  if (include) {
    builder = builder.include(include);
  }

  const results = await builder.analyze();
  const blockingViolations = results.violations.filter(
    (violation) => violation.impact === "serious" || violation.impact === "critical",
  );

  expect(
    blockingViolations,
    blockingViolations
      .map(
        (violation) =>
          `${violation.id} (${violation.impact}): ${violation.help}\n${violation.nodes
            .map((node) => `  ${node.target.join(", ")}: ${node.failureSummary ?? ""}`)
            .join("\n")}`,
      )
      .join("\n\n"),
  ).toEqual([]);
}

/**
 * A deliberately small, dependency-free semantic regression check for the
 * mock browser journeys.  Full axe coverage is not currently installed in
 * this application; these checks protect the WCAG failures most likely to be
 * introduced while changing layouts without adding a second browser bundle.
 */
export async function expectNoBasicSemanticViolations(page: Page, scope = "main") {
  const violations = await page.locator(scope).evaluate((root) => {
    const isVisible = (element: Element) => {
      const style = window.getComputedStyle(element);
      return !element.hasAttribute("hidden") && style.display !== "none" && style.visibility !== "hidden";
    };
    const hasAccessibleName = (element: Element) => {
      const labelledBy = element.getAttribute("aria-labelledby");
      if (labelledBy) {
        return labelledBy.split(/\s+/).some((id) => Boolean(document.getElementById(id)?.textContent?.trim()));
      }
      return Boolean(
        element.getAttribute("aria-label")?.trim() ||
        element.getAttribute("title")?.trim() ||
        element.textContent?.trim() ||
        (element instanceof HTMLInputElement && element.value.trim()),
      );
    };
    const formControlHasLabel = (element: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement) => {
      if (element.type === "hidden" || element.getAttribute("aria-label") || element.getAttribute("aria-labelledby")) {
        return true;
      }
      if (element.labels?.length) {
        return true;
      }
      const id = element.id;
      return Boolean(id && document.querySelector(`label[for="${CSS.escape(id)}"]`));
    };

    const failures: string[] = [];
    root.querySelectorAll("input, select, textarea").forEach((element) => {
      if (isVisible(element) && !formControlHasLabel(element as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement)) {
        failures.push(`Unlabelled form control: ${element.outerHTML}`);
      }
    });
    root.querySelectorAll("button, [role=button], a[href]").forEach((element) => {
      if (isVisible(element) && !hasAccessibleName(element)) {
        failures.push(`Unnamed interactive control: ${element.outerHTML}`);
      }
    });
    root.querySelectorAll("img").forEach((element) => {
      if (isVisible(element) && !element.hasAttribute("alt")) {
        failures.push(`Image without alt attribute: ${element.outerHTML}`);
      }
    });
    root.querySelectorAll("[role=dialog], [role=alertdialog]").forEach((element) => {
      if (isVisible(element) && !hasAccessibleName(element)) {
        failures.push(`Unlabelled dialog: ${element.outerHTML}`);
      }
    });
    return failures;
  });

  expect(violations).toEqual([]);
}
