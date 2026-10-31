from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, KeepTogether)
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.colors import HexColor

OUT = 'output/enterprise-modernization-assessment/LICENSE_MANAGER_OPTION_A_WITHOUT_ACCOUNTING.pdf'
PAGE_W, PAGE_H = A4
NAVY = HexColor('#17324D')
BLUE = HexColor('#DCEBFA')
ROW = HexColor('#F3F6F9')
RED = HexColor('#A82424')
GREEN = HexColor('#256B45')

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='CoverTitle', parent=styles['Title'], fontName='Helvetica-Bold',
    fontSize=28, leading=34, alignment=TA_CENTER, textColor=NAVY, spaceAfter=8))
styles.add(ParagraphStyle(name='CoverSub', parent=styles['Normal'], fontSize=13, leading=18,
    alignment=TA_CENTER, textColor=NAVY))
styles.add(ParagraphStyle(name='H1x', parent=styles['Heading1'], fontName='Helvetica-Bold',
    fontSize=18, leading=23, textColor=NAVY, spaceBefore=0, spaceAfter=9))
styles.add(ParagraphStyle(name='H2x', parent=styles['Heading2'], fontName='Helvetica-Bold',
    fontSize=12.5, leading=16, textColor=NAVY, spaceBefore=9, spaceAfter=5))
styles.add(ParagraphStyle(name='Bodyx', parent=styles['BodyText'], fontSize=9.3, leading=13,
    spaceAfter=6, textColor=HexColor('#1F2937')))
styles.add(ParagraphStyle(name='Small', parent=styles['BodyText'], fontSize=7.8, leading=10.5,
    textColor=HexColor('#26384A')))
styles.add(ParagraphStyle(name='TableHead', parent=styles['BodyText'], fontName='Helvetica-Bold',
    fontSize=7.8, leading=10.5, textColor=colors.white))
styles.add(ParagraphStyle(name='Note', parent=styles['BodyText'], fontSize=9, leading=13,
    leftIndent=7, rightIndent=7, textColor=NAVY))

def P(s, style='Bodyx'):
    return Paragraph(str(s), styles[style])

def table(headers, rows, widths=None, small=True):
    style = 'Small' if small else 'Bodyx'
    values = [[P(x, 'TableHead') for x in headers]] + [[P(x, style) for x in row] for row in rows]
    t = Table(values, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), .25, HexColor('#AFC0D0')), ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, ROW]),
        ('LEFTPADDING', (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    return t

def callout(title, text, color=BLUE):
    t = Table([[P('<b>%s</b><br/>%s' % (title, text), 'Note')]], colWidths=[174*mm])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),color),('BOX',(0,0),(-1,-1),.5,HexColor('#8EACC8')),
                           ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
                           ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    return t

def section(title, lead=None):
    out=[P(title, 'H1x')]
    if lead: out.append(P(lead))
    return out

def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(HexColor('#B7C7D7')); canvas.line(18*mm, 13*mm, PAGE_W-18*mm, 13*mm)
    canvas.setFont('Helvetica', 7.5); canvas.setFillColor(HexColor('#526577'))
    canvas.drawString(18*mm, 8.5*mm, 'License Manager | Option A detailed scope | Audit-only | 31 October 2026')
    canvas.drawRightString(PAGE_W-18*mm, 8.5*mm, 'Page %d' % doc.page)
    canvas.restoreState()

story=[]
story += [Spacer(1, 42*mm), P('License Manager', 'CoverTitle'), P('Option A - detailed scope without accounting', 'CoverTitle'),
          Spacer(1, 5*mm), P('Enterprise modernization assessment | 31 October 2026', 'CoverSub'), Spacer(1, 15*mm),
          callout('Management decision', 'Modernize the operational Licence Manager first. This option deliberately excludes a new general ledger, double-entry accounting, accounting bank reconciliation and financial statements.', BLUE),
          Spacer(1, 9*mm), P('<b>Planning baseline:</b> 445 developer-days likely (range 237-770), subject to validation against approved business rules, isolated test evidence and remediation sampling.', 'CoverSub'),
          Spacer(1, 20*mm), P('Evidence status: local repository and authenticated local UI were assessed read-only. Production deployment, production data, backup restoration and complete dynamic-route coverage remain unverified.', 'CoverSub'), PageBreak()]

story += section('1. Executive decision summary', 'Option A is the smallest reliable programme that tackles the operational risks already visible in the current system without turning the application into an accounting platform.')
story += [table(['Decision area','Option A commitment','Outcome'], [
    ['Trust boundary','Define and enforce server-side company scope for queries, writes, exports and background jobs.','Records cannot rely on a UI company selector alone.'],
    ['Licence correctness','Make one auditable owner for balances, allocations, restrictions and report totals.','The owner can trace a number to its transactions.'],
    ['Reconciliation','Classify candidate differences using source evidence before correction.','No mass cleanup or overwritten balances.'],
    ['Usability','Create focused work queues, safe corrections, parity reports and clear exceptions.','One or two employees need fewer manual cross-checks.'],
    ['Release discipline','Require isolated tests, UAT, recovery evidence and rollback gates.','Useful change without risking live operations.'],
], [31*mm, 82*mm, 61*mm]), Spacer(1,6),
callout('Recommendation', 'Approve Phase 0 only until the owner confirms company policy, authoritative restriction documents, correction policy and required reports. Accounting can be evaluated after a stable operational release.', HexColor('#E8F4EA')),
P('Explicit exclusion', 'H2x'), P('Option A does <b>not</b> build a chart of accounts, journals, accounting vouchers, AR/AP ledgers, bank-statement matching, trial balance, Profit and Loss from postings, balance sheet, tax closing, or accounting migration. Existing operational invoices, BOEs and operational reconciliation remain in scope.') , PageBreak()]

story += section('2. Verified assessment position', 'Findings below distinguish what was directly observed from risks that require controlled verification.')
story += [table(['Area','Evidence / result','Status','Operational consequence'], [
 ['Repository baseline','Branch develop at d2cb2446ba01e0e23e6ef3570f6449bdd001cf65. Deployment commit unknown.','CONFIRMED / NOT ASSESSED','Local code cannot be assumed to equal production.'],
 ['Local access','Root, health and schema endpoints responded; sampled business endpoints required authentication.','CONFIRMED','Authentication boundary exists, but authorization depth requires separate proof.'],
 ['UI pages','Dashboard, Licences, SION Planning, Allotments, BOEs, Trades, Reconciliation and Reconciliation Issues rendered under local authenticated read-only review.','CONFIRMED','Visible state and normal navigation reviewed; mutation paths not exercised.'],
 ['Tests','Frontend: 543/544 passed; one AllocationStrategyEditor test failed. Typecheck passed. Lint reported 3 errors and 9 warnings.','CONFIRMED','Regression baseline is not clean.'],
 ['Route collision','Direct /admin/users resolved to Django admin login, not the React user-management route.','CONFIRMED P1','Administration navigation/URL ownership needs an explicit decision and regression test.'],
 ['Company isolation','Global roles and unscoped-query evidence were found; complete tenant enforcement was not demonstrated.','INFERRED RISK P0','A cross-company data boundary must be proven server-side before trust is claimed.'],
], [29*mm, 66*mm, 30*mm, 49*mm]), Spacer(1,7),
P('Inspection limitation', 'H2x'), P('No production database query, record edit, migration, deployment, destructive test, restore test or penetration test was performed. Every remediation item must begin from a read-only, reproducible baseline in an isolated environment.'), PageBreak()]

story += section('3. Page and workflow scope', 'The browser assessment is useful operational evidence, but it is not proof that every route, permission path or mutation workflow works.')
story += [table(['Inspected page','Read-only observation / required modernization outcome','Priority'], [
 ['Dashboard','Displayed operating indicators. Make KPI definitions clickable, company-scoped, dated and traceable to a filtered underlying list.','P1'],
 ['Licences','Core list/detail access was rendered. Provide canonical entitlement ledger, expiry views, state history and source links.','P0'],
 ['SION Planning','Planning validation issues were visible. Move rule explanations and shared-cap calculations behind a canonical resolver.','P0'],
 ['Allotments','Allocation operational view rendered. Enforce idempotency, available-balance checks and safe amendment/reversal flows.','P0'],
 ['BOEs','BOE list/workflow surface rendered. Add dependency preview, controlled correction and direct reconciliation links.','P0'],
 ['Trades / invoices','Trade data is operationally linked. Clarify invoice lifecycle and prevent duplicate or invalid utilisation.','P1'],
 ['Reconciliation','Metrics and issues list rendered. Define candidate semantics, tolerance, counting unit and review status.','P0'],
 ['Reconciliation Issues','Displayed issue candidates require record-level evidence and owner disposition; do not treat labels as confirmed financial errors.','P0'],
], [35*mm, 116*mm, 23*mm]), Spacer(1,6),
P('Required workflow acceptance evidence', 'H2x'),
table(['Workflow','Minimum safe completion proof'], [
 ['Licence / allocation','Original entitlement, reservation, posted utilisation, reversal and displayed balance agree in a golden scenario.'],
 ['Restriction check','Applicable rule, source/version, base quantity/value, shared pool and user-facing explanation agree.'],
 ['BOE / invoice correction','Downstream dependencies are shown; correction creates a traceable reversal/amendment rather than silently replacing history.'],
 ['Reconciliation','Candidate status, matching basis, tolerance and disposition are traceable; reports reconcile to source records.'],
 ['Company access','Direct ID, list, export, report and background-job cross-company attempts are denied server-side.'],
], [48*mm,126*mm]), PageBreak()]

story += section('4. Data integrity and reconciliation', 'The dashboard counts below were observed as displayed operational metrics only. They must not be represented as verified accounting errors or production-wide facts.')
story += [table(['Displayed metric','Observed value','What is confirmed','Required verification before action'], [
 ['Total BOEs','1,043','A local UI displayed the count.','Query definition, date/company/deletion filters, unique key and record sample.'],
 ['Total import invoices','317','A local UI displayed the count.','Determine whether the unit is document, line or current record.'],
 ['Matched records','2','A local UI displayed the count.','Match algorithm, tolerance, status lifecycle and historical scope.'],
 ['Unmatched invoices','53','A local UI displayed the count.','Confirm excluded/hidden/superseded items and review candidates.'],
 ['Duplicate-debit candidates','1,699','A local UI displayed candidates; no financial duplication conclusion was proved.','Record-level evidence distinguishing valid repeats, historic references and actual duplicates.'],
 ['CIF difference','172,760.37','A local UI displayed a difference.','Currency, rounding, date and reconciliation basis.'],
 ['Missing DGFT','109','A local UI displayed missing-information records.','Required field definition, document source and remediation ownership.'],
], [38*mm, 24*mm, 53*mm, 59*mm]), Spacer(1,7),
callout('Remediation rule', 'Use four queues: (1) safe automated detection, (2) candidates needing owner approval, (3) manual source-document review, and (4) unresolved policy questions. Preserve immutable evidence and record the decision; never “repair” a balance by overwriting a display field.'),
P('Operational reconciliation, not accounting reconciliation', 'H2x'), P('Option A includes matching BOEs, invoices, allocations and utilisation records for operational control. It excludes accounting bank reconciliation, ledger settlement and statutory financial statements.'), PageBreak()]

story += section('5. Canonical calculation and DFIA/SION scope', 'The target is not a new formula guessed during implementation. It is one explicit, tested and explainable owner for each approved rule.')
story += [table(['Metric / rule','Authoritative target owner','Required controls / acceptance criteria'], [
 ['Licence entitlement and available balance','Balance Service plus immutable ledger/read model','Decimal policy; original, reserved, posted, released and reversed states; company scope; time ordering; report/UI parity.'],
 ['Allotment and BOE allocation','Allocation Service','Database transaction and lock strategy; no double consumption; idempotency; clear cancellation and amendment semantics.'],
 ['SION restriction / AU handling','Restriction Resolver plus versioned rule record','Official-source reference, effective period, base, unit conversion, individual vs shared cap and explanation shown to user.'],
 ['Shared aggregate cap','Named condition pool, not free-text percentage grouping','Independent same-percentage groups must not merge; pool membership and consumption are immutable and explainable.'],
 ['Reconciliation difference','Reconciliation Query Service / report read model','Counting unit, filters, tolerance, exclusions, candidate classification and export parity documented.'],
 ['Dashboard / Excel / PDF totals','Read models fed by canonical services','No independent frontend or report formula; trace source -> query -> service -> API -> UI/export.'],
], [44*mm, 49*mm, 81*mm]), Spacer(1,6),
P('Confirmed implementation concern', 'H2x'), P('The condition-pool and SION percentage logic are separate. A free-text percentage-based grouping cannot safely represent independent pools that happen to share the same percentage. Exact rule meaning therefore remains a BUSINESS DECISION REQUIRED until official documents and examples are approved.'),
P('Concurrency acceptance test', 'H2x'), P('In an isolated environment, two simultaneous valid allocation requests for the same remaining entitlement must produce at most one accepted consumption when their combined demand exceeds the available amount. The losing request must return a clear outcome, leave no partial debit and create an auditable event.'), PageBreak()]

story += section('6. Security and company isolation', 'Option A treats company separation as a correctness control, not merely a navigation preference.')
story += [table(['Control','Detailed scope','Release evidence'], [
 ['Tenant/membership boundary','Choose a company/master-data ownership policy; represent membership and active scope explicitly.','Owner-approved policy and test fixtures for at least two companies.'],
 ['Server-side query scope','Scope every queryset, lookup, write, bulk action, report and export by authorized company.','Negative direct-ID/list/filter/export tests prove denial.'],
 ['Object authorization','Verify object belongs to permitted entity after request validation, not only by hiding buttons.','API tests for create/read/update/delete and file download/upload.'],
 ['Background work','Pass and validate tenant/company context in tasks, imports, exports and scheduled jobs.','Task tests demonstrate no cross-company processing.'],
 ['Audit events','Record actor, company, object, prior/resulting state, reason and correlation identifier for material actions.','Audit sample supports traceability without exposing secrets.'],
 ['Route ownership','Resolve /admin/users collision: retain Django admin under an explicit protected URL or move SPA route.','Authenticated and unauthenticated routing regression tests.'],
], [38*mm, 78*mm, 58*mm]), Spacer(1,7),
callout('Risk classification', 'The current evidence does not prove a cross-company breach. It establishes that server-enforced isolation is not demonstrated, which is sufficient to make this a P0 verification and implementation gate.'), PageBreak()]

story += section('7. Option A delivery backlog', 'The estimates below are planning estimates, not completed-task measurements. They include implementation but must be refined with acceptance examples and dependency analysis in Phase 0.')
story += [table(['ID','Epic / independently deliverable outcome','Likely days','Priority','Dependency'], [
 ['LM-001','Company isolation: scoped service/query/export/job access, membership policy and negative tests.','45','P0','Owner company policy'],
 ['LM-002','Canonical balances: Decimal contract, ledger/read model, report parity and golden calculations.','65','P0','Approved examples'],
 ['LM-003','Reconciliation: documented candidate semantics, reproducible baseline and owner remediation queue.','50','P0','Read-only data access'],
 ['LM-004','Restrictions: versioned shared pools, AU/explanations, locking and rule evidence.','70','P1','Domain decision'],
 ['LM-005','BOE/trade: dependency preview, safe amendment/reversal and allocation safeguards.','45','P1','LM-002'],
 ['LM-006','Operational UX/reporting: work queues, filter/export parity, page-specific safety states.','85','P2','LM-002/003'],
 ['LM-007','Quality/release: isolated test data, observability, recovery test, UAT and controlled release.','67','P1','Test/staging access'],
 ['TOTAL','Option A planning baseline','445','', 'Validation required'],
], [18*mm, 88*mm, 20*mm, 16*mm, 36*mm]), Spacer(1,8),
P('Estimate range and calendar', 'H2x'), P('Supplied planning range: 237-770 developer-days. At 3.5 productive developer-days per week, the likely baseline suggests roughly 13-18 calendar months for one developer once business review, UAT and interruptions are included. A small team may reduce calendar duration to about 6-10 months after the foundation, but introduces integration, review and release-coordination overhead.'), PageBreak()]

story += section('8. Implementation phases and exit gates', 'No phase is complete merely because code was written. Each gate requires demonstrated behaviour, documentation and owner acceptance.')
story += [table(['Phase','Scope','Exit gate'], [
 ['0. Evidence and test harness','Freeze read-only baseline, map calculations and routes, establish isolated seeded data and decision log.','Approved rules/examples; reproducible baseline; no unresolved P0 ambiguity hidden.'],
 ['1. Isolation and containment','Company policy, membership, scoped data boundary, route collision resolution and security negative tests.','No cross-company access in API/list/export/job evidence.'],
 ['2. Canonical calculations','Balance ledger/read model, allocation safeguards, Decimal/rounding/cancellation policy and parity reports.','Golden examples and concurrency/reversal tests pass.'],
 ['3. Restriction planning','Versioned rule evidence, condition pools, AU handling and user explanation.','Domain owner approves test cases and exceptions.'],
 ['4. BOE/invoice/reconciliation','Candidate classification, source links, correction workflow and review queue.','Owner signs off sampled classifications; no destructive cleanup.'],
 ['5. UI/report parity','Work queues, page-specific validation/loading/error states, mobile/a11y essentials and exports.','Critical page acceptance and report parity pass.'],
 ['6. Hardening and release','Regression suite, performance checks, backup restore rehearsal, UAT and rollback drill.','Production release checklist is signed; monitoring/owner support defined.'],
], [31*mm, 67*mm, 76*mm]), Spacer(1,7),
callout('First production-safe milestone', 'A scoped, read-only operational dashboard and reports whose numbers can be reconciled to a controlled source dataset, combined with server-side company isolation evidence. Do not wait for an aesthetic redesign; do not post accounting entries.'), PageBreak()]

story += section('9. Testing, release and recovery requirements', 'The existing suite provides a useful starting point but does not establish financial or tenant correctness.')
story += [table(['Test family','Required Option A coverage','Acceptance evidence'], [
 ['Calculation tests','Golden balances, restrictions, shared caps, rounding, date ordering, cancellation/reversal.','Approved historical examples; backend/API/report outputs agree.'],
 ['Concurrency and idempotency','Competing allocation/BOE actions, retries, duplicate requests and partial failures.','No overspend/duplicate debit; explicit response and audit event.'],
 ['Permission isolation','Role/company matrix; direct IDs; filters; exports; documents; background jobs.','Positive and negative server-side tests.'],
 ['Workflow E2E','Licence -> allocation -> BOE/invoice -> reconciliation candidate -> review outcome.','Isolated environment; no production records.'],
 ['UI quality','Loading/empty/error/denied states, keyboard navigation, responsive priority paths.','Page-specific acceptance checklist.'],
 ['Reporting','Screen/API/Excel/PDF filters, totals, sorting and pagination.','Parity sample and documented tolerance.'],
 ['Operations','Backups, restore rehearsal, task failure/retry, logging, monitoring and rollback.','Isolated restore success; release evidence retained.'],
], [34*mm, 86*mm, 54*mm]), Spacer(1,7),
P('Current test baseline', 'H2x'), P('The audited frontend run reported 543 passing tests out of 544, one failure in AllocationStrategyEditor, three lint errors, nine lint warnings and a passing typecheck. These figures do not measure backend domain coverage, production behaviour, company isolation or recovery. The failed test and lint errors should be treated as baseline quality debt, not quietly ignored.'), PageBreak()]

story += section('10. Required owner decisions and explicit exclusions', 'These decisions change scope, risk, cost or acceptance. They should be recorded before dependent work starts.')
story += [table(['Decision required','Recommended default','Risk of postponing','Owner / adviser'], [
 ['Legal-entity / master-data policy','Separate legal-entity scope by default; define exceptions explicitly.','Isolation design and historic remediation cannot be accepted.','Business owner'],
 ['Restriction authority and exceptions','Use official document reference, effective dates and approved examples.','Incorrect cap behaviour or undocumented overrides.','Owner + DFIA/domain adviser'],
 ['Historical correction policy','Use traceable reversal/amendment; preserve source and reviewer disposition.','Silent loss of history and unreliable reconciliation.','Business owner'],
 ['Approval thresholds','Owner approval for high-value, expired, override or downstream-dependent actions.','Unsafe one-person processing.','Business owner'],
 ['Essential reports','Prioritize daily exception, balance, expiry and reconciliation reports.','UI/report scope expands without operational value.','Owner / operators'],
 ['Accounting timing','Defer new GL until Option A exit gates are proven.','A ledger may formalize unreliable operational source data.','Owner + CA'],
], [37*mm, 57*mm, 53*mm, 33*mm]), Spacer(1,8),
callout('Why accounting is deferred', 'Operational reconciliation is included now because it directly protects licence and BOE/invoice workflows. Accounting is deferred because the audited code contains invoice/trade payment models but no discovered JournalEntry, chart of accounts, trial balance or bank-statement/bank-transaction domain. Adding those safely requires stable source transactions, CA-approved policies and a separate migration/cutover programme.'),
P('Explicit Option A exclusions', 'H2x'), P('New general ledger, double-entry posting, vouchers, receivable/payable ledgers, accounting bank reconciliation, trial balance, statutory Profit and Loss/balance sheet, financial-year close, Tally/accounting migration, and tax workflows are not part of Option A.'), PageBreak()]

story += section('11. Traceability, report locations and integrity statement', 'This detailed PDF is a management summary. The Markdown audit documents contain the working inventories and limitations.')
story += [table(['Detailed source document','Purpose'], [
 ['00_EXECUTIVE_SUMMARY.md','Decision summary and evidence posture.'],
 ['01_AUDIT_BASELINE_AND_EVIDENCE.md','Branch, local access and test baseline.'],
 ['03_PAGE_BY_PAGE_BROWSER_AUDIT.md','Pointer to detailed local browser audit matrix.'],
 ['10_CANONICAL_CALCULATION_AUDIT.md','Authoritative calculation-chain requirements.'],
 ['12_OPERATIONAL_RECONCILIATION_AUDIT.md','Metric limitations and reconciliation evidence requirements.'],
 ['15_SECURITY_AND_COMPANY_ISOLATION_AUDIT.md','Company isolation risk and required controls.'],
 ['17_TEST_COVERAGE_AND_QA_STRATEGY.md','Existing test evidence and proposed quality strategy.'],
 ['21-23 Option A documents','Option A detailed scope, phased roadmap and planning estimate.'],
 ['28-29 decisions and backlog','Scope-changing decisions, dependencies and independently deliverable work items.'],
 ['30_FINAL_AUDIT_COMPLETENESS_AND_LIMITATIONS.md','Explicit coverage boundaries and unverified areas.'],
], [74*mm, 108*mm]), Spacer(1,9),
callout('Integrity statement', 'No application source code, business records, database schema, migration, permissions, configuration, deployment or production system was changed for this assessment. The created documentation and PDF are audit artifacts only. Production remains unverified; all unverified findings must retain that label until supported by authorized evidence.', HexColor('#FFF2D9')),
P('Prepared for management review', 'H2x'), P('Recommended next action: approve the mandatory decisions and a short Phase 0 evidence/test-harness engagement. Re-estimate only after the authoritative business rules, tenant policy, source-data access and golden examples are available.'),]

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm,
                        title='License Manager - Option A detailed scope without accounting', author='License Manager audit')
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(OUT)
