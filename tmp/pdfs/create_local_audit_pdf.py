from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.pdfbase.pdfmetrics import stringWidth

OUT = "output/pdf/license-manager-localhost-audit-2026-10-31.pdf"

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleX", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24, leading=29, textColor=colors.HexColor("#102A43"), alignment=TA_CENTER, spaceAfter=9))
styles.add(ParagraphStyle(name="SubX", parent=styles["Normal"], fontSize=10, leading=14, textColor=colors.HexColor("#486581"), alignment=TA_CENTER, spaceAfter=18))
styles.add(ParagraphStyle(name="H1X", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=colors.HexColor("#102A43"), spaceBefore=12, spaceAfter=8))
styles.add(ParagraphStyle(name="H2X", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#243B53"), spaceBefore=8, spaceAfter=5))
styles.add(ParagraphStyle(name="BodyX", parent=styles["BodyText"], fontSize=9.1, leading=13, textColor=colors.HexColor("#243B53"), spaceAfter=6))
styles.add(ParagraphStyle(name="SmallX", parent=styles["BodyText"], fontSize=7.6, leading=10, textColor=colors.HexColor("#334E68")))
styles.add(ParagraphStyle(name="Callout", parent=styles["BodyText"], fontSize=10, leading=14, textColor=colors.HexColor("#102A43"), backColor=colors.HexColor("#EAF4FF"), borderColor=colors.HexColor("#9FB3C8"), borderWidth=0.5, borderPadding=8, spaceAfter=10))

def p(txt, style="BodyX"):
    return Paragraph(txt, styles[style])

def table(rows, widths):
    t = Table([[p(c, "SmallX") for c in r] for r in rows], colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#243B53")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("GRID", (0,0), (-1,-1), .25, colors.HexColor("#BCCCDC")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F0F4F8")]),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    return t

def footer(canvas, doc):
    canvas.saveState(); canvas.setStrokeColor(colors.HexColor("#D9E2EC")); canvas.line(18*mm, 14*mm, 192*mm, 14*mm)
    canvas.setFont("Helvetica", 7.5); canvas.setFillColor(colors.HexColor("#627D98"))
    canvas.drawString(18*mm, 9*mm, "License Manager - localhost audit - 31 Oct 2026")
    canvas.drawRightString(192*mm, 9*mm, f"Page {doc.page}")
    canvas.restoreState()

doc = SimpleDocTemplate(OUT, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=20*mm)
story = []
story += [Spacer(1, 18*mm), p("License Manager", "TitleX"), p("Localhost Audit and Implementation Scope", "TitleX"), p("Target: http://localhost:8000/  |  Evidence captured: 31 October 2026", "SubX")]
story += [p("Executive conclusion", "H1X"), p("The local instance is available and serves the React application shell successfully. Public health and OpenAPI endpoints respond; unauthenticated business endpoints correctly reject access. The audit does not establish authenticated workflow correctness, data integrity or production readiness because browser automation was unavailable and no credentials/test data were supplied.", "Callout")]
story += [table([
    ["Live check", "Observed result", "Assessment"],
    ["GET /", "HTTP 200; 1,036-byte SPA HTML; JS/CSS asset references", "PASS - shell reachable"],
    ["GET /api/health/", "HTTP 200 {status: ok}", "PASS - process health only"],
    ["GET /api/schema/", "HTTP 200; OpenAPI 3.0.3; 481,089 bytes", "PASS - API schema exposed"],
    ["GET /api/auth/me/, dashboard, reconciliation, companies", "HTTP 401; Bearer challenge", "PASS - unauthenticated access rejected"],
    ["Browser interaction", "Browser provider unavailable", "BLOCKED - no UI claim"],
], [35*mm, 82*mm, 45*mm]), Spacer(1, 10)]

story += [p("Observed errors and audit limitations", "H1X")]
story += [table([
    ["ID", "Severity", "Finding / evidence", "Implementation needed"],
    ["LIVE-01", "P2", "Local response identifies WSGIServer/CPython. This is acceptable for local development but not production evidence.", "Verify production ASGI/WSGI server, TLS, proxy headers, logging and rate limiting in staging."],
    ["LIVE-02", "P2", "No authenticated browser or API workflow was executed; local HTTP checks cannot validate pages, forms or permissions by role.", "Provide isolated test account/data or staging environment; run role-based workflow and accessibility suite."],
    ["QA-01", "P2", "Frontend suite previously executed: 543/544 tests passed; stale planning payload expectation fails.", "Agree API request contract then update/add regression test."],
    ["QA-02", "P2", "Frontend lint previously executed: 3 ESM require errors and 9 warnings.", "Make lint clean before release; migrate script or configure lint scope."],
    ["SEC-01", "P0 SaaS", "Repository review shows global role model and unscoped company/domain reads in material paths.", "Tenant/membership context, scoped repositories, object checks, isolation tests and backfill."],
    ["DFR-01", "P1", "Restriction pool groups by free-text percentage, not explicit group membership.", "Versioned restriction rule/group/member and immutable usage/reservation ledger."],
], [17*mm, 17*mm, 65*mm, 63*mm]), Spacer(1, 8)]

story += [p("What is currently evidenced", "H1X"), p("The repository contains Django/DRF APIs and React SPA routes for licences, SION planning, allotments, BOEs, trades, reports, ledger packages, masters and BOE-to-invoice reconciliation. Atomic transactions and row locks exist in critical planning/allotment paths. The reconciliation module is not bank reconciliation; it performs explicit BOE/invoice triage. Commercial invoice and trade payment models exist, but no general-ledger, journal-entry, chart-of-accounts, bank-statement or bank-transaction domain was found.", "BodyX")]

story += [p("Required implementation scope", "H1X")]
story += [table([
    ["Phase", "Scope", "Definition of done"],
    ["0. Baseline", "Confirm deployed commit, create isolated test harness, characterise current balances/restrictions and inventory permissions.", "Repeatable test environment; baseline examples and known gaps signed off."],
    ["1. Protection", "Choose internal vs external SaaS; tenant isolation, idempotency and role/object tests.", "Cross-tenant negative tests pass; unscoped access is blocked."],
    ["2. Single source of truth", "Canonical backend balance/restriction service; migrate reports/APIs/UI incrementally.", "Preview, commit and reports agree on golden data and concurrency cases."],
    ["3. UX foundation", "Route manifest, shared forms/tables/states, high-risk workflow redesign and accessibility gate.", "Keyboard/responsive/error/empty/loading behaviour verified in E2E."],
    ["4. DFIA/SION restrictions", "Explicit 2/3/5/10% individual/shared pools; AU policy; audit explanation and locking.", "No overspend under concurrent allocations; every result explains rule/base/usage."],
    ["5. Accounting", "Tenant/legal entity, chart, immutable balanced journals, subledgers, posting/reversal/period controls.", "Every posted entry balances; AR/AP and trial balance reconcile."],
    ["6. Bank reconciliation", "Statement import, normalisation, duplicate controls, matching/manual review, totals and audit history.", "End-to-end statement-to-ledger reconciliation tested including split/combined/override."],
], [25*mm, 78*mm, 59*mm])]

story += [PageBreak(), p("Restriction, accounting and bank design requirements", "H1X")]
story += [p("Restriction planning", "H2X"), p("Do not equate existing CIF condition pools and SION quantity percentage capacity until the business meaning is formally agreed. The new resolver should select an effective versioned rule, determine scope and group, calculate historical and planned use, lock a shared pool at commit, create an immutable consumption/reservation event and return a human-readable explanation. Invalid or conflicting configuration must warn/block rather than quietly permit allocation.", "BodyX")]
story += [p("Accounting", "H2X"), p("Build the double-entry core before P&L, balance sheet, advanced tax or Tally replacement. Required controls are: company/tenant-scoped chart, voucher numbering and states, Decimal/currency precision, idempotent source references, immutable posted lines, debit-credit equality, reversals, period locks, audit trail and subledger reconciliation. Indian GST/TDS/export treatment requires qualified tax review.", "BodyX")]
story += [p("Bank reconciliation", "H2X"), p("Implement it as a separate bounded context: statement batch/import preview, source-row retention and fingerprinting, canonical bank transactions, deterministic explainable matching, manual split/combined review, appropriate accounting postings and completion/reopen history. Start with validated CSV/XLSX; do not promise reliable PDF/bank-specific parsing without representative samples.", "BodyX")]
story += [p("Management decisions that unblock delivery", "H1X")]
story += [table([
    ["Decision", "Why it is required"],
    ["Deployment target and release authority", "Local HTTP success does not establish the deployed revision, configuration or operational controls."],
    ["Internal multi-company vs external SaaS", "Determines tenant model, migration strategy, security and commercial scope."],
    ["2/3/5/10% and AU definitions", "Determines rule base, shared-pool membership, priority, historical use and overrides."],
    ["Accounting first-release and tax policy", "Prevents building reports on unreliable financial foundations."],
    ["Bank formats and Tally migration", "Bounds adapters, import/mapping work and data-reconciliation effort."],
], [60*mm, 102*mm])]

story += [p("Verification plan before production", "H1X"), p("Use a seeded, isolated database/Redis namespace and role-specific accounts. Gate release on clean lint/typecheck/tests; backend unit/integration tests for Decimal, balances, restrictions and accounting invariants; API permission/tenant negatives; browser E2E for licence-to-allotment-to-BOE/trade flows; accessibility/mobile checks; migration/backfill reconciliation; load benchmarks; task retry/idempotency checks; and backup/restore rehearsal. Never treat static source review or an HTTP 200 as a completed financial workflow.", "Callout")]
story += [p("Evidence notes", "H1X"), p("Live evidence was captured via safe GET requests to localhost only. No credentials, mutations, data changes or destructive operations were used. The initial full repository assessment reports are located under docs/assessment/. The mandated repository code index was absent, which limits dependency-graph evidence. This document is a management scope report, not an implementation or production-readiness certification.", "BodyX")]

doc.build(story, onFirstPage=footer, onLaterPages=footer)
print(OUT)
