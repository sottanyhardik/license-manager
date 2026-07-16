# PDF Preview Implementation

## Status

This guide documents the current browser-side PDF preview paths in the React
frontend. The app has two supported preview mechanisms:

1. `frontend/src/pages/PDFViewer.tsx`
   - Dedicated protected route: `/pdf-viewer?url=<api-path>`
   - Fetches a PDF endpoint with the shared Axios client.
   - Displays the returned PDF blob in a full-screen iframe.
   - Browser refresh or the floating refresh button regenerates the PDF from
     the same API path.

2. `frontend/src/utils/pdfPreview.js`
   - Opens an already-fetched PDF blob in a new tab.
   - Writes a small wrapper page with an embedded PDF and a named Download
     button.
   - Used by several master-list and document preview actions where the caller
     already has the PDF bytes.

## Current Files

- `frontend/src/pages/PDFViewer.tsx`
- `frontend/src/routes/AppRoutes.tsx`
- `frontend/src/utils/pdfPreview.js`
- PDF callers include:
  - `frontend/src/pages/masters/MasterList.tsx`
  - `frontend/src/components/LicenseBalanceModal.tsx`
  - `frontend/src/pages/AllotmentAction.tsx`
  - `frontend/src/pages/masters/tables/AllotmentsTable.tsx`

## Dedicated Route Flow

`PDFViewer.tsx` is lazy-loaded from `AppRoutes.tsx` and wrapped in
`ProtectedRoute`.

```tsx
<Route path="/pdf-viewer" element={
    <ProtectedRoute>
        <PDFViewer />
    </ProtectedRoute>
} />
```

The viewer expects a `url` query parameter containing a relative backend API
path.

```ts
const apiUrl = searchParams.get("url");
const response = await api.get(apiUrl, { responseType: "blob" });
const blob = new Blob([response.data], { type: "application/pdf" });
const url = window.URL.createObjectURL(blob);
setPdfUrl(url);
```

The generated blob URL is revoked when the component unmounts.

## Blob Preview Flow

`openPdfPreview(data, filename)` is used when a caller has already fetched PDF
bytes.

```js
const response = await api.get(apiPath, {
    params,
    responseType: "blob",
});

const opened = openPdfPreview(
    response.data,
    `${entityName}_${new Date().toISOString().split("T")[0]}.pdf`,
);
```

The helper:

- Creates a PDF blob when needed.
- Opens a blank tab.
- Writes a minimal wrapper page.
- Escapes the title and download filename.
- Adds a download link using the sanitized filename.
- Revokes the blob URL when the wrapper tab unloads.

## Validation And Error Handling

`PDFViewer.tsx` handles:

- Missing `url` query parameter.
- HTTP 404 with "PDF endpoint not found".
- HTTP 401 with an authentication error message.
- HTTP 500 with a server-generation error message.
- Network failures with a retry message.
- Generic Axios errors.

The route uses the project Axios client, so authentication headers and token
refresh behavior are inherited from `frontend/src/api/axios.js`.

## Security Notes

- `/pdf-viewer` is protected by `ProtectedRoute`.
- `PDFViewer.tsx` normalizes the `url` query parameter and rejects empty,
  absolute, protocol-relative, backslash-containing, and control-character
  values before making an Axios request.
- The viewer should be used with relative backend API paths resolved by the
  shared Axios base URL.
- `openPdfPreview()` escapes HTML before writing the tab title, download label,
  and download filename.
- Blob URLs are revoked after use to reduce memory lifetime.

## UX Behavior

Dedicated route:

- Shows a loading state while the PDF is generated.
- Shows an error panel with a retry button on failure.
- Uses a full-screen iframe for the PDF.
- Provides a floating refresh button.

Blob preview helper:

- Uses the browser's native PDF renderer.
- Gives the preview tab a meaningful title.
- Provides a named Download button.
- Returns `null` when the popup is blocked so callers can show a toast.

## Browser Behavior

PDF rendering is delegated to the browser:

- Chrome and Edge use the built-in PDF viewer.
- Firefox uses PDF.js.
- Safari uses native PDF rendering.
- Mobile browsers may hand off to the system PDF viewer.

## Adding A New PDF Preview

Use `/pdf-viewer` when the endpoint can be represented as a stable relative API
path that should regenerate on refresh.

```ts
const viewerUrl = `/pdf-viewer?url=${encodeURIComponent("reports/example.pdf/")}`;
window.open(viewerUrl, "_blank", "noopener");
```

Use `openPdfPreview()` when the component already fetched a blob or needs a
custom filename for the preview tab and download button.

```ts
const response = await api.get("reports/example.pdf/", { responseType: "blob" });
const opened = openPdfPreview(response.data, "example-report.pdf");
if (!opened) {
    toast.error("Pop-up blocked. Allow pop-ups for this site to view the PDF.");
}
```

## Audit Notes

- The earlier guide referenced obsolete files such as `PDFViewer.jsx`,
  `App.jsx`, and `LicenseLedger.jsx`; the current frontend uses TypeScript
  route/component files.
- The License Ledger page currently generates some ledger PDFs client-side with
  `frontend/src/utils/ledgerExport.js`; it is not solely backed by the
  `/pdf-viewer` route.
- `PDFViewer.tsx` URL validation is covered by `frontend/src/pages/PDFViewer.test.tsx`.
