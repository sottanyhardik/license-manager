# API Graph

> Living document. Each row is added when the endpoint is implemented in `backend/`.
> Legacy endpoints live at `/api/*`. New endpoints live at `/api/v1/*`.

## Endpoint Parity Tracker

| New Endpoint | Legacy Equivalent | Auth | Method | Status |
|---|---|---|---|---|
| /api/v1/auth/login/ | /api/auth/login/ | none | POST | pending |
| /api/v1/auth/logout/ | /api/auth/logout/ | JWT | POST | pending |
| /api/v1/auth/refresh/ | /api/auth/token/refresh/ | none | POST | pending |
| /api/v1/licenses/ | /api/licenses/ | JWT+role | GET, POST | pending |
| /api/v1/licenses/:id/ | /api/licenses/:id/ | JWT+role | GET, PATCH, DELETE | pending |
| ... | ... | ... | ... | pending |

> Full legacy contract: `docs/api-contract/legacy-v1.yaml`

## API Response Envelope

All `/api/v1/` responses use:

```json
{
  "success": true,
  "data": {},
  "message": null
}
```

```json
{
  "success": false,
  "data": null,
  "errors": [{"field": "...", "message": "..."}],
  "message": "Validation failed"
}
```

## URL Routing (nginx)

```
/api/v1/*   → backend/ (new Django app, port 8001)
/api/*      → legacy/backend/ (existing, port 8000)
/           → frontend/ dist (new React app)
```
