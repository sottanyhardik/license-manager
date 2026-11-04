/**
 * Regression test for savedDraft TDZ error fix.
 *
 * This test verifies that LicensePlanningWorkspace renders without
 * a "Cannot access 'savedDraft' before initialization" ReferenceError.
 *
 * The error occurred when savedDraft was declared after the useEffect
 * that referenced it in its dependency array.
 */

import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LicensePlanningWorkspace from "./LicensePlanningWorkspace";

const withQueryClient = (node: React.ReactNode) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>;

describe("LicensePlanningWorkspace TDZ Regression", () => {
  it("should render without ReferenceError on savedDraft", () => {
    // This test passes if no ReferenceError is thrown during render
    expect(() => {
      render(withQueryClient(
        <MemoryRouter initialEntries={["/planning?sion=E126"]}>
          <LicensePlanningWorkspace />
        </MemoryRouter>
      ));
    }).not.toThrow("Cannot access 'savedDraft' before initialization");
  });

  it("should render the component structure without TDZ error", () => {
    const { container } = render(withQueryClient(
      <MemoryRouter initialEntries={["/planning?sion=E126"]}>
        <LicensePlanningWorkspace />
      </MemoryRouter>
    ));

    // If we get here without throwing, the TDZ error is fixed
    expect(container).toBeTruthy();
  });
});
