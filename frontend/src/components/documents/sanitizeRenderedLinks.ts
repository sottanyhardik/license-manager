const SAFE_HREF = /^(?:https?:|mailto:|#)/i;

/**
 * Neutralise links rendered from an uploaded document: only http(s), mailto and
 * in-document anchors keep their href (no `javascript:`/`data:`/`file:`), and
 * external links open in a new tab without `window.opener`.
 */
export function sanitizeRenderedLinks(root: HTMLElement): void {
    root.querySelectorAll("a[href]").forEach(anchor => {
        const href = (anchor.getAttribute("href") ?? "").trim();
        if (!SAFE_HREF.test(href)) {
            anchor.removeAttribute("href");
            return;
        }
        if (!href.startsWith("#")) {
            anchor.setAttribute("target", "_blank");
            anchor.setAttribute("rel", "noopener noreferrer");
        }
    });
}
