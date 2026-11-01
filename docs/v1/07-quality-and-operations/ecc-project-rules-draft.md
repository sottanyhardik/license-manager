# ECC project rules for License Manager — DRAFT, NOT ACTIVE

Status: **draft only.** Nothing in this file is loaded by any agent session. It becomes active only when the owner approves one of the options in [ECC integration status](ecc-integration-status.md) section 7 and the rules file is placed where the agent loads it.

## Where these rules would live (decision pending)

| Option | Mechanism | Evidence | Trade-off |
| --- | --- | --- | --- |
| A | `.claude/rules/license-manager.md` (project scope, path-scoped rules are also supported) | The bundled Claude Code CLI 2.1.312 recognises `.claude/rules/*.md` and `.claude/rules/**` (string search of the binary; **not** tested in a live session) | New untracked file under `.claude/`; does not edit the tracked `CLAUDE.md` |
| B | Amend the tracked root `CLAUDE.md` | `CLAUDE.md` is tracked in git. It currently says "Never modify source code" and describes a documentation-only agent, which conflicts with this mission | Changes the instruction every session reads; needs owner approval and a reviewed commit |
| C | ECC rules copy to `~/.claude/rules/ecc/` | ECC README: plugin cannot distribute rules; manual copy only | **Global** effect on every project. Not recommended for a project-specific rule set |

Plugin `CLAUDE.md` is **not** loaded as project context (verified by `plugin validate`), so ECC's own CLAUDE.md gives no guidance here.

## Conflict that must be resolved first

`CLAUDE.md` (tracked) says **"Never modify source code"**. The current mission requires source changes. **Resolved on 2026-10-31 by option B**: a 2-line scope amendment at the top of `CLAUDE.md`. The original rule (line 52) is unchanged and applies outside the V1 mission. The amendment is uncommitted and needs owner review. Removing its blockquote restores the original scope.

## Draft rules (to be placed in the chosen file)

1. **Investigate before changing.** Consult the code index (`.claude/index/`) and the V1 documents in `docs/v1/` before reading or editing source. Cite the file and symbol for every behavioural claim.
2. **Preserve business logic.** Do not change licence-balance formulas, rounding, hidden-BOE treatment, allocation, or ledger semantics unless the change is specified and covered by tests. Owner decisions D1–D6 in `docs/v1/00-executive-overview/decisions-required.md` are not decided and must not be implemented by inference. D2 (balance semantics) is open.
3. **Small, reviewable changes.** One behavioural change per change set. Add or update a focused regression test with every behavioural change.
4. **Preserve API contracts** unless a deliberate, documented change is approved. Update every dependent caller in the same change.
5. **Authorization.** Enforce permissions on the backend. Frontend hiding is not authorization. Test direct API access and cross-company access for any endpoint touched.
6. **Money and quantities.** Use `Decimal` with the existing 2-dp quantisation helpers. Do not introduce floats into financial calculations.
7. **Migrations.** Additive and reversible by default. Run `makemigrations --check --dry-run`. Never run a destructive migration against any non-test database without explicit approval and a documented recovery plan.
8. **Tests and gates.** Report only commands that were actually run, with exit codes and counts. Never fabricate results or coverage. Backend: `manage.py check`, migration drift check, and the relevant pytest scope. Frontend: `npm run lint`, `typecheck`, `test`, `build`, and `format:check` for applicable changes.
9. **Isolated test databases.** When running pytest, set `TEST_DB_NAME` to a dedicated name so concurrent runs cannot drop each other's test database.
10. **Docs.** Update `docs/v1/` alongside any material architectural or behavioural change, and the traceability matrix where a route, endpoint, or workflow changes.
11. **Git safety.** No `git reset --hard`, `git clean`, forced checkouts, destructive stash operations, commits, or pushes without explicit authorization. Preserve untracked `docs/v1/` and all stashes.
12. **Operations.** No production data, configuration, or service changes without explicit authorization. Do not terminate processes not started for the current task.
13. **Secrets.** Do not read or print `.env`, deploy secret files, `~/.claude.json`, or `~/.codex/auth.json`. Report only file names and hashes.
14. **Dependencies and MCP.** Do not add dependencies or MCP servers without evaluating purpose and maintenance cost, and without owner approval for MCP servers that run downloaded packages.

## Verification required before this draft can be activated

- Enable ECC (or the chosen option) and confirm the rules are loaded in a live session by asking the agent to quote rule 1. This is a harmless verification, and it must run only after the owner approves enabling the plugin, because the plugin's session hooks run during that session.
- Confirm the rules file is not duplicated by any ECC rules copy.
