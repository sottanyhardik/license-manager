import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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
vi.mock("../../services/api", () => ({
  boeApi: { fetchBOEList: vi.fn(() => Promise.resolve(META)) },
  masterApi: {},
  licenseApi: {},
  allotmentApi: {},
}));

import MasterList from "./MasterList";
import api from "../../api/axios";

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
            <Route path="/masters/:entity" element={<MasterList />} />
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
});
