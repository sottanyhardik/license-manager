import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
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
  return render(
    <AuthContext.Provider value={authValue as never}>
      <MemoryRouter initialEntries={[`/masters/${entity}`]}>
        <Routes>
          <Route path="/masters/:entity" element={<MasterList />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
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
});
