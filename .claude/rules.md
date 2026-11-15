# Rules index (kept for agents that reference `.claude/rules.md`)

Rules moved to `.claude/rules/` on 2026-11-15 (original: `.claude/backups/2026-11-15-pre-ecc/rules.md`).

| File | Scope |
|---|---|
| `rules/business-rules.md` | CIF/balance/reconciliation protection — backend domain apps |
| `rules/backend.md` | Django/DRF conventions + backend gates — `backend/**`, MDS, mds-client |
| `rules/frontend.md` | React/Tailwind/shadcn stack + frontend gates — `frontend/**` |
| `rules/safety.md` | Autonomy boundaries (always loaded) |
| `rules/documentation-mode.md` | docs/ generation spec — `docs/**` |
| `rules/ecc/**` | Vendored ECC language rules (lower precedence than the above) |

Quality gates for every area: `scripts/dev/quality-gate.sh` (mirrors `.github/workflows/ci.yml`).
