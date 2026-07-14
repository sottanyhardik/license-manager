# License Manager

A production trade-compliance system for managing DGFT import/export licenses
(DFIA, incentive licenses), pre-auth allotments, Bills of Entry (BOE), trade
invoices, and duty calculations. The system enforces SION norms, tracks license
balances and ledger events, generates regulatory PDFs, and supports 12 RBAC
roles across multiple company/port configurations.

---

## Repository layout

```
license-manager/
├── backend/            # New Django 6.x application (port 8001)
├── frontend/           # New React 19 SPA (port 5173)
├── legacy/             # Read-only reference — do not modify
├── docs/
│   ├── knowledge-graph/   # Living architecture + module docs
│   ├── adr/               # Architecture decision records
│   └── api-contract/      # legacy-v1.yaml — full legacy API contract
├── master-data-service/   # Standalone master-data sync service
├── mds-client/            # Client package for master-data-service
├── scripts/               # Utility scripts
├── docker-compose.yml
└── auto-deploy.sh         # Production deploy to all servers
```

---

## Quick start (local dev)

### Prerequisites

- Docker + Docker Compose
- Python 3.13 + [uv](https://docs.astral.sh/uv/) (local backend only)
- Node 22 + npm (local frontend only)

### With Docker (recommended)

```bash
cp .env.example .env          # edit DB_PASSWORD and SECRET_KEY if desired
docker compose up
```

| Service   | URL                               |
|-----------|-----------------------------------|
| Backend   | http://localhost:8001/api/health/ |
| Frontend  | http://localhost:5173             |
| API docs  | http://localhost:8001/api/docs/   |
| Mailpit   | http://localhost:8025             |

### Without Docker

```bash
# Backend
cd backend
uv venv && source .venv/bin/activate
uv pip install -r requirements/dev.txt
python manage.py migrate
python manage.py runserver 8001

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## Architecture

The rebuild uses a **hybrid parallel-run** strategy (ADR-001):

- `legacy/` serves live production traffic on port 8000 and is read-only.
- `backend/` + `frontend/` are the new codebase, built module by module
  against the same PostgreSQL database.
- nginx routes `/api/v1/*` to the new backend (8001) and all other traffic to
  legacy (8000) until the production cutover gate (ADR-009) is met.
- No data migration is required at cutover — both apps share a single database
  with additive-only schema changes (ADR-002).

Full detail: [docs/knowledge-graph/architecture.md](docs/knowledge-graph/architecture.md)

---

## Tech stack

| Layer      | Technology                                          |
|------------|-----------------------------------------------------|
| Backend    | Python 3.13 / Django 6.x / Django REST Framework    |
| Task queue | Celery 5 / Redis 7                                  |
| Database   | PostgreSQL 16                                       |
| Frontend   | React 19 / TypeScript 5 / Vite 6                    |
| UI         | Tailwind CSS v4 / shadcn (Radix UI primitives)      |
| Data fetch | TanStack Query v5 / Axios                           |
| Forms      | React Hook Form / Zod                               |
| Tables     | TanStack Table v8                                   |
| Email dev  | Mailpit                                             |

---

## Key docs

| Path | Contents |
|------|----------|
| `docs/knowledge-graph/architecture.md` | System topology, routing, key ADRs |
| `docs/knowledge-graph/modules.md` | Per-module status, tables, services, APIs |
| `docs/adr/` | Architecture decision records (ADR-001 through ADR-010) |
| `docs/api-contract/legacy-v1.yaml` | Full legacy API contract (reference) |
| `legacy/README.md` | Legacy system documentation |

---

## Development workflow

- Branch from `develop`; open PRs back to `develop`.
- `develop` merges to `master` on release.
- `feature/V1` is the active rebuild branch.
- `legacy/` is read-only — no commits to files under that directory.

---

## Backend commands

```bash
uv run pytest                           # run test suite
uv run ruff check .                     # lint (ruff E/F/I/N/UP)
uv run python manage.py migrate         # apply migrations
uv run celery -A config worker -l info  # start Celery worker
```

---

## Frontend commands

```bash
npm run dev        # dev server (Vite, port 5173)
npm run build      # production build (tsc + vite)
npm run typecheck  # TypeScript check (tsc --noEmit)
npm run lint       # ESLint (zero warnings policy)
```

---

## Production deploy

```bash
export DEPLOY_PASSWORD=...
./auto-deploy.sh master                   # deploy to all servers
./auto-deploy.sh master 165.232.185.220   # deploy to one server
```

Requires `sshpass` (`brew install sshpass` / `sudo apt install sshpass`).
See the script header for MDS sync and SSL cert automation details.

---

## Legacy app

The original application lives in `legacy/` and continues to serve production
traffic. It must not be modified under any circumstances (ADR-010). Consult
it as a ground-truth reference for business rules when reimplementing a module.
See [legacy/README.md](legacy/README.md) for its own documentation.
