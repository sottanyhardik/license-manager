# User questions register

Every product-owner question asked during the audit interview. One question per message. Status values: PENDING_USER, ANSWERED, CONFIRMED, IMPLEMENTATION_REQUIRED, IMPLEMENTED, VERIFIED. Categories: BUSINESS_RULE, FINANCIAL_RULE, SECURITY_POLICY, WORKFLOW, USER_EXPERIENCE, REPORTING, DATA_POLICY, INTEGRATION, TECHNICAL_TRADEOFF, PRODUCT_SCOPE.

Answers are recorded in `user-decisions.md`. Confirmed requirements are in `approved-business-requirements.md`.

| Q ID | Category | Priority | Title | Status | Related issues / decisions | Depends on |
|---|---|---|---|---|---|---|
| Q-001 | BUSINESS_RULE | P0 | Meaning of "Null DFIA" and its balance cut-off | ANSWERED (UD-003): `balance_cif` < 200 everywhere. Currency to be confirmed under Q-011. | ISS-001, ISS-002, ISS-003; DEC-01 | — |
| Q-002 | SECURITY_POLICY | P0 | May USER_MANAGER act on superuser accounts? | PENDING_USER (queued) | ISS-011 | Agent 05b verification |
| Q-003 | SECURITY_POLICY | P0 | Which roles may see company PAN, GST and bank details, including in exports? | PENDING_USER (queued) | ISS-012 | Agent 05b verification |
| Q-004 | FINANCIAL_RULE | P0 | Treatment of hidden (OTH / previous-owner) BOEs in the licence balance | PENDING_USER (queued) | Characterization test `test_balance_semantics_d2_characterization.py` (93,000 vs 63,000 gap) | Agent 06 verification |
| Q-005 | FINANCIAL_RULE | P0 | How the approved available-balance rule relates to the Customs and Financial engines | PENDING_USER (queued; evidence now available) | Repo D2 (`decisions-required.md`); owner D2; ISS-019 to ISS-024 | Agent 06 verified (done) |
| Q-016 | FINANCIAL_RULE | P0 | Reconsider approved rule UD-002 in light of ISS-019 to ISS-021 (new evidence against "not deducted twice") | PENDING_USER (queued; owner must decide whether to reconsider) | UD-002; ISS-019, ISS-020, ISS-021 | Q-005 |
| Q-006 | TECHNICAL_TRADEOFF | P0 | Dashboard counts: live balance or stored flag | PENDING_USER (queued) | DEC-02, ISS-001 | Q-001 |
| Q-007 | DATA_POLICY | P1 | Correction of historical stored Null DFIA flags | PENDING_USER (queued) | DEC-03 | Q-001, Q-006 |
| Q-008 | USER_EXPERIENCE | P1 | Server-side default filter on the licence list | PENDING_USER (queued) | DEC-04, ISS-002 | Q-001 |
| Q-009 | SECURITY_POLICY | P1 | Session revocation on logout, password change and password reset | PENDING_USER (queued) | ISS-013 | — |
| Q-010 | TECHNICAL_TRADEOFF | P1 | Scheduled Celery jobs: keep, remove or re-implement | PENDING_USER (queued) | ISS-014 | — |
| Q-011 | BUSINESS_RULE | P0 | Currency of the 200 threshold: `$` or `₹` | ANSWERED (UD-004): US dollars | UD-003; ISS-003 | Q-001 answer |
| Q-017 | REPORTING | P1 | DFIA report "NULL DFIA" table: keep the ₹1,000 / ₹20,000 split, or use the Null DFIA (`balance_cif` < $200) rule | PENDING_USER (queued) | UD-003; `report_service.py:196–255` | Q-011 (answered) |
| Q-018 | USER_EXPERIENCE | P1 | Dashboard "Missing DGFT — Require data entry" card: keep this label and meaning, or change it to the Null DFIA balance rule | PENDING_USER (in questionnaire) | UD-003; `Dashboard.tsx` around 415–425 | Q-001 (answered) |
| Q-019 | BUSINESS_RULE | P1 | "Expiring soon" dashboard card: balance threshold (US$100 in code) and 30-day window | PENDING_USER (in questionnaire) | `views/dashboard.py` ~119–135 | — |
| Q-020 | FINANCIAL_RULE | P0 | When a BOE is linked to an allotment, is it one consumption or two? | PENDING_USER (in questionnaire) | ISS-022; `balance_calculator.py` ~745–826; `percentage_existing_usage.py` ~216–226 | — |
| Q-021 | FINANCIAL_RULE | P1 | Which outstanding allotment types (AT, AR) reduce available balance | PENDING_USER (in questionnaire) | ISS-024 | Q-022 |
| Q-022 | FINANCIAL_RULE | P0 | What "allotted entitlement" means in the approved rule | PENDING_USER (in questionnaire) | UD-002 | — |
| Q-023 | FINANCIAL_RULE | P1 | Several sales linked to one BOE: cap billed utilisation at BOE CIF? | PENDING_USER (in questionnaire) | ISS-023 | Q-016 |
| Q-024 | BUSINESS_RULE | P1 | "Protected Nut Products reserve" in the SION waterfall: live rule, amount and unit | PENDING_USER (in questionnaire) | `split_by_percentage_planner.py` ~286–287 | Q-013 |
| Q-025 | BUSINESS_RULE | P1 | Should commission purchases reduce the licence balance? | PENDING_USER (in questionnaire) | `balance_calculator.py` ~1091–1116; ledger characterization tests | Q-005 |
| Q-026 | FINANCIAL_RULE | P1 | Negative licence balance: show as negative or floor at zero | PENDING_USER (in questionnaire) | `balance_calculator.py` ~1397–1404, ~1643–1651 | Q-005 |
| Q-028 | TECHNICAL_TRADEOFF | P2 | How to commit the uncommitted work | PENDING_USER (in questionnaire) | GIT-1; ISS-009 | — |
| Q-029 | TECHNICAL_TRADEOFF | P2 | Git-ignore `frontend/responsive-screenshots/` | PENDING_USER (in questionnaire) | ISS-010 | — |

Consolidated questionnaire generated 2026-11-01: `Project_User_Decisions_Questionnaire_2026-11-01.docx` (Downloads). It contains 26 open questions: 8 Critical, 16 Important, 2 Optional.
| Q-012 | SECURITY_POLICY | P1 | Browser token and download-token posture | PENDING_USER (queued) | Repo D4 | — |
| Q-013 | BUSINESS_RULE | P0 | SION and restriction pool semantics | PENDING_USER (queued) | Repo D3 | — |
| Q-014 | PRODUCT_SCOPE | P1 | Accounting scope for V1 | PENDING_USER (queued) | Repo D5 | — |
| Q-015 | SECURITY_POLICY | P2 | Audit-trail assurance level | PENDING_USER (queued) | Repo D6; ISS-related activity logging | — |

Module-by-module interview questions (company, user, customer, supplier, exporter, importer, licence, DFIA, SION, BOE, allotment, trade, billing, invoicing, payment, commission, client ledger, accounting, reconciliation, reporting, documents, dashboard, navigation, search, notifications, mobile, future scope) are not yet drafted. They are queued after the P0 items above.

---

## Q-001 — Meaning of "Null DFIA" and its balance cut-off

- **Category:** BUSINESS_RULE
- **Priority:** P0
- **Status:** PENDING_USER (asked 2026-11-01; waiting for answer)

**Current application behaviour**

- Licence list filter `is_null` (`backend/apps/license/views/license.py`, `apply_advanced_filters`; documented at about line 219): live balance below ₹200 is "Null DFIA"; ₹200 or more is not.
- Stored flag `LicenseFlags.is_null`, set when balance is below ₹500: `backend/apps/license/signals.py:316`, `backend/apps/license/services/validation_service.py:322`, `backend/apps/license/management/commands/sync_licenses.py:193`.
- Maintenance script: below ₹100 (`backend/apps/core/scripts/calculate_balance.py:210`).
- Dashboard card titled "Missing DGFT" with the description "Require data entry", counting the stored flag and linking to `/licenses?is_null=True&is_expired=all` (`frontend/src/pages/Dashboard.tsx` around lines 415–425).
- DFIA reports: the "NULL DFIA" table lists active licences with balance below ₹1,000, and expired licences below ₹20,000 (`backend/apps/license/services/report_service.py:196–255`).

**Ambiguity**

The same label is used for a balance cut-off at five different levels (₹100, ₹200, ₹500, ₹1,000, ₹20,000) and, on the dashboard, for a data-completeness alert ("Missing DGFT, require data entry"). These cannot all be right.

**Affected modules**

Licence list and filters, dashboard KPI and alert card, DFIA and SION reports, licence sync, validation service, signals, licence exports.

**Related issues**

ISS-001 (dashboard and list disagree), ISS-002 (server default not applied), ISS-003 (multiple thresholds); DEC-01.

**Business impact**

A licence can show as "Null DFIA" on the dashboard while the list shows it as not Null DFIA, and reports use different cut-offs again. Users who act on those lists (for example, data entry or follow-up with DGFT) may chase the wrong licences.

**Available options**

- A. Null DFIA is a balance cut-off at ₹200 everywhere. Matches the live licence list. Changes the stored-flag computation, the signal, the validation service and the sync command.
- B. Null DFIA is a balance cut-off at ₹500 everywhere. Matches the stored flag. Changes the live list filter and every consumer of `is_null`.
- C. Two separate concepts with separate names. (1) A low-balance cut-off, with a figure you set, used for filters and reports. (2) "Null DFIA" as a different condition, for example missing DGFT details, which is what the dashboard card says.
- D. Something else. You describe what Null DFIA means in your business.

**Recommendation**

C. The dashboard card says "Missing DGFT — require data entry", which reads as a data-completeness alert, not a balance threshold. The code has five balance figures for one concept. Splitting the two concepts stops one number from driving unrelated screens. I do not recommend a figure. You choose the low-balance figure, if any.

**Final interpretation**

Pending owner answer.

**Required implementation** (after answer)

Depends on the answer. Under A or B: change the single threshold constant, its stored-flag computation and all consumers, and update the two existing tests that pin 200 and 500. Under C: two named concepts, two labels, and a rule per consumer.

**Required tests** (after answer)

Boundary tests at the chosen figure(s) for the list filter, stored flag, dashboard count, DFIA report and export. Parity test that the dashboard count equals the list count for the same filter.

**Acceptance criteria** (after answer)

For every screen that shows Null DFIA or low balance, the count and the rows agree with the approved definition, and the label matches the definition.

**Status:** ANSWERED on 2026-11-01 (see UD-003). Currency clarification open under Q-011. Two follow-ups are open: the "NULL DFIA" DFIA report split at ₹1,000/₹20,000 (`report_service.py:196–255`), queued as Q-017, and the dashboard "Missing DGFT" card (`Dashboard.tsx` around 415–425), queued as Q-018.

---

## Q-002 — May USER_MANAGER act on superuser accounts? (queued)

- **Current behaviour:** USER_MANAGER can list, reset the password of, and (through the default ModelViewSet) delete any user, including superusers. Source read: `backend/apps/accounts/views/user_management.py` and `backend/apps/accounts/permissions.py` around lines 109–112. Runtime not run. Verification agent 05b pending.
- **Problem:** Likely a defect rather than a policy choice, but the owner should confirm the intended rule for superuser accounts.
- **Options (draft):** A. USER_MANAGER may not act on superusers. B. USER_MANAGER may reset passwords but not delete superusers. C. Other.
- **Recommendation (draft):** A.
- **Status:** PENDING_USER. Do not ask until Agent 05b reports.

## Q-003 — Which roles may see company PAN, GST and bank details, including in exports? (queued)

- **Current behaviour:** The company serializer hides PAN, GST and bank fields from roles outside the sensitive list. The export builder reads undeclared columns with `getattr`, so PAN and GST appear in the export for read-only roles. Source read: `backend/apps/core/serializers/models.py:39–62`, `backend/apps/core/views/master_view.py:709–756`, `backend/apps/accounts/permissions.py:209–237`. Runtime not run.
- **Problem:** The on-screen rule and the export rule disagree.
- **Options (draft):** A. Same rule on screen and in export, with the current sensitive-role list. B. Export of sensitive fields only for named roles. C. Other.
- **Status:** PENDING_USER. Ask after Agent 05b reports and after Q-002.

## Q-004 — Treatment of hidden (OTH / previous-owner) BOEs in the licence balance (queued)

- **Current behaviour:** On the characterization fixture (export CIF 100,000; hidden BOE 30,000; visible BOE 5,000; outstanding allotment 2,000; purchase 20,000; sale 15,000), `calculate_balance()` returns 93,000 (excludes hidden BOE), `calculate_customs_balance()` returns 63,000 (includes hidden BOE), and the Customs ledger ends at 63,000. The snapshot's `customs_balance` field is fed by `calculate_balance()` and so reports 93,000. Source: `backend/apps/license/services/balance_calculator.py`, `balance_snapshot.py`, and `backend/apps/license/tests/test_balance_semantics_d2_characterization.py`.
- **Problem:** The same licence shows two different "customs balances" depending on which path is used. The owner's approved available-balance rule does not say how a hidden BOE is treated.
- **Status:** PENDING_USER. Ask after Agent 06 reports and after Q-005.

## Q-005 — How the approved available-balance rule relates to the Customs and Financial engines (queued)

- **Current behaviour:** The code has three balance formulas (Customs, Financial and the snapshot), each with different debit rules. The repo's `decisions-required.md` D2 asks which of these is shown to users. The owner's approved rule (allotted − unbilled BOE − billed utilisation, billed BOE not deducted twice) is not written anywhere in the repo.
- **Problem:** It is not clear whether the owner's rule replaces both engines, is one of them, or describes a third output.
- **Status:** PENDING_USER. Ask after Agent 06 reports.

## Q-006 to Q-015

Drafted in the summary table above. Full entries are added when each is asked. Their details come from `execution/unresolved-decisions.md` (DEC-02 to DEC-04), `docs/v1/00-executive-overview/owner-decision-packets.md` (D3 to D6), and the security findings in `discovered-issues.md` (ISS-013, ISS-014).
