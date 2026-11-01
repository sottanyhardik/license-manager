# Parallel work board

Updated 2026-11-01 (new-chat session). Each workstream has one owner and one output file. Agents do not decide product questions; they recommend, and the owner decides.

| Workstream | Owner (agent or lead) | Scope (files it may read) | Output file | Status |
|---|---|---|---|---|
| WS-01 D2 formula verification | code-reviewer agent (background) | `backend/apps/license/services/balance_*.py`, `license_balance_ledger_builder.py`, `test_balance_semantics_d2_characterization.py`, `docs/v1/04-domain-and-business-rules/` | `agents/agent-06-d2-formula-verification.md` | DONE (static). Findings ISS-019 to ISS-025. Owner decision needed (Q-005, Q-016). |
| WS-02 Security verification ISS-011/012/013 | security-auditor agent (background) | `backend/apps/accounts/`, `backend/apps/core/serializers/models.py`, `backend/apps/core/views/master_view.py`, SIMPLE_JWT settings | `agents/agent-05b-security-verification.md` | IN_PROGRESS |
| WS-03 Null DFIA evidence | Lead | Licence views, signals, validation, reports, dashboard | `user-questions-register.md` (Q-001) | DONE (evidence gathered; question asked) |
| WS-04 Recovery and registers | Lead | `docs/v1/system-audit/execution/` | `new-chat-recovery-report.md`, registers | DONE (first pass) |
| WS-05 API audit (A-05) | Not started | `docs/v1/09-traceability/api-operation-register.tsv`, permissions inventory | `06-api-audit.md` | NOT_STARTED |
| WS-06 Database audit (A-06) | Not started | `docs/v1/06-data-and-migrations/current-schema.md`, `backend/apps/*/models*.py` | `07-database-audit.md` | NOT_STARTED |
| WS-07 Older decision records (R-03) | Not started | `docs/v1/execution-log.md`, `docs/v1/08-implementation/checkpoint-2026-10-31-*.md` | Append to recovery report | NOT_STARTED |
| WS-08 Frontend route audit (A-04) | Not started | `frontend/src/` routes, API clients, `docs/v1/system-audit/inventories/frontend-route-inventory.md` | `05-frontend-audit.md` | NOT_STARTED |
| WS-09 Runtime checks (ISS-011/012/017/018) | Blocked: needs owner authorisation for a disposable test database and an authorised test user | Test database only | Evidence in `evidence/test-results.md` | BLOCKED (authorisation) |
| WS-10 UI/UX screen audit (A-09) | Blocked: needs running stack and authenticated session | Browser | `10-ui-ux-audit.md` | BLOCKED (environment) |

## Blocked by user decision

- Q-001 (Null DFIA) blocks: dashboard alert wording, list default, report cut-offs, stored-flag recalculation (DEC-01 to DEC-04).
- Q-004 and Q-005 block: any D2 balance change, any Customs/Financial label change, and the balance-regression test for hidden BOEs.
- Q-002 and Q-003 block: any change to user-management or company-export permissions.

## Rules in force

- No source change without the scope amendment conditions in `CLAUDE.md`.
- No destructive git, data or production operation.
- No historical data or flag is rebuilt silently (DEC-03).
- Use the code index (`.claude/index/`) before reading source.
