# Routes, APIs and integrations - current evidence

Local authenticated read-only rendering was observed for Dashboard, Licences, SION Planning, Allotments, BOEs, Trades, Reconciliation and Reconciliation Issues. Browser coverage was partial; mutation workflows were not executed against shared data. Direct `/admin/users` resolved to Django admin login rather than the expected SPA administration route, a P1 route-ownership investigation.

Root, health and schema endpoints responded locally; sampled unauthenticated business endpoints required authentication. Exact endpoint inventory, serializer/service path, authentication matrix and integration contracts are pending source-index-supported inventory.

Master-data integration is documented as existing; its current contracts, failure behaviour, credentials and production configuration are NOT_ASSESSED.

