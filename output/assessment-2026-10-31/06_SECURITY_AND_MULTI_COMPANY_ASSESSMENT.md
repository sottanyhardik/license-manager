# Security and multi-company assessment

Authentication and JWT/role protections exist; sampled unauthenticated endpoints returned 401. That does not prove company isolation. Static evidence indicates global role-oriented access and materially unscoped query paths, making isolation a P0 condition for external SaaS and P1 for internal multi-entity operations.

Required: tenant/membership separate from legal entity/counterparty; mandatory scoped repository/query boundary; direct-ID/export/background-job negative tests; company-scoped financial/audit events; least privilege; signed protected documents; audit logs for high-impact changes; staging secrets/CORS/backup/restore/monitoring verification. No exploit or unauthorised testing was performed.
