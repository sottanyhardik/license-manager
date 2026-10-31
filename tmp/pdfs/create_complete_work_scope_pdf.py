from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

OUT = "output/pdf/license-manager-complete-work-scope-2026-10-31.pdf"
s = getSampleStyleSheet()
s.add(ParagraphStyle(name="T", parent=s["Title"], fontName="Helvetica-Bold", fontSize=23, leading=27, alignment=TA_CENTER, textColor=colors.HexColor("#102A43"), spaceAfter=7))
s.add(ParagraphStyle(name="S", parent=s["Normal"], fontSize=9.5, leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#486581"), spaceAfter=15))
s.add(ParagraphStyle(name="H", parent=s["Heading1"], fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=colors.HexColor("#102A43"), spaceBefore=9, spaceAfter=6))
s.add(ParagraphStyle(name="H2", parent=s["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=colors.HexColor("#243B53"), spaceBefore=7, spaceAfter=4))
s.add(ParagraphStyle(name="B", parent=s["BodyText"], fontSize=8.8, leading=12.2, textColor=colors.HexColor("#243B53"), spaceAfter=5))
s.add(ParagraphStyle(name="SM", parent=s["BodyText"], fontSize=7.4, leading=9.5, textColor=colors.HexColor("#243B53")))
s.add(ParagraphStyle(name="Call", parent=s["BodyText"], fontSize=9.5, leading=13, textColor=colors.HexColor("#102A43"), backColor=colors.HexColor("#EAF4FF"), borderColor=colors.HexColor("#9FB3C8"), borderWidth=.5, borderPadding=7, spaceAfter=8))
def p(x, st="B"): return Paragraph(x, s[st])
def tbl(rows, widths):
    t=Table([[p(c,"SM") for c in r] for r in rows], colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#243B53")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),.25,colors.HexColor("#BCCCDC")),("VALIGN",(0,0),(-1,-1),"TOP"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F0F4F8")]),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    return t
def foot(c,d):
    c.saveState(); c.setStrokeColor(colors.HexColor("#D9E2EC")); c.line(18*mm,14*mm,192*mm,14*mm); c.setFont("Helvetica",7); c.setFillColor(colors.HexColor("#627D98")); c.drawString(18*mm,9*mm,"License Manager - complete work scope - 31 Oct 2026"); c.drawRightString(192*mm,9*mm,"Page %s"%d.page); c.restoreState()

doc=SimpleDocTemplate(OUT,pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=15*mm,bottomMargin=20*mm)
z=[]
z += [Spacer(1,14*mm),p("License Manager","T"),p("Complete Work Scope - One Integrated Business Application","T"),p("Live local inspection + repository assessment | 31 October 2026","S")]
z += [p("Purpose and boundary","H"),p("This scope defines the work required for users to operate licence management, trade operations, financial control, accounting and bank reconciliation from one application. It is a proposed implementation plan, not evidence that features already work. Live inspection used an authenticated local session in read-only mode; no business records were created, edited, deleted, planned, recalculated or reconciled.","Call")]
z += [p("Live data signals requiring immediate attention","H"),tbl([
["Signal","Observed locally","Required response"],
["Reconciliation","1,043 BOEs; 317 import invoices; only 2 matched; 53 unmatched invoices; 1,699 duplicate-debit findings.","P0 data triage, classification, root-cause analysis and protected remediation workflow."],
["Data completeness","Dashboard reports 109 Missing DGFT records and 6 pending invoices.","Data-quality owner, required-field rules, remediation queue, source/import fixes."],
["Planning governance","E1 has 8 active rules and 2 validation issues; metadata says last update/modifier unavailable.","Show issue details, require audit metadata, approval and effective-version controls."],
["BOE operations","Live records expose inline invoice entry, merge, edit and delete actions; multi-licence BOEs occur.","Impact preview, permission/approval controls, idempotent writes and audit/reversal path."],
],[35*mm,65*mm,62*mm])]
z += [p("Target operating model","H"),p("A tenant-aware modular monolith remains appropriate: React provides user workflows; Django application services own all financial/licence calculations; PostgreSQL holds authoritative transactional data; Celery/Redis support durable jobs; reports use approved read models. A user should see a consistent company context, actionable work queues, clear calculation explanations, audit history and safe recovery on every screen.","B")]

z += [PageBreak(),p("Complete functional scope","H"),tbl([
["Module","Required user capability","Essential implementation"],
["Identity and administration","Sign in, profile, company/team switch, roles, approvals, activity review.","Tenant, membership, capability policy, object scope, MFA/session policy, admin audit."],
["Masters","Companies, counterparties, ports, HS/SION/product/rate masters with controlled changes.","Global-vs-tenant policy, validation, effective dating, imports, duplicate merge, change approval."],
["Licences","Create/import, review balances, documents, status, expiry, item details and lifecycle.","Canonical balance service, document integrity, state transitions, expiry work queue, audit/reversal."],
["Planning and restrictions","Configure rules, preview plan, allocate, explain result and correct exceptions.","Versioned rules, explicit groups, 2/3/5/10% pools, AU policy, reservations, locking, Decimal standard."],
["Allotments","Create, allocate/reverse, monitor shortfalls and capacity.","Idempotency, row locking, plan/restriction checks, allocation history and exception approval."],
["BOE","Capture/PDF import, lines/documents, licence linkage, transfer letters and corrections.","Structured extraction review, duplicate detection, unit/currency validation, immutable source/audit links."],
["Trade and invoices","Purchase/sale, lines, counterparties, payments, attachments and status.","Final-party validation, paired trade safety, invoice numbering, source-to-ledger bridge."],
["Reconciliation","Find/match BOE-invoice exceptions and show ownership/outcome.","Prioritised queues, deterministic candidates, differences, bulk triage, safe merge/reverse, audit."],
["Reports and exports","Operational, licence, planning and financial reporting.","Single service/read-model source, date/company filters, export parity and report versioning."],
],[29*mm,61*mm,72*mm])]

z += [PageBreak(),p("Accounting and bank reconciliation","H"),p("Accounting must be implemented before claiming a Tally-level replacement. Existing commercial invoice/trade data becomes source data for controlled posting; it must not itself be treated as a general ledger.","Call")]
z += [tbl([
["Layer","Scope","Definition of done"],
["Foundation","Legal entity/company boundary, chart of accounts, account groups, accounting periods, vouchers, opening balances.","Configured accounts and periods with an approved ownership and numbering policy."],
["Journal engine","Draft/approved/posted states, immutable journal lines, idempotent source references, reversals, period locks.","Every posted voucher satisfies debit = credit using documented Decimal/currency precision."],
["Subledgers","Sales, purchases, AR/AP, receipts, payments, credit/debit notes, advances and allocations.","Customer/supplier outstanding and ageing reconcile exactly to control accounts."],
["Tax/compliance","GST/TDS/export treatment, invoice data, tax summaries and audit exports.","Rules signed off by qualified Indian tax adviser and verified against approved examples."],
["Bank reconciliation","CSV/XLSX import, statement batches, normalized rows, dedupe, match suggestions, manual split/combine, adjustments and close/reopen.","Statement and book balances reconcile with explainable outstanding items and immutable history."],
["Migration","Tally mapping, opening balance/data import, exception reports and parallel reconciliation.","Migration reconciliation signed off; rollback/exception handling rehearsed."],
],[31*mm,69*mm,62*mm])]
z += [p("Data-remediation workstream","H"),p("Create a protected data-quality hub: issue type, severity, source system/file, affected entity, financial/licence impact, assignee, reason code, recommended action, approval, before/after values and audit event. Prioritise duplicate debits; BOE/invoice missing links; CIF/quantity mismatches; zero/missing quantities; unclassified products; missing DGFT fields; inconsistent company/product names; stale planning mappings; and orphaned documents. Use dry-run repair previews and reversible corrections. Do not mass-correct records before baseline exports and business approval.","B")]

z += [PageBreak(),p("UI/UX and workflow redesign","H"),tbl([
["Area","Observed/likely friction","Required upgrade"],
["Dashboard","Useful counts, but only high-level signal; Missing DGFT and pending-invoice alerts lack visible remediation ownership.","Actionable queues, trend/age, data-quality score, owner/SLA and drill-down with safe filters."],
["Licence list","Long filter panel, opaque initial preselected statuses, wording defects and card density.","Saved views, filter chips, explainable defaults, compact table/cards toggle, clear reset, column preferences."],
["Planning","Validation issue count is visible but not actionable; metadata is unavailable.","Rule health drawer, impact simulation, version comparison, audit timeline, approval/review gates."],
["BOE","High-impact actions sit beside records; delete/merge/invoice action needs stronger guardrails.","Impact preview, reason/approval, undo/reversal, document panel and linked-record graph."],
["Reconciliation","Large exception volume; row actions require rapid but safe review.","Queue filters/priorities, candidate confidence, side-by-side evidence, bulk dry run, exception ownership."],
["Global system","Consistent navigation is now visible, but every module needs predictable loading/empty/error/success patterns.","Design tokens, accessible controls, command palette, responsive data grids, keyboard flow and Axe tests."],
],[31*mm,64*mm,67*mm])]
z += [p("Important UX rules","H"),p("Show currency, unit and date context beside every material number. Never hide a restrictive filter. Do not allow destructive or financially consequential actions without a clear impact statement, permission check, reason and audit record. Keep calculated balances read-only in the frontend; present backend explanation rather than duplicate calculations.","Call")]

z += [PageBreak(),p("Delivery plan, tests and release gates","H"),tbl([
["Phase","Scope","Dependencies"],
["0 - Baseline","Confirm deployed version; isolate test database/Redis; golden data; data-quality/reconciliation register.","Environment, business SMEs."],
["1 - Containment","Tenant decision, permission/object scoping, critical data protection and regression tests.","Data classification and company model."],
["2 - SSOT","Balance, allocation and restriction service contracts; caller migration; report parity.","Golden examples, Decimal rules."],
["3 - UX foundation","Route/form/table/error primitives; dashboard/list/reconciliation work queues.","Stable APIs and workflow ownership."],
["4 - Restriction planning","Explicit pools, AU policy, versioned rules, plan/commit/concurrency/audit.","Regulatory/business decisions."],
["5 - Accounting","Ledger/subledgers/posting/reversal/periods, then financial reports.","Tenant and tax/CA review."],
["6 - Bank reconciliation","Import/adapters/matching/manual review/totals/audit/ledger linkage.","Posted accounting foundation and statement samples."],
["7 - Hardening","Performance, backups/restore, security, monitoring, accessibility, staging/release drills.","All prior contracts and test automation."],
],[27*mm,79*mm,56*mm])]
z += [p("Minimum test matrix","H"),p("Unit: balances, Decimal rounding, restriction resolution, journal balancing. Integration: locks, idempotency, reversals, imports, query scoping. API: validation and tenant/role negatives. E2E: licence -> plan -> allotment -> BOE -> trade -> reconciliation; invoice/payment -> journal -> bank match. Data: duplicate, missing, zero, invalid unit/currency, stale mapping. Nonfunctional: accessibility, responsive layouts, performance, restore/recovery and security scanning. A test is PASS only after execution in an isolated environment with recorded evidence.","B")]
z += [p("Management decisions","H"),p("Approve: internal multi-company versus external SaaS; company/tenant hierarchy; restriction calculation bases and AU meaning; accounting/tax scope; Tally migration requirement; supported bank formats; approval thresholds; historic-data correction policy; target scale and release authority. These decisions control the schedule and prevent building conflicting rules.","Call")]
z += [p("Assessment limitation","H"),p("The live review confirms authenticated presentation and selected operational data, but did not perform mutations. Browser-driven functional tests, API write tests and financial posting tests must be run in a dedicated seeded test environment. The repository dependency index expected by AGENTS.md was unavailable. No application code, configuration, database record or production environment was changed.","B")]
doc.build(z,onFirstPage=foot,onLaterPages=foot); print(OUT)
