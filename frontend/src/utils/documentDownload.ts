/**
 * Authenticated document/download helpers.
 *
 * Browser-native ways of opening a file — `<a href>`, `<img src>`, `window.open`,
 * `?access_token=` query params — either can't send an `Authorization` header or
 * leak the JWT into logs/history. These helpers instead fetch the file through the
 * shared axios instance (which attaches `Authorization: Bearer <access>` on every
 * request, see api/axios.ts) as a Blob, then hand the browser a short-lived
 * object URL. Use them to replace:
 *   - direct `/media/...` links to uploaded documents, and
 *   - `?access_token=`-style links to export endpoints (balance-excel/pdf, etc.).
 *
 * See docs/media-security-cutover.md for the full migration + activation runbook.
 */
import api from "../api/axios";

const ABSOLUTE_OR_PROTOCOL_RELATIVE_URL = /^(?:[a-z][a-z\d+.-]*:)?\/\//i;

function hasUnsafePathCharacters(path: string): boolean {
  return [...path].some((char) => {
    const code = char.charCodeAt(0);
    return char === "\\" || code < 32 || code === 127;
  });
}

export function normalizeAuthedFilePath(path: string): string {
  const normalized = String(path ?? "").trim();

  if (!normalized) {
    throw new Error("Authenticated file path is required.");
  }
  if (ABSOLUTE_OR_PROTOCOL_RELATIVE_URL.test(normalized)) {
    throw new Error("Authenticated file path must be relative to the API origin.");
  }
  if (hasUnsafePathCharacters(normalized)) {
    throw new Error("Authenticated file path contains unsafe characters.");
  }

  return normalized;
}

/**
 * Normalize a stored file URL/path to the authenticated media endpoint path,
 * relative to the axios baseURL (which is the `/api` prefix).
 * Accepts "/media/foo/bar.pdf", "media/foo/bar.pdf" or "foo/bar.pdf".
 */
export function toProtectedMediaPath(fileUrlOrPath: string): string {
  const value = String(fileUrlOrPath ?? "").trim();
  const path = value
    .replace(/^(?:https?:)?\/\/[^/]+/i, "")
    .replace(/^\/?media\//, "")
    .replace(/^\/+/, "");

  if (!path || hasUnsafePathCharacters(path)) {
    throw new Error("Protected media path is required.");
  }

  return `/media/${path}`;
}

/**
 * Fetch a protected file with the auth header and either trigger a download
 * (when `filename` is given) or open it in a new tab. `path` is relative to the
 * axios baseURL, e.g. "/media/licenses/123/copy.pdf" or
 * "/licenses/123/balance-excel/".
 */
export async function openAuthedFile(path: string, filename?: string): Promise<void> {
  const safePath = normalizeAuthedFilePath(path);
  const res = await api.get(safePath, { responseType: "blob" });
  const blobUrl = URL.createObjectURL(res.data as Blob);
  try {
    if (filename) {
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } else {
      window.open(blobUrl, "_blank", "noopener");
    }
  } finally {
    // Revoke after a delay so the new tab/download has time to read it.
    setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
  }
}

/** Convenience: open an uploaded document (stored `.file` URL) authenticated. */
export function openDocument(fileUrlOrPath: string, filename?: string): Promise<void> {
  return openAuthedFile(toProtectedMediaPath(fileUrlOrPath), filename);
}
