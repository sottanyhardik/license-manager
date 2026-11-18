import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthContext } from "../../context/AuthContext";
import { sanitizeRenderedLinks } from "@/components/documents/sanitizeRenderedLinks";
import MasterRecordPanel from "./MasterRecordPanel";

const { getSpy, renderAsync } = vi.hoisted(() => ({ getSpy: vi.fn(), renderAsync: vi.fn() }));
vi.mock("../../api/axios", () => ({ default: { get: getSpy, delete: vi.fn() } }));
vi.mock("@/api/axios", () => ({ default: { get: getSpy, delete: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("docx-preview", () => ({ renderAsync }));

const TL_META = { list_display: ["name"], form_fields: ["name", "tl"] };
const TL = { id: 41, name: "LABDHI NEW", tl: "http://localhost:8000/media/tl/LABDHI_NEW.docx", created_on: "2026-01-02T03:04:05Z" };
const SION_META = { list_display: ["norm_class", "description"], form_fields: ["norm_class", "description"], nested_field_defs: { export_norm: [] } };
const SION = {
    id: 3, norm_class: "A3627", description: "Biscuits",
    export_norm: [{ id: 1, description: "BISCUITS", quantity: "1.00", unit: "kg" }],
    import_norm: [{ id: 2, serial_number: 1, description: "WHEAT FLOUR", hsn_code_label: "1101 - Flour", quantity: "0.80", unit: "kg" }],
    notes: [], conditions: [],
};

/** `/masters/<entity>/<lookup>[?tab=<id>]` → the inline panel for that record (what the list renders). */
function renderAt(path: string) {
    const [route, query = ""] = path.split("?");
    const [, , entity, lookup] = route.split("/");
    const initialTab = new URLSearchParams(query).get("tab") ?? undefined;
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const value = { isSuperAdmin: () => true, hasRole: () => true, hasAnyRole: () => true } as unknown as React.ContextType<typeof AuthContext>;
    return render(
        <QueryClientProvider client={client}>
            <AuthContext.Provider value={value}>
                <MasterRecordPanel entity={entity} lookup={decodeURIComponent(lookup)} label={`${entity} ${lookup}`} initialTab={initialTab} />
            </AuthContext.Provider>
        </QueryClientProvider>,
    );
}

function routes(file: () => Promise<unknown>) {
    getSpy.mockImplementation((url: string) => {
        if (url === "masters/transfer-letters/") return Promise.resolve({ data: TL_META });
        if (url === "masters/transfer-letters/41/") return Promise.resolve({ data: TL });
        if (url === "masters/sion-classes/") return Promise.resolve({ data: SION_META });
        if (url === "masters/sion-classes/3/") return Promise.resolve({ data: SION });
        if (url === "/media/tl/LABDHI_NEW.docx") return file();
        return Promise.reject({ response: { status: 404 } });
    });
}

describe("MasterDetail documents, accordion and related records", () => {
    beforeEach(() => {
        getSpy.mockReset();
        renderAsync.mockReset();
        sessionStorage.clear();
        renderAsync.mockImplementation(async (_blob: Blob, body: HTMLElement) => {
            body.innerHTML = `<div class="docx-wrapper"><section class="docx"><h1>TRANSFER LETTER</h1><table><tbody><tr><td>Licence No</td></tr></tbody></table><a href="javascript:alert(1)">bad</a></section><section class="docx"><p>Page two</p></section></div>`;
        });
    });

    it("Transfer Letter: the record's own .docx renders in the Document tab via the authenticated media path", async () => {
        const user = userEvent.setup();
        const blob = new Blob(["docx"], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
        routes(() => Promise.resolve({ data: blob }));
        renderAt("/masters/transfer-letters/41");

        expect(await screen.findByRole("tab", { name: "Overview", selected: true })).toBeInTheDocument();

        // Documents tab: the stored file with an authenticated download, and its rendered preview.
        await user.click(screen.getByRole("tab", { name: "Documents" }));
        expect(screen.getByRole("button", { name: "Download LABDHI_NEW.docx" })).toBeInTheDocument();
        const doc = await screen.findByRole("document", { name: "LABDHI_NEW.docx preview" });
        expect(await within(doc).findByText("TRANSFER LETTER")).toBeInTheDocument();
        expect(within(doc).getByText("Licence No")).toBeInTheDocument();
        expect(getSpy).toHaveBeenCalledWith("/media/tl/LABDHI_NEW.docx", expect.objectContaining({ responseType: "blob" }));
        expect(renderAsync).toHaveBeenCalledWith(blob, expect.any(HTMLElement), undefined, expect.objectContaining({ breakPages: true }));
        // Unsafe link from the document is neutralised.
        expect(within(doc).getByText("bad")).not.toHaveAttribute("href");
        // Pages and zoom.
        expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Zoom in" }));
        expect(screen.getByText("110%")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Download" })).toBeEnabled();

        // Details: the file is not repeated as a raw URL field (it lives in Documents).
        await user.click(screen.getByRole("tab", { name: "Details" }));
        expect(screen.getByRole("button", { name: "General information" })).toBeInTheDocument();
        expect(screen.queryByText("http://localhost:8000/media/tl/LABDHI_NEW.docx")).not.toBeInTheDocument();
    });

    it("Transfer Letter: a missing file is explained, not a blank viewer", async () => {
        const user = userEvent.setup();
        routes(() => Promise.reject({ response: { status: 404 } }));
        renderAt("/masters/transfer-letters/41?tab=document");
        // Old `?tab=document` links open the Documents tab.
        expect(await screen.findByRole("tab", { name: "Documents", selected: true })).toBeInTheDocument();
        await user.click(screen.getByRole("tab", { name: "Documents" }));
        expect(await screen.findByText("Document file is missing")).toBeInTheDocument();
        expect(renderAsync).not.toHaveBeenCalled();
    });

    it("Transfer Letter: an unreadable document shows a render error and keeps the download", async () => {
        routes(() => Promise.resolve({ data: new Blob(["not a zip"]) }));
        renderAsync.mockRejectedValueOnce(new Error("Corrupted zip"));
        renderAt("/masters/transfer-letters/41?tab=document");
        expect(await screen.findByText("Could not render this document")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Download" })).toBeEnabled();
    });

    it("SION class: child norms appear under Related records with their count", async () => {
        const user = userEvent.setup();
        routes(() => Promise.reject(new Error("unused")));
        renderAt("/masters/sion-classes/3");
        const tab = await screen.findByRole("tab", { name: /Related records/ });
        expect(tab).toHaveTextContent("2");
        await user.click(tab);
        expect(screen.getByRole("region", { name: "Export items" })).toHaveTextContent("BISCUITS");
        expect(screen.getByRole("region", { name: "Import items" })).toHaveTextContent("1101 - Flour");
        expect(screen.queryByRole("region", { name: "Notes" })).not.toBeInTheDocument();
        expect(screen.queryByRole("tab", { name: "Documents" })).not.toBeInTheDocument();
    });
});

describe("sanitizeRenderedLinks", () => {
    it("keeps http(s)/mailto/anchors and strips other schemes", () => {
        const root = document.createElement("div");
        root.innerHTML = `<a href="https://dgft.gov.in">a</a><a href="mailto:x@y.z">b</a><a href="#p2">c</a><a href=" javascript:alert(1)">d</a><a href="data:text/html,x">e</a>`;
        sanitizeRenderedLinks(root);
        const [a, b, c, d, e] = Array.from(root.querySelectorAll("a"));
        expect(a).toHaveAttribute("rel", "noopener noreferrer");
        expect(a).toHaveAttribute("target", "_blank");
        expect(b).toHaveAttribute("href", "mailto:x@y.z");
        expect(c).not.toHaveAttribute("target");
        expect(d).not.toHaveAttribute("href");
        expect(e).not.toHaveAttribute("href");
    });
});
