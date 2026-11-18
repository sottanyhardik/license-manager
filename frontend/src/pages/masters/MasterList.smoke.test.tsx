import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext } from "../../context/AuthContext";

// Minimal metadata shape the list view expects from the API.
const META = {
  results: [],
  list_display: ["name"],
  form_fields: [],
  search_fields: ["name"],
  filter_fields: [],
  filter_config: {},
  ordering_fields: [],
  nested_field_defs: {},
  nested_list_display: {},
  field_meta: {},
  default_filters: {},
  inline_editable: [],
  current_page: 1,
  total_pages: 1,
  page_size: 25,
  has_next: false,
  has_previous: false,
};

// Mock the shared axios instance: every GET resolves the empty-but-valid metadata.
vi.mock("../../api/axios", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: META })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// Mock the dedicated API services (only boeApi is used, for bill-of-entries).
vi.mock("../../api", () => ({
  boeApi: {
    fetchBOEList: vi.fn(() => Promise.resolve(META)),
    exportBOEPortExcel: vi.fn(() => Promise.resolve(new Blob())),
  },
  masterApi: {},
  licenseApi: {},
  allotmentApi: {},
}));

// Spy on the dangerous-action confirmation (resolves "confirmed"); the rest of the hook stays real.
const { confirmSpy } = vi.hoisted(() => ({ confirmSpy: vi.fn(() => Promise.resolve(true)) }));
vi.mock("../../hooks/useConfirmDialog.jsx", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../hooks/useConfirmDialog")>();
  return {
    ...actual,
    useConfirmDialog: () => ({ ...actual.useConfirmDialog(), confirmDangerousAction: confirmSpy }),
  };
});

import MasterList from "./MasterList";
import api from "../../api/axios";
import { boeApi } from "../../api";

const authValue = {
  user: { id: 1, username: "t", is_superuser: true, roles: [] },
  loading: false,
  loginSuccess: vi.fn(),
  logout: vi.fn(),
  hasRole: () => true,
  hasAnyRole: () => true,
  isSuperAdmin: () => true,
  canManageUsers: () => true,
};

function renderAt(entity: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={authValue as never}>
        <MemoryRouter initialEntries={[`/masters/${entity}`]}>
          <Routes>
            <Route path="/masters/:entity/:id?" element={<MasterList />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

describe("MasterList smoke", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders a master entity without crashing and finishes loading", async () => {
    const { container } = renderAt("companies");
    // Renders something and settles (loading spinner clears) without throwing.
    await waitFor(() => expect(container).not.toBeEmptyDOMElement());
  });

  it("renders generic master rows with their data (gates GenericMasterCards extraction)", async () => {
    (api.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: {
        ...META,
        results: [
          {
            id: 11,
            name: "Acme Trading",
          },
        ],
      },
    });
    renderAt("companies");
    expect(await screen.findByText("Acme Trading")).toBeInTheDocument();
  });

  it("passes the backend's bulk_actions to the generic master rows and posts one bulk request", async () => {
    const user = userEvent.setup();
    (api.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { ...META, list_display: ["code", "name"], bulk_actions: ["delete"], results: [{ id: 11, code: "INAAA1", name: "Port A" }] },
    });
    (api.post as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: { action: "delete", requested: 1, succeeded: 1, failed: 0, results: [{ key: "11", ok: true }] },
    });
    const confirmSpyWindow = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderAt("ports");
    await user.click(await screen.findByRole("checkbox", { name: "Select all on page" }));
    await user.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("masters/ports/bulk/", { action: "delete", keys: ["11"] }));
    expect(await screen.findByTestId("bulk-results")).toHaveTextContent("1 of 1 deleted");
    confirmSpyWindow.mockRestore();
    (api.get as unknown as ReturnType<typeof vi.fn>).mockImplementation(() => Promise.resolve({ data: META }));
  });

  it("uses the generic rows for field-definition lists and for configured child collections (SION classes)", async () => {
    const rate = { id: 1, date: "2026-11-01", usd: "84.10", euro: "91.20", pound_sterling: "107.00", chinese_yuan: "11.60", is_active: true };
    (api.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { ...META, list_display: ["date", "usd", "is_active"], nested_field_defs: [{ field: "is_active", label: "Active", type: "boolean" }], results: [rate] },
    });
    const first = renderAt("exchange-rates");
    expect(await screen.findByRole("list", { name: "Exchange Rates" })).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    first.unmount();

    const sion = { id: 2, norm_class: "A3627", description: "Biscuits", export_norm: [{ id: 9, description: "BISCUITS", quantity: "1.000", unit: "kg" }], import_norm: [], notes: [], conditions: [] };
    const sionList = { ...META, list_display: ["norm_class"], nested_field_defs: { export_norm: [{ name: "description" }] }, results: [sion] };
    (api.get as unknown as ReturnType<typeof vi.fn>).mockImplementation((url: string) =>
      Promise.resolve({ data: url === "masters/sion-classes/2/" ? sion : sionList }));
    renderAt("sion-classes");
    const list = await screen.findByRole("list", { name: /sion classes/i });
    expect(within(list).getByRole("link", { name: "A3627" })).toBeInTheDocument();
    fireEvent.click(within(list).getByRole("button", { name: "Expand A3627" }));
    // The row opens the full record inline; child norms are its Related records.
    await userEvent.setup().click(await screen.findByRole("tab", { name: /Related records/ }));
    const exportItems = await screen.findByRole("region", { name: "Export items" });
    expect(within(exportItems).getByText("BISCUITS")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Import items" })).not.toBeInTheDocument();
    (api.get as unknown as ReturnType<typeof vi.fn>).mockImplementation(() => Promise.resolve({ data: META }));
  });

  it("renders the licenses entity without crashing", async () => {
    const { container } = renderAt("licenses");
    await waitFor(() => expect(container).not.toBeEmptyDOMElement());
  });

  it("renders incentive-licenses rows with their data (gates EntityTable extraction)", async () => {
    (api.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: {
        ...META,
        results: [
          {
            id: 7,
            license_number: "INC-TEST-777",
            license_type: "RODTEP",
            license_value: 100000,
            sold_value: 0,
            balance_value: 100000,
            sold_status: "NO",
            is_active: true,
          },
        ],
      },
    });
    renderAt("incentive-licenses");
    // The row must render its identifying content.
    expect(await screen.findByText("INC-TEST-777")).toBeInTheDocument();
    expect(screen.getByText("RODTEP")).toBeInTheDocument();
  });

  it("renders allotments rows with their data (gates EntityTable extraction)", async () => {
    (api.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: {
        ...META,
        results: [
          {
            id: 3,
            invoice: "INV-ALLOT-3",
            item_name: "Crude Palm Oil",
            is_boe: false,
            is_approved: true,
            required_quantity: 1000,
            allotment_details: [],
          },
        ],
      },
    });
    renderAt("allotments");
    expect(await screen.findByText("INV-ALLOT-3")).toBeInTheDocument();
    expect(screen.getByText("Crude Palm Oil")).toBeInTheDocument();
  });

  it("exposes the established Company, Port, and BOE selectors on allotments", async () => {
    (api.get as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: {
        ...META,
        filter_config: {
          company: { type: "fk", fk_endpoint: "/masters/companies/", label_field: "name" },
          port: { type: "fk", fk_endpoint: "/masters/ports/", label_field: "name" },
          is_boe: { type: "exact", label: "BOE" },
        },
      },
    });

    renderAt("allotments");

    // Compact register: the filter panel is closed by default and opens on demand.
    await userEvent.click(await screen.findByRole("button", { name: /^Filters/ }));
    expect(await screen.findByText("Company")).toBeInTheDocument();
    expect(screen.getByText("Port")).toBeInTheDocument();
    expect(screen.getByText("BOE")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yes" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "No" })).toBeInTheDocument();
  });

  describe("bill-of-entries register actions", () => {
    it("links Add New to the BOE create route", async () => {
      renderAt("bill-of-entries");
      const addNew = await screen.findByRole("link", { name: /Add New/ });
      expect(addNew).toHaveAttribute("href", "/bill-of-entries/create");
    });

    it("keeps Excel/PDF as buttons and moves Port-wise Excel into the action menu", async () => {
      const user = userEvent.setup();
      renderAt("bill-of-entries");
      expect(await screen.findByRole("button", { name: "Export to Excel" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Export to PDF" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /port-wise BOE Excel/i })).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "More bill of entry actions" }));
      await user.click(await screen.findByRole("menuitem", { name: "Port-wise Excel" }));
      await waitFor(() => expect(boeApi.exportBOEPortExcel).toHaveBeenCalledTimes(1));
    });

    it("confirms before bulk-updating empty product names", async () => {
      const user = userEvent.setup();
      const post = api.post as unknown as ReturnType<typeof vi.fn>;
      post.mockResolvedValueOnce({ data: { success: true, message: "done" } });
      renderAt("bill-of-entries");

      await user.click(await screen.findByRole("button", { name: "More bill of entry actions" }));
      const menu = await screen.findByRole("menu");
      await user.click(within(menu).getByRole("menuitem", { name: "Update all empty product names" }));

      await waitFor(() => expect(post).toHaveBeenCalledWith("bill-of-entries/bulk-update-product-names/"));
      expect(confirmSpy).toHaveBeenCalledWith("Bulk Update Product Names", expect.stringContaining("empty product_name"));
      expect(confirmSpy.mock.invocationCallOrder[0]).toBeLessThan(post.mock.invocationCallOrder[0]);
    });

    it("does not post the bulk update when the confirmation is declined", async () => {
      const user = userEvent.setup();
      confirmSpy.mockResolvedValueOnce(false);
      renderAt("bill-of-entries");

      await user.click(await screen.findByRole("button", { name: "More bill of entry actions" }));
      await user.click(await screen.findByRole("menuitem", { name: "Update all empty product names" }));

      await waitFor(() => expect(confirmSpy).toHaveBeenCalledTimes(1));
      expect(api.post).not.toHaveBeenCalled();
    });
  });
});
