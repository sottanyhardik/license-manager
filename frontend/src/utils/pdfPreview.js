/**
 * Opens a PDF blob in a new tab with a meaningful tab title (so the user can
 * tell which document they're previewing — license number, allotment number,
 * invoice number, etc.) instead of the opaque blob UUID Chrome shows by default.
 *
 * @param {Blob|ArrayBuffer} data - PDF bytes or an existing Blob.
 * @param {string} filename - Display name shown in the tab and as the
 *   default name for the in-viewer download button. ".pdf" is appended if
 *   missing.
 * @returns {Window|null} The opened window, or null if the popup was blocked.
 */
export function openPdfPreview(data, filename) {
    const blob = data instanceof Blob ? data : new Blob([data], { type: 'application/pdf' });
    const url = window.URL.createObjectURL(blob);

    const safeName = sanitizeFilename(filename);
    const win = window.open('', '_blank');

    if (!win) {
        window.URL.revokeObjectURL(url);
        return null;
    }

    // Write a tiny wrapper page that owns the blob URL, sets the title, and
    // provides a Download button whose href carries the meaningful filename.
    // The browser's in-viewer download button will still use the blob UUID,
    // but the floating Download button below uses the proper name.
    win.document.open();
    win.document.write(`<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>${escapeHtml(safeName)}</title>
<style>
  html, body { margin: 0; padding: 0; height: 100%; background: #525659; }
  embed, iframe { width: 100%; height: 100%; border: none; display: block; }
  .dl { position: fixed; top: 12px; right: 12px; z-index: 9999;
        background: #2563eb; color: #fff; text-decoration: none;
        padding: 8px 14px; border-radius: 6px; font-family: system-ui, sans-serif;
        font-size: 14px; font-weight: 500; box-shadow: 0 2px 8px rgba(0,0,0,.3); }
  .dl:hover { background: #1d4ed8; }
</style>
</head>
<body>
<a class="dl" href="${url}" download="${escapeHtml(safeName)}">⬇ Download</a>
<embed src="${url}" type="application/pdf">
</body>
</html>`);
    win.document.close();

    // Revoke when the wrapper tab unloads so we don't leak per-preview.
    win.addEventListener('unload', () => window.URL.revokeObjectURL(url));

    return win;
}

function sanitizeFilename(name) {
    const base = (name || 'document').toString().trim().replace(/[\\/:*?"<>|]+/g, '_');
    return /\.pdf$/i.test(base) ? base : `${base}.pdf`;
}

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
