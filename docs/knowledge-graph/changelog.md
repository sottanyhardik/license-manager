# Changelog

> Living document. One entry per completed phase or significant change.
> Format: ## [Phase/Date] — Summary followed by bullet list of changes.

---

## [Phase 0] — Foundation (feature/V1)

### Repository
- Moved `backend/` → `legacy/backend/` (read-only reference)
- Moved `frontend/` → `legacy/frontend/` (read-only reference)
- Created `legacy/README.md` (read-only rule)
- Scaffolded `backend/` (new Django app, empty)
- Scaffolded `frontend/` (new React app, empty)
- Updated `auto-deploy.sh` to reference `legacy/backend/` and `legacy/frontend/`

### Documentation
- Created `docs/adr/` — 10 ADRs (see `docs/knowledge-graph/decisions.md`)
- Created `docs/knowledge-graph/` — 8 living documents scaffolded
- Updated `docs/05-database.md` — full ER diagram, 42-model table inventory, signal map, cascade register

### Tooling (pending)
- `backend/` Django scaffold (P0.5) — in progress
- `frontend/` React scaffold (P0.6) — in progress
- Docker Compose (P0.7) — pending
- GitHub Actions CI/CD (P0.8) — pending
- Pre-commit hooks (P0.9) — pending

---

## [Hotfixes on master — pre-Phase-0]

- `fix(backend/pdf)`: billing % (pct/rate_pct) precision — 3 decimal places enforced in compute_amount(), PDF formatters, TradeForm placeholder
- `fix(deploy)`: health check uses HTTPS domain instead of raw IP (was returning 301 on HTTP)
