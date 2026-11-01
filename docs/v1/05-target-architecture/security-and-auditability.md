# Security and auditability

## Verified current controls

Default API authentication, role permissions, JWT rotation/blacklisting/revocation checks, production settings validation, rate limits, restrictive CORS and scoped query-token handling are implemented. Query-string bearer tokens are accepted only for GET/HEAD download-like paths as compatibility. Permissions are central and high blast radius; ledger writes deny unknown actions by default.

## Risks and V1 controls

| Priority | Risk | V1 closure |
| --- | --- | --- |
| P0 | Company/object isolation is not demonstrated end-to-end; current tests intentionally allow documented roles to read multiple companies. | Owner-approved policy, then query/mutation/download/export scope tests matching that policy. |
| P1 | Query-string download credentials may leak via history/logs/referrers. | Complete protected-media migration, inventory consumers, remove compatibility only after contract confirmation. |
| P1 | Client-side localStorage JWT increases XSS exposure. | Approve CSP/XSS posture or cookie migration, with CSRF/UX test plan. |
| P2 | Asynchronous daemon audit logging may lose events on termination. | Specify audit durability; durable queue/outbox if compliance requires it. |

No existing authorization behavior is changed by this specification. All access paths—API, downloads, exports, jobs and direct lookups—need a role/object-scope matrix.
