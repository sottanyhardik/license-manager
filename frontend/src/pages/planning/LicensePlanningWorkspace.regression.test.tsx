/**
 * Regression test for savedDraft TDZ error fix.
 *
 * This test verifies that LicensePlanningWorkspace renders without
 * a "Cannot access 'savedDraft' before initialization" ReferenceError.
 *
 * The error occurred when savedDraft was declared after the useEffect
 * that referenced it in its dependency array.
 */

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import LicensePlanningWorkspace from "./LicensePlanningWorkspace";

describe("LicensePlanningWorkspace TDZ Regression", () => {
  it("should render without ReferenceError on savedDraft", () => {
    // This test passes if no ReferenceError is thrown during render
    expect(() => {
      render(
        <MemoryRouter initialEntries={["/planning?sion=E126"]}>
          <LicensePlanningWorkspace />
        </MemoryRouter>
      );
    }).not.toThrow("Cannot access 'savedDraft' before initialization");
  });

  it("should render the component structure without TDZ error", () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/planning?sion=E126"]}>
        <LicensePlanningWorkspace />
      </MemoryRouter>
    );

    // If we get here without throwing, the TDZ error is fixed
    expect(container).toBeTruthy();
  });
});
