import { expect, test } from "@playwright/test";
import { expectNoBasicSemanticViolations, expectNoSeriousOrCriticalAxeViolations } from "./accessibilityHelpers";

/**
 * Browser-level accessibility regression checks that do not require a live
 * backend or user credentials. These deliberately inspect semantics rather
 * than visual implementation details, so they protect the sign-in workflow
 * through future layout redesigns.
 */
test.describe("sign-in accessibility", () => {
  test("keeps labels, keyboard focus, password visibility, and reduced-motion rendering", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/login", { waitUntil: "networkidle" });

    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Welcome back", level: 1 })).toBeVisible();

    const username = page.getByLabel("Username");
    const password = page.getByRole("textbox", { name: "Password" });
    const passwordToggle = page.getByRole("button", { name: "Show password" });

    await expect(username).toBeFocused();
    await expect(username).toHaveAttribute("autocomplete", "username");
    await expect(password).toHaveAttribute("autocomplete", "current-password");
    await expect(password).toHaveAttribute("type", "password");

    await passwordToggle.focus();
    await expect(passwordToggle).toBeFocused();
    await passwordToggle.press("Enter");
    await expect(password).toHaveAttribute("type", "text");
    await expect(page.getByRole("button", { name: "Hide password" })).toBeVisible();

    await expectNoBasicSemanticViolations(page);
    await expectNoSeriousOrCriticalAxeViolations(page, "main");

    await expect(page.getByRole("link", { name: "Forgot password?" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
      .toBeTruthy();
  });
});
