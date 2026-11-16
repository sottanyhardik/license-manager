# Baseline report — before ERP orchestration setup (2026-11-16 ~08:52 IST)

Collected read-only before any modification.

## Git

- Branch `feature/version5`, HEAD `e6dfc9b7cd74e0cdd485e90bbaa4c87e73011a31`
  ("docs(erp): record approved owner decisions, OD-06 assessment, …").
- Default branch `origin/HEAD → develop` @ `0c28a897`. HEAD is 10 commits ahead of develop, 0 behind.
  `master` @ `0df4d46d`.
- Stash: empty. Worktrees: only the main checkout.
- Branches: `develop`, `feature/version5`, `master`, `worktree-agent-a19bdca551906c320` (tip `22024f76`,
  based on `02f15724`), `worktree-agent-a72f3b374274863a8` (tip `1a9a62ec`, based on **develop** `0c28a897`).
- Staged: `D backend/.env_dgft` (OD-06: untracking the DGFT cookie file).
- Unstaged (19): `.DS_Store`, `.claude/memory/decisions.md`, `.gitignore`, `.idea/license-manager.iml`,
  `.idea/runConfigurations/Run_All__React___Beat__backend_worker_launchd_.xml` (deleted),
  `audit_evidence/pass1/BL-EXP/01/query_result`, `backend/.env.example`, `backend/apps/core/apps.py`,
  `backend/apps/core/tests/test_production_settings.py`, `backend/lmanagement/settings.py`,
  `backend/setup/Backup & Restore Script`, `backend/setup/PostgreSQL Commands`, `backend/setup/reset_lmanagement.sql`,
  `docs/erp-transformation/12-decisions-register.md`, `docs/guides/MANAGEMENT_COMMANDS.md`,
  `docs/modules/PHASE_4E_B_TEST_ENVIRONMENT_AUDIT.md`, `master-data-service/.env.production.example`,
  `scripts/database/db-tools.sh`, `scripts/diagnostics/server-health.sh`.
- Untracked (12): `backend/.env_dgft.example`, `backend/apps/accounts/management/commands/{force_password_reset,invalidate_all_sessions}.py`,
  `backend/apps/accounts/security_actions.py`, `backend/lmanagement/{checks,security_config}.py`,
  `backend/tests/test_od06_{credential_commands,security_config}.py`,
  `docs/security/OD-06-{history-remediation-assessment,remediation-manifest,rotation-runbook}.md`,
  `frontend/tsconfig.tsbuildinfo`.
- **OD-06 package** = the staged deletion, the settings/security_config/checks/apps.py/test changes, the
  two management commands + `security_actions.py`, the env example files, the `.gitignore` edit, the
  setup/script edits and the three `docs/security/OD-06-*` docs. All preserved. SHA-256 of every
  uncommitted file was recorded outside the repo (`/tmp/lm-orch-baseline/uncommitted.sha256`, 32 files)
  and re-verified after setup.

## Claude / ECC / IDE configuration

- `CLAUDE.md` (ECC-era version; pre-ECC backup in `.claude/backups/2026-11-15-pre-ecc/`).
- `.claude/settings.json`: `defaultMode: acceptEdits`, allow/ask/deny lists, hooks: PreToolUse(Bash)
  `hooks/guard_bash.py`, PostToolUse(Edit|Write) index refresh, SessionStart index, SessionEnd log.
  `settings.local.json`: 3 one-off allow rules.
- Note: `.claude/rules/safety.md` refers to `.claude/hooks/guard-bash.sh`; the real file is `guard_bash.py`.
  Doc drift only (left unchanged and reported here).
- 40 agents (16 project, 12 vendored ECC, 12 added 2026-11-15), 18 skills (all vendored ECC), 7 commands,
  rules `backend/business-rules/documentation-mode/frontend/safety` + `rules/ecc/{common,python,react,typescript,web}`.
- **ECC**: vendored at commit `d2ef2680` (2026-11-15, MIT). The plugin `everything-claude-code@everything-claude-code`
  is **not installed** (installed plugins: only `jetbrains-central@jetbrains-central`). No ECC installer was run.
  `ECC_HOOK_PROFILE=minimal`.
- User settings `~/.claude/settings.json`: Central-routed (`ANTHROPIC_BASE_URL` → 127.0.0.1:19516, `apiKeyHelper`
  → `central …`), `enforceAvailableModels: true` with 15 models, model picker "via JetBrains Air". Not modified.
- MCP: `pycharm` server (global, HTTP 127.0.0.1) — Connected. No project `.mcp.json`.
- Session permission mode at setup: **bypass permissions active** (not from project settings).
- Claude Code 2.1.325 · Central 2.5.0 (authenticated, proxy running) — see `CENTRAL_CLI.md`.

## Decisions register (`docs/erp-transformation/12-decisions-register.md`, uncommitted edit)

Approved: OD-01 … OD-10, OD-21 (OD-06 amended package approved 2026-11-16). Open: OD-11 … OD-20.
Snapshot: `.claude/state/decisions-snapshot.md`.

## Observed during setup (not caused by this setup)

Between 08:57 and 08:58, another concurrent Claude session created four worktrees on new `feature/erp-*`
branches at `e6dfc9b7` (see `ACTIVE_TASKS.md`). They were left untouched.

## Rollback of this setup

Everything added is listed in the final report. To revert: delete the new files (`.claude/orchestration/`,
`.claude/state/`, `.claude/agents/erp-*.md`, the 10 new skill directories). Then revert the additive hunks in
`.claude/settings.json`, `.claude/hooks/guard_bash.py`, `.claude/hooks/test_guard_bash.py`, `CLAUDE.md` and
`.claude/agents/README.md` (`git diff` shows exactly those hunks; these files had no other uncommitted changes).
