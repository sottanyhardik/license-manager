# Legacy Application

Read-only reference. Do not modify.

This directory contains the original License Manager application, frozen at the
point of Phase 0 restructure (2026-07-14).

## Contents

- `legacy/backend/` — Django backend (Python 3.x, DRF, lmanagement project)
- `legacy/frontend/` — React 18 SPA (Vite, TypeScript, Tailwind v3)

## Rules

- **No commits to `legacy/`** except emergency hotfixes with engineering lead sign-off.
- Emergency hotfixes require a ticket explaining why `backendv1` could not absorb the change,
  and the same fix must be applied to `backendv1` within 5 business days.
- See `docs/adr/ADR-010-legacy-readonly.md` for the full policy.

## Running the legacy app

The legacy app still deploys via `auto-deploy.sh` and runs in production.
The remote servers have the app at `$SERVER_PATH/legacy/backend` and
`$SERVER_PATH/legacy/frontend` after the restructure.

For local development of the legacy app:

```bash
cd legacy/backend
source ../../venv/bin/activate   # or create one: python3 -m venv ../../venv
pip install -r requirements.txt
python manage.py check
python manage.py runserver
```
