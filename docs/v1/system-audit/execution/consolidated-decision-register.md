# Consolidated decision register (round 1 answers)

Source: `Project_User_Decisions_Questionnaire_2026-11-01.docx`, answer panels read on 2026-11-01. Registered as draft for owner approval. No code, data or configuration changed.

Status values: **Confirmed**, **Clarification Needed**, **Deferred**.

Answers are recorded as given. Where a free-text answer required interpretation, the interpretation is shown and marked. Where an answer conflicts with an approved rule or a repository safeguard, the conflict is named and the approved rule is not changed.

## Summary

| Status | Count | Items |
|---|---|---|
| Confirmed | 17 | Q-002, Q-004, Q-006, Q-008, Q-009, Q-012, Q-013 (interim), Q-015, Q-017, Q-018, Q-019, Q-021, Q-023, Q-025, Q-026, Q-028, Q-029 |
| Clarification Needed | 9 | Q-003, Q-005, Q-007, Q-010, Q-014, Q-016, Q-020, Q-022, Q-024 |
| Deferred | 3 | Q-013 policy table; Q-015 event-by-event durability list; Q-010 remaining two jobs (in the Clarification table) |

Totals: 17 + 9 = 26 questions. Q-010 is in the Clarification table because its daily-sync part is confirmed (option A) and its other two jobs are not decided. Q-013 and Q-015 are Confirmed for their interim answers and Deferred for the rest.

## Confirmed decisions

| ID | Topic | Answer | Interpretation | Affected modules | Test and implementation requirements |
|---|---|---|---|---|---|
| Q-002 | USER_MANAGER and superusers | A | USER_MANAGER cannot view, reset the password of, or delete superusers. | Accounts (user management) | Negative tests for each action against a superuser; positive tests for non-superuser management. Implemented 2026-11-01 (Slice 1): `backend/apps/accounts/views/user_management.py`; tests `backend/apps/accounts/test_superuser_protection.py`; evidence `docs/v1/system-audit/evidence/iss-011-013-verification.md`. |
| Q-004 | Hidden (previous-owner / OTH) BOE debits | YES (mapped to option A) | Hidden BOE debits reduce every balance figure. Consistent with Q-005 answer. | Balance outputs, customs ledger, snapshot | Balance tests with the hidden-BOE fixture; expected result changes for live balance. |
| Q-006 | Dashboard counts | A | Dashboard counts use live balance. | Dashboard, licence list | Parity test: dashboard count equals list count for the same filter. |
| Q-008 | Licence list API default filter | A | Keep the unfiltered API. Correct the dead lookup for clarity only; no behaviour change. | Licence list API | Existing unfiltered-API tests remain passing. |
| Q-009 | Sessions on password change, reset and logout | A | A password change or reset ends all other sessions of that user. Logout ends the current session only. | Accounts, token handling | Depends on ISS-013 verification (the security re-check did not complete; see Open items). |
| Q-012 | Browser and download tokens | A | Keep local-storage tokens and URL-token compatibility. Recorded as an accepted security trade-off. | Authentication, protected downloads, invoice share links | Record the accepted trade-off in the security document. |
| Q-013 | SION and restriction rules (interim) | A | Freeze current behaviour with golden test data. Policy table is deferred (see Deferred). | SION planning, split planner, allocation | Golden-data snapshot tests before any change. |
| Q-015 | Audit assurance | R (recommended option C) | Durable audit for some events, best-effort for others, chosen per event type. | Activity history, reconciliation logs, maintenance | Event-type list is Deferred (see below). |
| Q-017 | DFIA report NULL DFIA table | A | NULL DFIA table uses balance below US$200. The 1,000 and 20,000 split is removed. | DFIA reports, item report | Boundary tests at 199.99, 200, 200.01. |
| Q-018 | Dashboard "Missing DGFT" card | A | Card renamed "Null DFIA — balance under US$200" and counts the balance rule. | Dashboard | Count and label test. |
| Q-019 | Expiring-soon card | B | 30-day window and balance threshold of US$200 (Null DFIA threshold). Changes the current US$100. | Dashboard | Boundary test at US$200 and 30-day window. |
| Q-021 | AT and AR allotments | B | Both AT and AR allotments reduce the available balance. Overrides my recommendation (A). | Licence balance, item balance | Licence and item figures must agree; test with an AR and an AT allotment. |
| Q-023 | Several sales linked to one BOE | C | Allow and count every sale (current behaviour). Over-deduction risk (ISS-023) is accepted. | Trade, licence balance | Record accepted risk; test current behaviour. |
| Q-025 | Commission purchases | B | Commission is a separate metric and does not change the licence balance. | Trade, licence balance, ledger, exports | Balance excludes commission; ledger shows commission as a separate metric. Affects the Q-005 formula (see Clarification). |
| Q-026 | Negative balance | B | A negative balance is shown as negative. | Balance outputs, ledger, dashboard, exports | Negative-value display tests on screen, export and API. |
| Q-028 | Commit uncommitted work | A | Owner reviews, then commits in grouped commits. No commit made by the audit. | Repository | None until the owner asks for commits. |
| Q-029 | Screenshot folder | A | Git-ignore `frontend/responsive-screenshots/`. Interpreted from the explanation field; the option letter was left blank. | Repository | Ignore rule added only when approved. |

## Clarification needed

| ID | Topic | Answer given | Problem | Clarification required |
|---|---|---|---|---|
| Q-003 | Who sees PAN, GST and bank details | "ALL WILL SEE NO RESTRICTION" | Unclear whether this covers the on-screen restriction as well as exports. The on-screen restriction is a deliberate role list (`full_access_roles_for_sensitive_fields`). Removing it exposes bank account numbers to every company reader. | Does this apply to screen as well as export? (Round 2, R2-01) |
| Q-005 | Single source of truth for balance | "Make a single source of truth in the licence model: balance CIF = Total CIF − (allotted, no linked BOE) − (BOE, no linked bill) − billed." Hidden / OTH BOEs act as BOEs with no linked bill. Linked BOEs and their bills are excluded. | The formula is cut off after "billed". The term "billed" is not defined. The formula as written still deducts both a BOE with no linked bill and any sale, so an unlinked sale still double-deducts. That conflicts with the Q-016 answer. | Complete the formula and define "billed" and "allotted". (Round 2, R2-03) |
| Q-007 | Historical Null DFIA flags | B: recalculate all flags now, without a report | Conflicts with DEC-03 (`unresolved-decisions.md`), which requires a read-only reconciliation report, an approved correction rule, an audit record per changed flag and a rollback plan before any change. The owner has the authority to waive it, but the waiver must be explicit. | Confirm the waiver, or choose the report-first path. (Round 2, R2-06) |
| Q-010 | Scheduled jobs (two of three) | A: keep daily licence sync; decide the other two separately | The daily sync is confirmed. The licence-update check and the task-record cleanup are not decided. | Decide each. (Round 2, R2-07) |
| Q-014 | Accounting scope | "A, B, C" | Options were exclusive. Three letters were given, which could mean A alone, A with B and C, or something else. | Which combination? (Round 2, R2-08) |
| Q-016 | Approved rule UD-002 and three cases | Other: "We don't maintain row-level trade. Show the difference between financial and customs balance in the licence overview." | This is a new option. It conflicts with UD-002 (approved) for the unlinked-sale case, which the approved rule says must not deduct twice. Showing the difference does not change the balance. | Approve amending UD-002 for unlinked sales, or choose another option. (Round 2, R2-04) |
| Q-020 | BOE linked to an allotment | "Consume the allotment once" | The principle is accepted. The answer does not say what happens to the rest of an allotment when the BOE is smaller. The Q-005 formula excludes a linked allotment entirely, which drops the remainder. | Is the remainder outstanding, or used up? (Round 2, R2-05) |
| Q-022 | Meaning of "allotted entitlement" | Unanswered | Critical. It is the starting figure of UD-002. The Q-005 answer uses "allotted" in a different sense. | Choose the meaning. (Round 2, R2-02) |
| Q-024 | Protected Nut Products reserve | "B," (live fixed reserve) | Live rule is confirmed, but the unit is not stated. | State the unit. (Round 2, R2-09) |

## Deferred

| ID | Topic | Why deferred | Trigger to revisit |
|---|---|---|---|
| Q-013 | Full SION policy table | Interim freeze chosen. The table requires owner-supplied rules. | When the owner supplies the policy table. |
| Q-015 | Event-by-event audit durability | The answer chose a per-type approach, but the list of event types is not yet written. | After engineering proposes a list for approval. |
| Q-010 | Licence-update check and task-record cleanup | Not decided (see Clarification). | Round 2, R2-07. |

## Conflicts with approved rules and safeguards

1. **UD-002 (available balance) and Q-016.** The owner's Q-016 answer accepts the unlinked-sale case and asks for a difference to be shown. The approved rule says billing must not deduct twice. Approval is needed before the approved rule is changed. The rule has not been changed.
2. **DEC-03 (flag reconciliation) and Q-007.** The owner's B answer waives the report and audit requirements. The waiver must be confirmed. No flag has been changed.
3. **Q-003 and the sensitive-field design.** The "no restriction" answer reverses a deliberate role list. Confirm the scope before any change.
4. **Q-005 formula and Q-016 answer.** The formula as written still deducts an unlinked sale twice. This must be resolved with R2-03 and R2-04 together.

## Open items that block implementation

- Critical: Q-022 (unanswered), Q-005 (formula incomplete), Q-016 (approval needed), Q-020 (remainder), Q-003 (scope).
- Verification: the security re-check of ISS-011, ISS-012 and ISS-013 stopped before writing its report (`agents/agent-05b-security-verification.md` does not exist). ISS-011 and ISS-012 were read directly during the audit. ISS-013 is still unverified. Q-009 (session rule) cannot be implemented until ISS-013 is verified.

## Round 2 answers (asked in chat, one at a time)

| Item | Ref | Answer | Status |
|---|---|---|---|
| R2-01 | Q-003 | B: exports show PAN, GST and bank details to all company readers; the on-screen restriction for roles outside the sensitive list stays. | Confirmed |
| R2-02 | Q-022 | A: "allotted entitlement" means the licence's total export CIF. | Confirmed |
| R2-03 | Q-005 | Formula: balance CIF = Total CIF − (allotted, no linked BOE) − (BOE, no linked bill) − billed. "Billed" = all sales, linked or not (option B). Unlinked sales are deducted twice, and the user corrects them manually. | Confirmed (conflict with UD-002 acknowledged; see R2-04) |
| R2-04 | Q-016 | A: UD-002 is amended for unlinked sales. The balance deducts both the BOE and the sale. The licence overview shows the difference between the financial and customs balance. UD-002 still applies to linked billing. | Confirmed (UD-002 amendment approved for this case only) |
| R2-05 | Q-020 | Other: once a BOE is linked to an allotment, the allotment is ignored and only the BOE counts. The unused part of the allotment is recredited to the balance. Example: licence 100; allotment 50 → balance 50; linked BOE 40 → balance 60. | Confirmed (new option C). Edge case to confirm: a linked BOE larger than its allotment. |
| R2-06 | Q-007 | B: recalculate historical Null DFIA flags now without a reconciliation report. The DEC-03 safeguards are waived for this change. The owner typed "B", not the word "waive"; the option text states the waiver and is recorded as such. No data changed yet; a separate go-ahead is needed before the recalculation runs. | Confirmed (DEC-03 waiver for this change; implementation needs a separate go-ahead) |
| R2-07 | Q-010 | One daily job, run once a day. It does the licence update and the task-record cleanup together. No separate licence-update check (R2-07a = A). Supersedes the round 1 answer A for the daily sync. | Confirmed |
| R2-08 | Q-014 | D: V1 accounting scope is commercial invoice and payment evidence, a double-entry general ledger, and bank statement matching. | Confirmed in scope. Implementation Deferred until finance supplies requirements (chart of accounts, posting events, tax, periods and locks, reversals, bank source, reconciliation authority). Per D5. |
| R2-09 | Q-024 | A: Protected Nut Products reserve is a live, fixed reserve of US$2.70 per kilogram. | Confirmed |
| R2-10 | Register | Pending | Draft |

## Approval

**Approved by the owner on 2026-11-01 (R2-10 = A).** The register is the approved record of decisions for V1 as listed above. Items marked Deferred are not approved for implementation. The R2-06 waiver authorises only the decision to recalculate flags; running the recalculation on data still needs a separate go-ahead.

Implementation order and gates are in `docs/v1/08-implementation/decision-implementation-plan-2026-11-01.md`.
